# Integration Architecture & Agentic Framework
## Deep Technical Specification

---

## 1. Frontend/Backend DB Integration Strategy

### 1.1 The Problem

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SYSTEMS                              │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │  Gmail  │ │ GDrive  │ │Calendar │ │Outlook  │ │  Jira   │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
│       │           │           │           │           │         │
│       └───────────┴───────────┴───────────┴───────────┘         │
│                               │                                  │
│                               ▼                                  │
│              ┌────────────────────────────────┐                  │
│              │   FRONTEND/BACKEND DB          │                  │
│              │   (Their responsibility)       │                  │
│              │   - Raw emails, documents      │                  │
│              │   - OAuth tokens               │                  │
│              │   - User accounts              │                  │
│              └────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ HOW?
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        AI SYSTEM DB                              │
│              (Your responsibility)                               │
│              - Embeddings                                        │
│              - Knowledge items                                   │
│              - Chat history                                      │
│              - User preferences                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Solution: Integration Service Layer (NOT NL2SQL)

**Why NOT NL2SQL:**
- Security risk (SQL injection, data exposure)
- Tight coupling to their schema (breaks when they change)
- Performance unpredictable
- Hard to maintain

**Instead: Dedicated Integration Service with defined contracts**

```
┌─────────────────────────────────────────────────────────────────┐
│                  INTEGRATION ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────┘

   Frontend/Backend Team                      AI Team
   ─────────────────────                      ────────
          │                                       │
          │                                       │
   ┌──────▼──────┐                         ┌─────▼─────┐
   │  Their DB   │                         │  AI DB    │
   │  (Source)   │                         │ (pgvector)│
   └──────┬──────┘                         └─────▲─────┘
          │                                      │
          │                                      │
   ┌──────▼─────────────────────────────────────┴─────┐
   │              INTEGRATION SERVICE                  │
   │                                                   │
   │  Option A: REST API (They expose, we consume)    │
   │  Option B: Shared Read Replica (We query)        │
   │  Option C: Event Stream (Kafka/Redis pub-sub)    │
   │                                                   │
   └───────────────────────────────────────────────────┘
```

### 1.3 Recommended: Option A - REST API Contract

**Frontend/Backend team exposes these endpoints for AI system:**

```yaml
# API Contract: External Data Service
# Base URL: https://internal-api.company.com/v1/data

endpoints:

  # ─────────────────────────────────────────────────────
  # GMAIL
  # ─────────────────────────────────────────────────────

  GET /users/{user_id}/emails:
    description: "Get emails for initial sync or incremental"
    query_params:
      - since: datetime (ISO 8601) - for incremental sync
      - limit: int (default 100, max 500)
      - cursor: string - pagination cursor
    response:
      items:
        - id: string (Gmail message ID)
          thread_id: string
          from: string (email address)
          to: string[]
          cc: string[]
          subject: string
          body_text: string (plain text)
          body_html: string (optional)
          date: datetime
          labels: string[]
          attachments: [{name, mime_type, size, gdrive_id?}]
          is_read: boolean
          is_starred: boolean
      next_cursor: string | null
      has_more: boolean

  GET /users/{user_id}/emails/{email_id}:
    description: "Get single email with full content"
    response:
      # Full email object

  # ─────────────────────────────────────────────────────
  # GOOGLE DRIVE
  # ─────────────────────────────────────────────────────

  GET /users/{user_id}/documents:
    description: "Get documents metadata and content"
    query_params:
      - since: datetime
      - limit: int
      - cursor: string
      - mime_types: string[] (filter by type)
    response:
      items:
        - id: string (Drive file ID)
          name: string
          mime_type: string
          content_text: string (extracted text)
          folder_path: string
          created_at: datetime
          modified_at: datetime
          size_bytes: int
          shared_with: string[]
          owner: string
      next_cursor: string | null

  GET /users/{user_id}/documents/{doc_id}:
    description: "Get single document with full content"

  # ─────────────────────────────────────────────────────
  # CALENDAR
  # ─────────────────────────────────────────────────────

  GET /users/{user_id}/events:
    description: "Get calendar events"
    query_params:
      - start_date: date
      - end_date: date
      - limit: int
    response:
      items:
        - id: string
          title: string
          description: string
          start: datetime
          end: datetime
          location: string
          attendees: [{email, name, status}]
          recurrence: string | null
          meet_link: string | null
          created_by: string

  # ─────────────────────────────────────────────────────
  # JIRA
  # ─────────────────────────────────────────────────────

  GET /users/{user_id}/jira/issues:
    description: "Get Jira issues user has access to"
    query_params:
      - since: datetime
      - project_keys: string[]
      - status: string[]
      - limit: int
    response:
      items:
        - id: string
          key: string (PROJ-123)
          project_key: string
          type: string (task, bug, story, epic)
          summary: string
          description: string
          status: string
          priority: string
          assignee: string
          reporter: string
          created_at: datetime
          updated_at: datetime
          labels: string[]
          components: string[]

  POST /users/{user_id}/jira/issues:
    description: "Create new Jira issue"
    body:
      project_key: string
      type: string
      summary: string
      description: string
      assignee: string (optional)
      priority: string (optional)
      labels: string[] (optional)
    response:
      id: string
      key: string
      url: string

  # ─────────────────────────────────────────────────────
  # WEBHOOKS (They call us)
  # ─────────────────────────────────────────────────────

  # They register webhooks with us:
  # When email arrives → POST our /webhooks/email-created
  # When doc changes → POST our /webhooks/document-updated
  # etc.
```

---

## 2. First-Time Sync: Detailed Flow

### 2.1 Sequence Diagram

```
┌──────┐     ┌────────┐     ┌──────────────┐     ┌─────────────┐     ┌────────┐
│ User │     │Frontend│     │External Data │     │  AI System  │     │  AI DB │
│      │     │Backend │     │   Service    │     │             │     │        │
└──┬───┘     └───┬────┘     └──────┬───────┘     └──────┬──────┘     └───┬────┘
   │             │                  │                    │                │
   │ 1. Connect Gmail               │                    │                │
   │─────────────>                  │                    │                │
   │             │                  │                    │                │
   │             │ 2. OAuth flow    │                    │                │
   │             │<─────────────────>                    │                │
   │             │                  │                    │                │
   │             │ 3. Store tokens  │                    │                │
   │             │──────────────────>                    │                │
   │             │                  │                    │                │
   │             │ 4. Notify AI: Start sync              │                │
   │             │───────────────────────────────────────>                │
   │             │                  │                    │                │
   │             │                  │    5. GET /emails  │                │
   │             │                  │<───────────────────│                │
   │             │                  │                    │                │
   │             │                  │    6. Return batch │                │
   │             │                  │────────────────────>                │
   │             │                  │                    │                │
   │             │                  │                    │ 7. Process     │
   │             │                  │                    │    - Parse     │
   │             │                  │                    │    - Summarize │
   │             │                  │                    │    - Embed     │
   │             │                  │                    │────────────────>
   │             │                  │                    │                │
   │             │                  │                    │ 8. Repeat      │
   │             │                  │<───────────────────│    until done  │
   │             │                  │────────────────────>                │
   │             │                  │                    │────────────────>
   │             │                  │                    │                │
   │             │ 9. Sync complete │                    │                │
   │             │<──────────────────────────────────────│                │
   │             │                  │                    │                │
   │ 10. Ready!  │                  │                    │                │
   │<────────────│                  │                    │                │
```

### 2.2 Initial Sync Implementation

```python
# sync_service.py

from datetime import datetime, timedelta
from typing import AsyncGenerator
import asyncio
import httpx
from openai import AsyncOpenAI

class SyncService:
    def __init__(
        self,
        external_api_base: str,
        external_api_key: str,
        openai_client: AsyncOpenAI,
        db_session
    ):
        self.external_api = httpx.AsyncClient(
            base_url=external_api_base,
            headers={"Authorization": f"Bearer {external_api_key}"}
        )
        self.openai = openai_client
        self.db = db_session

    async def initial_sync(
        self,
        user_id: str,
        sources: list[str],
        config: dict
    ) -> str:
        """
        Trigger initial sync for a new user.
        Returns sync_id for tracking progress.
        """
        sync_id = str(uuid.uuid4())

        # Create sync record
        sync_record = await self.db.execute(
            """
            INSERT INTO integration_sync (id, user_id, status)
            VALUES ($1, $2, 'started')
            RETURNING id
            """,
            sync_id, user_id
        )

        # Launch background tasks for each source
        tasks = []

        if 'gmail' in sources:
            tasks.append(self._sync_gmail(
                sync_id, user_id,
                days=config.get('gmail_days', 30)
            ))

        if 'gdrive' in sources:
            tasks.append(self._sync_gdrive(
                sync_id, user_id,
                months=config.get('document_months', 6)
            ))

        if 'jira' in sources:
            tasks.append(self._sync_jira(
                sync_id, user_id,
                months=config.get('jira_months', 3)
            ))

        if 'calendar' in sources:
            tasks.append(self._sync_calendar(
                sync_id, user_id,
                days=config.get('calendar_days', 30)
            ))

        # Run syncs concurrently
        asyncio.create_task(self._run_syncs(sync_id, tasks))

        return sync_id

    async def _run_syncs(self, sync_id: str, tasks: list):
        """Run all sync tasks and update status."""
        try:
            await asyncio.gather(*tasks)
            await self._update_sync_status(sync_id, 'completed')
        except Exception as e:
            await self._update_sync_status(sync_id, 'failed', str(e))

    async def _sync_gmail(
        self,
        sync_id: str,
        user_id: str,
        days: int
    ):
        """Sync Gmail emails."""
        since = datetime.utcnow() - timedelta(days=days)
        cursor = None
        total_synced = 0

        while True:
            # Fetch batch from external service
            response = await self.external_api.get(
                f"/users/{user_id}/emails",
                params={
                    "since": since.isoformat(),
                    "limit": 100,
                    "cursor": cursor
                }
            )
            data = response.json()

            # Process batch
            for email in data['items']:
                await self._process_email(user_id, email)
                total_synced += 1

            # Update progress
            await self._update_source_progress(
                sync_id, 'gmail', total_synced
            )

            # Check pagination
            if not data.get('has_more'):
                break
            cursor = data['next_cursor']

        # Mark source complete
        await self._mark_source_complete(sync_id, 'gmail', total_synced)

    async def _process_email(self, user_id: str, email: dict):
        """Process single email: summarize, embed, store."""

        # 1. Generate summary (for hybrid approach)
        summary = await self._generate_email_summary(email)

        # 2. Extract entities
        entities = await self._extract_entities(email, summary)

        # 3. Create embedding from summary
        embedding = await self._create_embedding(summary)

        # 4. Store knowledge item
        item_id = await self.db.execute(
            """
            INSERT INTO knowledge_items
            (user_id, source_type, source_id, content_type, title, summary, content, metadata, source_created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            ON CONFLICT (user_id, source_type, source_id)
            DO UPDATE SET summary = $6, content = $7, metadata = $8, synced_at = NOW()
            RETURNING id
            """,
            user_id,
            'gmail',
            email['id'],
            'email',
            email['subject'],
            summary,
            email['body_text'][:10000],  # Truncate very long emails
            json.dumps({
                'from': email['from'],
                'to': email['to'],
                'thread_id': email['thread_id'],
                'labels': email['labels'],
                'date': email['date']
            }),
            email['date']
        )

        # 5. Store embedding
        await self.db.execute(
            """
            INSERT INTO embeddings (knowledge_item_id, user_id, embedding, chunk_text)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (knowledge_item_id) WHERE chunk_index = 0
            DO UPDATE SET embedding = $3, chunk_text = $4
            """,
            item_id, user_id, embedding, summary
        )

        # 6. Store entities and mentions
        for entity in entities:
            await self._store_entity_mention(user_id, entity, item_id)

    async def _generate_email_summary(self, email: dict) -> str:
        """Generate concise summary for embedding."""
        prompt = f"""Summarize this email in 2-3 sentences. Capture:
- Main topic or request
- Key people mentioned
- Any action items or deadlines

From: {email['from']}
To: {', '.join(email['to'][:3])}
Subject: {email['subject']}
Date: {email['date']}

Body:
{email['body_text'][:3000]}
"""
        response = await self.openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3
        )
        return response.choices[0].message.content

    async def _extract_entities(self, email: dict, summary: str) -> list[dict]:
        """Extract entities (people, projects, topics) from email."""
        prompt = f"""Extract entities from this email. Return JSON array.

Email:
From: {email['from']}
Subject: {email['subject']}
Summary: {summary}

Extract:
- People (name, email if available)
- Projects/products mentioned
- Companies/organizations
- Key topics

Return format:
[
  {{"type": "person", "name": "John Smith", "email": "john@company.com"}},
  {{"type": "project", "name": "Q1 Launch"}},
  {{"type": "topic", "name": "budget planning"}}
]
"""
        response = await self.openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0,
            response_format={"type": "json_object"}
        )

        try:
            result = json.loads(response.choices[0].message.content)
            return result.get('entities', result) if isinstance(result, dict) else result
        except:
            return []

    async def _create_embedding(self, text: str) -> list[float]:
        """Create embedding vector for text."""
        response = await self.openai.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    async def _sync_gdrive(self, sync_id: str, user_id: str, months: int):
        """Sync Google Drive documents with chunking."""
        since = datetime.utcnow() - timedelta(days=months * 30)
        cursor = None
        total_synced = 0

        while True:
            response = await self.external_api.get(
                f"/users/{user_id}/documents",
                params={
                    "since": since.isoformat(),
                    "limit": 50,
                    "cursor": cursor
                }
            )
            data = response.json()

            for doc in data['items']:
                await self._process_document(user_id, doc)
                total_synced += 1

            await self._update_source_progress(sync_id, 'gdrive', total_synced)

            if not data.get('has_more'):
                break
            cursor = data['next_cursor']

        await self._mark_source_complete(sync_id, 'gdrive', total_synced)

    async def _process_document(self, user_id: str, doc: dict):
        """Process document: chunk, embed each chunk, store."""

        content = doc['content_text']

        # 1. Chunk the document
        chunks = self._chunk_document(content)

        # 2. Store knowledge item (main record)
        item_id = await self.db.execute(
            """
            INSERT INTO knowledge_items
            (user_id, source_type, source_id, content_type, title, content, metadata, source_created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (user_id, source_type, source_id)
            DO UPDATE SET title = $5, content = $6, metadata = $7, synced_at = NOW()
            RETURNING id
            """,
            user_id,
            'gdrive',
            doc['id'],
            'document',
            doc['name'],
            content[:50000],  # Store full content up to limit
            json.dumps({
                'mime_type': doc['mime_type'],
                'folder_path': doc['folder_path'],
                'total_chunks': len(chunks),
                'modified_at': doc['modified_at']
            }),
            doc['created_at']
        )

        # 3. Delete old embeddings (for re-sync)
        await self.db.execute(
            "DELETE FROM embeddings WHERE knowledge_item_id = $1",
            item_id
        )

        # 4. Create embedding for each chunk
        for i, chunk in enumerate(chunks):
            embedding = await self._create_embedding(chunk['text'])

            await self.db.execute(
                """
                INSERT INTO embeddings
                (knowledge_item_id, user_id, embedding, chunk_index, chunk_text)
                VALUES ($1, $2, $3, $4, $5)
                """,
                item_id, user_id, embedding, i, chunk['text']
            )

        # 5. Extract and store entities
        entities = await self._extract_entities_from_doc(doc, chunks[0]['text'] if chunks else '')
        for entity in entities:
            await self._store_entity_mention(user_id, entity, item_id)

    def _chunk_document(
        self,
        content: str,
        chunk_size: int = 600,
        overlap: int = 100
    ) -> list[dict]:
        """Chunk document with overlap."""
        # Split by paragraphs first
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_words = len(para.split())

            if current_size + para_words > chunk_size and current_chunk:
                # Save chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append({
                    'text': chunk_text,
                    'index': len(chunks),
                    'word_count': current_size
                })

                # Keep last paragraph for overlap
                if current_chunk:
                    current_chunk = [current_chunk[-1]]
                    current_size = len(current_chunk[0].split())
                else:
                    current_chunk = []
                    current_size = 0

            current_chunk.append(para)
            current_size += para_words

        # Don't forget last chunk
        if current_chunk:
            chunks.append({
                'text': '\n\n'.join(current_chunk),
                'index': len(chunks),
                'word_count': current_size
            })

        return chunks
```

---

## 3. Real-Time Sync: Document Changes

### 3.1 Webhook Handler

```python
# webhooks.py

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from datetime import datetime

router = APIRouter(prefix="/webhooks")

class ItemCreatedEvent(BaseModel):
    user_id: str
    source: str  # gmail, gdrive, jira, calendar
    source_id: str
    content_type: str
    data: dict
    timestamp: datetime

class ItemUpdatedEvent(BaseModel):
    user_id: str
    source: str
    source_id: str
    changes: dict  # What changed
    full_data: dict  # Full current state
    timestamp: datetime

class ItemDeletedEvent(BaseModel):
    user_id: str
    source: str
    source_id: str
    timestamp: datetime


@router.post("/item-created")
async def handle_item_created(
    event: ItemCreatedEvent,
    background_tasks: BackgroundTasks,
    sync_service: SyncService = Depends(get_sync_service)
):
    """
    Called by frontend/backend when new item is created.
    Processes immediately for real-time availability.
    """

    # Add to background for non-blocking response
    background_tasks.add_task(
        sync_service.process_new_item,
        event.user_id,
        event.source,
        event.source_id,
        event.content_type,
        event.data
    )

    return {"status": "accepted", "source_id": event.source_id}


@router.post("/item-updated")
async def handle_item_updated(
    event: ItemUpdatedEvent,
    background_tasks: BackgroundTasks,
    sync_service: SyncService = Depends(get_sync_service)
):
    """
    Called when existing item is modified.
    Re-generates embeddings if content changed.
    """

    # Check if content changed (not just metadata)
    content_fields = ['body_text', 'content_text', 'description', 'summary']
    content_changed = any(
        field in event.changes
        for field in content_fields
    )

    if content_changed:
        # Re-process entirely
        background_tasks.add_task(
            sync_service.reprocess_item,
            event.user_id,
            event.source,
            event.source_id,
            event.full_data
        )
    else:
        # Just update metadata
        background_tasks.add_task(
            sync_service.update_item_metadata,
            event.user_id,
            event.source,
            event.source_id,
            event.changes
        )

    return {"status": "accepted", "reprocessing": content_changed}


@router.post("/item-deleted")
async def handle_item_deleted(
    event: ItemDeletedEvent,
    sync_service: SyncService = Depends(get_sync_service)
):
    """
    Called when item is deleted.
    Removes from AI DB and cleans up embeddings.
    """

    await sync_service.delete_item(
        event.user_id,
        event.source,
        event.source_id
    )

    return {"status": "deleted"}
```

### 3.2 Re-processing Logic

```python
# sync_service.py (continued)

class SyncService:
    # ... previous methods ...

    async def process_new_item(
        self,
        user_id: str,
        source: str,
        source_id: str,
        content_type: str,
        data: dict
    ):
        """Process newly created item in real-time."""

        if source == 'gmail':
            await self._process_email(user_id, data)

        elif source == 'gdrive':
            await self._process_document(user_id, data)

        elif source == 'jira':
            await self._process_jira_issue(user_id, data)

        elif source == 'calendar':
            await self._process_calendar_event(user_id, data)

        # Invalidate relevant Redis caches
        await self._invalidate_cache(user_id, source)

    async def reprocess_item(
        self,
        user_id: str,
        source: str,
        source_id: str,
        full_data: dict
    ):
        """Re-process item when content changes."""

        # Get existing item
        existing = await self.db.fetchrow(
            """
            SELECT id, metadata FROM knowledge_items
            WHERE user_id = $1 AND source_type = $2 AND source_id = $3
            """,
            user_id, source, source_id
        )

        if not existing:
            # New item, process normally
            await self.process_new_item(user_id, source, source_id, 'unknown', full_data)
            return

        item_id = existing['id']

        # Delete old embeddings
        await self.db.execute(
            "DELETE FROM embeddings WHERE knowledge_item_id = $1",
            item_id
        )

        # Delete old entity mentions
        await self.db.execute(
            "DELETE FROM entity_mentions WHERE knowledge_item_id = $1",
            item_id
        )

        # Re-process based on source
        if source == 'gmail':
            summary = await self._generate_email_summary(full_data)
            embedding = await self._create_embedding(summary)
            entities = await self._extract_entities(full_data, summary)

            # Update knowledge item
            await self.db.execute(
                """
                UPDATE knowledge_items
                SET summary = $1, content = $2, synced_at = NOW()
                WHERE id = $3
                """,
                summary, full_data.get('body_text', '')[:10000], item_id
            )

            # Insert new embedding
            await self.db.execute(
                """
                INSERT INTO embeddings (knowledge_item_id, user_id, embedding, chunk_text)
                VALUES ($1, $2, $3, $4)
                """,
                item_id, user_id, embedding, summary
            )

        elif source == 'gdrive':
            content = full_data.get('content_text', '')
            chunks = self._chunk_document(content)

            # Update knowledge item
            await self.db.execute(
                """
                UPDATE knowledge_items
                SET title = $1, content = $2, metadata = metadata || $3, synced_at = NOW()
                WHERE id = $4
                """,
                full_data.get('name'),
                content[:50000],
                json.dumps({'total_chunks': len(chunks)}),
                item_id
            )

            # Insert new embeddings for each chunk
            for i, chunk in enumerate(chunks):
                embedding = await self._create_embedding(chunk['text'])
                await self.db.execute(
                    """
                    INSERT INTO embeddings
                    (knowledge_item_id, user_id, embedding, chunk_index, chunk_text)
                    VALUES ($1, $2, $3, $4, $5)
                    """,
                    item_id, user_id, embedding, i, chunk['text']
                )

        # Invalidate cache
        await self._invalidate_cache(user_id, source)

    async def delete_item(
        self,
        user_id: str,
        source: str,
        source_id: str
    ):
        """Remove item and all related data."""

        # Get item ID first
        item = await self.db.fetchrow(
            """
            SELECT id FROM knowledge_items
            WHERE user_id = $1 AND source_type = $2 AND source_id = $3
            """,
            user_id, source, source_id
        )

        if not item:
            return

        item_id = item['id']

        # Delete in order (foreign keys)
        await self.db.execute(
            "DELETE FROM entity_mentions WHERE knowledge_item_id = $1",
            item_id
        )

        await self.db.execute(
            "DELETE FROM embeddings WHERE knowledge_item_id = $1",
            item_id
        )

        await self.db.execute(
            "DELETE FROM knowledge_items WHERE id = $1",
            item_id
        )

        # Invalidate cache
        await self._invalidate_cache(user_id, source)

    async def _invalidate_cache(self, user_id: str, source: str):
        """Invalidate Redis cache for user's source data."""
        patterns = [
            f"working:{user_id}:*",
            f"context:{user_id}:{source}:*",
            f"recent:{user_id}:*"
        ]
        for pattern in patterns:
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
```

---

## 4. Agentic Framework Choice

### 4.1 Recommendation: Custom Framework with OpenAI SDK

**Why NOT LangChain/LangGraph:**
- Too abstracted, hard to control
- Verbose for simple flows
- Extra dependency overhead
- Debugging is harder with abstractions
- Overkill for our use case

**Why Custom + OpenAI SDK (Function Calling):**
- **Full control**: Direct access to OpenAI API, no hidden magic
- **Lightweight**: No extra dependencies, just `openai` package
- **Debuggable**: Clear execution flow, easy to trace
- **Flexible**: Easy to customize tool execution, state management
- **Native async**: Built-in async support with `AsyncOpenAI`
- **Function calling**: Native support for tools/functions
- **Structured outputs**: JSON mode for reliable parsing
- **Cost efficient**: Direct API calls, no middleware overhead

### 4.2 Architecture: Orchestrator + Specialist Agents

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER REQUEST                                 │
│    "Create Jira tasks from John's proposal email"               │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR AGENT                             │
│                                                                  │
│  Role: Plan execution, delegate to specialists, assemble result │
│  Model: GPT-4o (best reasoning)                                 │
│                                                                  │
│  Available Tools:                                                │
│  ├── retrieve_context(query, sources, filters)                  │
│  ├── delegate_to_agent(agent_type, task, context)               │
│  ├── ask_user_question(question, options)                       │
│  └── execute_action(action_type, params)                        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  EMAIL AGENT    │  │ DOCUMENT AGENT  │  │   TASK AGENT    │
│                 │  │                 │  │                 │
│ • Draft emails  │  │ • Summarize docs│  │ • Create Jira   │
│ • Reply suggest │  │ • Extract info  │  │ • Update status │
│ • Thread summary│  │ • Create docs   │  │ • Find tasks    │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         │                     │                     │
         └─────────────────────┴─────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ACTION EXECUTOR                              │
│                                                                 │
│  Executes final actions via external APIs:                      │
│  • POST /users/{user_id}/jira/issues (create task)              │
│  • POST /users/{user_id}/emails/send (send email)               │
│  • POST /users/{user_id}/calendar/events (create event)         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Agent Implementation

### 5.1 Base Agent Structure

```python
# agents/base.py

from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel
from openai import AsyncOpenAI

class AgentState(BaseModel):
    """Current state of agent execution."""
    user_id: str
    session_id: str
    messages: list[dict]
    context: list[dict]
    pending_actions: list[dict]
    completed_actions: list[dict]
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    final_response: Optional[str] = None


class Tool(BaseModel):
    """Tool definition for function calling."""
    name: str
    description: str
    parameters: dict  # JSON Schema


class BaseAgent(ABC):
    """Base class for all agents."""

    def __init__(
        self,
        openai_client: AsyncOpenAI,
        model: str = "gpt-4o"
    ):
        self.openai = openai_client
        self.model = model

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Agent's system prompt."""
        pass

    @property
    @abstractmethod
    def tools(self) -> list[Tool]:
        """Tools available to this agent."""
        pass

    @abstractmethod
    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        state: AgentState
    ) -> tuple[Any, AgentState]:
        """Execute a tool and return result + updated state."""
        pass

    async def run(
        self,
        task: str,
        state: AgentState,
        max_iterations: int = 10
    ) -> AgentState:
        """Run agent until completion or max iterations."""

        # Add task to messages
        state.messages.append({
            "role": "user",
            "content": task
        })

        for i in range(max_iterations):
            # Call LLM
            response = await self.openai.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    *state.messages
                ],
                tools=[self._tool_to_openai(t) for t in self.tools],
                tool_choice="auto"
            )

            message = response.choices[0].message

            # Add assistant message to history
            state.messages.append(message.model_dump())

            # Check if done (no tool calls)
            if not message.tool_calls:
                state.final_response = message.content
                return state

            # Execute tool calls
            for tool_call in message.tool_calls:
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)

                result, state = await self.execute_tool(
                    tool_name, arguments, state
                )

                # Add tool result to messages
                state.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result)
                })

                # Check if needs user input
                if state.needs_clarification:
                    return state

        # Max iterations reached
        state.final_response = "I need more information to complete this task."
        return state

    def _tool_to_openai(self, tool: Tool) -> dict:
        """Convert Tool to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        }
```

### 5.2 Orchestrator Agent

```python
# agents/orchestrator.py

from agents.base import BaseAgent, AgentState, Tool
from context_service import ContextService
from agents.email_agent import EmailAgent
from agents.document_agent import DocumentAgent
from agents.task_agent import TaskAgent

class OrchestratorAgent(BaseAgent):
    """
    Main agent that coordinates all tasks.
    Retrieves context, delegates to specialists, executes actions.
    """

    def __init__(
        self,
        openai_client,
        context_service: ContextService,
        action_executor,
        **kwargs
    ):
        super().__init__(openai_client, model="gpt-4o", **kwargs)
        self.context_service = context_service
        self.action_executor = action_executor

        # Initialize specialist agents
        self.specialists = {
            "email": EmailAgent(openai_client),
            "document": DocumentAgent(openai_client),
            "task": TaskAgent(openai_client),
        }

    @property
    def system_prompt(self) -> str:
        return """You are an intelligent AI assistant orchestrator.

Your role:
1. Understand the user's request
2. Retrieve relevant context from their data (emails, documents, tasks, calendar)
3. Delegate to specialist agents when needed
4. Execute actions (create tasks, send emails, etc.)
5. Ask clarifying questions if information is missing

IMPORTANT RULES:
- Always retrieve context before taking action
- If required information is missing, ask the user
- Confirm destructive actions before executing
- Break complex tasks into steps

Available specialists:
- email: Draft emails, summarize threads, suggest replies
- document: Summarize docs, extract information, create content
- task: Create/update Jira tasks, find related tasks

After completing a task, provide a clear summary of what was done."""

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="retrieve_context",
                description="Search user's data for relevant context. Use before any action.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query describing what to find"
                        },
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Sources to search: gmail, gdrive, jira, calendar"
                        },
                        "time_filter": {
                            "type": "string",
                            "description": "Time filter: today, yesterday, last_week, last_month, custom"
                        },
                        "entity_filter": {
                            "type": "string",
                            "description": "Filter by entity name (person, project)"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="delegate_to_specialist",
                description="Delegate a subtask to a specialist agent",
                parameters={
                    "type": "object",
                    "properties": {
                        "specialist": {
                            "type": "string",
                            "enum": ["email", "document", "task"],
                            "description": "Which specialist to use"
                        },
                        "task": {
                            "type": "string",
                            "description": "Task for the specialist"
                        },
                        "context_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "IDs of context items to pass"
                        }
                    },
                    "required": ["specialist", "task"]
                }
            ),
            Tool(
                name="ask_user",
                description="Ask user for clarification or confirmation",
                parameters={
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Question to ask"
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional multiple choice options"
                        },
                        "required_for": {
                            "type": "string",
                            "description": "What this information is needed for"
                        }
                    },
                    "required": ["question"]
                }
            ),
            Tool(
                name="execute_action",
                description="Execute a final action (create task, send email, etc.)",
                parameters={
                    "type": "object",
                    "properties": {
                        "action_type": {
                            "type": "string",
                            "enum": [
                                "create_jira_task",
                                "update_jira_task",
                                "send_email",
                                "create_calendar_event",
                                "create_document"
                            ]
                        },
                        "params": {
                            "type": "object",
                            "description": "Action-specific parameters"
                        },
                        "confirm_first": {
                            "type": "boolean",
                            "default": True,
                            "description": "Whether to confirm with user first"
                        }
                    },
                    "required": ["action_type", "params"]
                }
            )
        ]

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        state: AgentState
    ) -> tuple[Any, AgentState]:
        """Execute orchestrator tools."""

        if tool_name == "retrieve_context":
            # Call context service
            results = await self.context_service.retrieve(
                user_id=state.user_id,
                query=arguments["query"],
                sources=arguments.get("sources"),
                time_filter=arguments.get("time_filter"),
                entity_filter=arguments.get("entity_filter"),
                limit=arguments.get("limit", 10)
            )

            # Add to state context
            state.context.extend(results['items'])

            return {
                "found": len(results['items']),
                "items": [
                    {
                        "id": item['id'],
                        "source": item['source'],
                        "type": item['content_type'],
                        "title": item['title'],
                        "summary": item.get('summary', item.get('content', '')[:200]),
                        "relevance": item['relevance_score'],
                        "date": item['source_created_at']
                    }
                    for item in results['items']
                ],
                "entities_found": results.get('entities', [])
            }, state

        elif tool_name == "delegate_to_specialist":
            specialist_name = arguments["specialist"]
            specialist = self.specialists.get(specialist_name)

            if not specialist:
                return {"error": f"Unknown specialist: {specialist_name}"}, state

            # Get context items to pass
            context_ids = arguments.get("context_ids", [])
            context_items = [
                item for item in state.context
                if item['id'] in context_ids
            ] if context_ids else state.context

            # Build task with context
            task_with_context = f"""Task: {arguments['task']}

Available Context:
{self._format_context(context_items)}
"""

            # Run specialist
            specialist_state = AgentState(
                user_id=state.user_id,
                session_id=state.session_id,
                messages=[],
                context=context_items,
                pending_actions=[],
                completed_actions=[]
            )

            result_state = await specialist.run(task_with_context, specialist_state)

            # Merge results
            state.pending_actions.extend(result_state.pending_actions)

            return {
                "specialist": specialist_name,
                "result": result_state.final_response,
                "pending_actions": result_state.pending_actions
            }, state

        elif tool_name == "ask_user":
            state.needs_clarification = True
            state.clarification_question = {
                "question": arguments["question"],
                "options": arguments.get("options"),
                "required_for": arguments.get("required_for")
            }
            return {"status": "awaiting_user_response"}, state

        elif tool_name == "execute_action":
            action_type = arguments["action_type"]
            params = arguments["params"]
            confirm_first = arguments.get("confirm_first", True)

            if confirm_first:
                # Add to pending, don't execute yet
                action = {
                    "type": action_type,
                    "params": params,
                    "status": "pending_confirmation"
                }
                state.pending_actions.append(action)
                return {
                    "status": "pending_confirmation",
                    "action": action
                }, state
            else:
                # Execute immediately
                result = await self.action_executor.execute(
                    user_id=state.user_id,
                    action_type=action_type,
                    params=params
                )
                state.completed_actions.append({
                    "type": action_type,
                    "params": params,
                    "result": result
                })
                return {"status": "executed", "result": result}, state

        return {"error": f"Unknown tool: {tool_name}"}, state

    def _format_context(self, items: list[dict]) -> str:
        """Format context items for prompt."""
        formatted = []
        for item in items[:10]:  # Limit context
            formatted.append(f"""
[{item['source'].upper()}] {item.get('title', 'Untitled')}
Type: {item.get('content_type', 'unknown')}
Date: {item.get('source_created_at', 'unknown')}
Content: {item.get('summary', item.get('content', ''))[:500]}
---""")
        return "\n".join(formatted)
```

### 5.3 Task Agent (Specialist)

```python
# agents/task_agent.py

class TaskAgent(BaseAgent):
    """Specialist agent for Jira task operations."""

    @property
    def system_prompt(self) -> str:
        return """You are a Jira task specialist.

Your capabilities:
- Extract tasks from documents, emails, or conversations
- Create well-structured Jira tasks with proper fields
- Find related existing tasks
- Update task status

When creating tasks:
- Write clear, actionable summaries
- Add detailed descriptions with context
- Set appropriate priority based on urgency keywords
- Suggest labels and components if mentioned

Output tasks in this format:
{
  "tasks": [
    {
      "summary": "Clear task title",
      "description": "Detailed description with context",
      "type": "task|bug|story|epic",
      "priority": "high|medium|low",
      "labels": [],
      "estimated_hours": null
    }
  ]
}"""

    @property
    def tools(self) -> list[Tool]:
        return [
            Tool(
                name="extract_tasks",
                description="Extract actionable tasks from context",
                parameters={
                    "type": "object",
                    "properties": {
                        "source_text": {
                            "type": "string",
                            "description": "Text to extract tasks from"
                        },
                        "project_key": {
                            "type": "string",
                            "description": "Jira project key"
                        }
                    },
                    "required": ["source_text"]
                }
            ),
            Tool(
                name="find_related_tasks",
                description="Find existing tasks related to a topic",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "project_key": {"type": "string"}
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="prepare_task_creation",
                description="Prepare task(s) for creation",
                parameters={
                    "type": "object",
                    "properties": {
                        "tasks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "summary": {"type": "string"},
                                    "description": {"type": "string"},
                                    "type": {"type": "string"},
                                    "priority": {"type": "string"},
                                    "labels": {"type": "array", "items": {"type": "string"}}
                                },
                                "required": ["summary", "description", "type"]
                            }
                        },
                        "project_key": {"type": "string"}
                    },
                    "required": ["tasks", "project_key"]
                }
            )
        ]

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        state: AgentState
    ) -> tuple[Any, AgentState]:

        if tool_name == "extract_tasks":
            # Use LLM to extract tasks
            extraction_prompt = f"""Extract actionable tasks from this text.
Return as JSON array with summary, description, type, priority.

Text:
{arguments['source_text'][:5000]}
"""
            response = await self.openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": extraction_prompt}],
                response_format={"type": "json_object"}
            )

            tasks = json.loads(response.choices[0].message.content)
            return {"extracted_tasks": tasks}, state

        elif tool_name == "prepare_task_creation":
            # Add to pending actions
            for task in arguments["tasks"]:
                state.pending_actions.append({
                    "type": "create_jira_task",
                    "params": {
                        "project_key": arguments["project_key"],
                        **task
                    },
                    "status": "pending_confirmation"
                })

            return {
                "prepared": len(arguments["tasks"]),
                "tasks": arguments["tasks"]
            }, state

        return {"error": f"Unknown tool: {tool_name}"}, state
```

---

## 6. Action Executor

### 6.1 Implementation

```python
# action_executor.py

from typing import Any
import httpx

class ActionExecutor:
    """
    Executes final actions by calling external APIs.
    This is the ONLY place that modifies external systems.
    """

    def __init__(
        self,
        external_api_base: str,
        external_api_key: str
    ):
        self.client = httpx.AsyncClient(
            base_url=external_api_base,
            headers={"Authorization": f"Bearer {external_api_key}"}
        )

    async def execute(
        self,
        user_id: str,
        action_type: str,
        params: dict
    ) -> dict:
        """Execute an action and return result."""

        if action_type == "create_jira_task":
            return await self._create_jira_task(user_id, params)

        elif action_type == "update_jira_task":
            return await self._update_jira_task(user_id, params)

        elif action_type == "send_email":
            return await self._send_email(user_id, params)

        elif action_type == "create_calendar_event":
            return await self._create_calendar_event(user_id, params)

        elif action_type == "create_document":
            return await self._create_document(user_id, params)

        else:
            raise ValueError(f"Unknown action type: {action_type}")

    async def _create_jira_task(self, user_id: str, params: dict) -> dict:
        """Create Jira task via external API."""

        # Validate required fields
        required = ["project_key", "summary", "type"]
        missing = [f for f in required if f not in params]
        if missing:
            return {
                "success": False,
                "error": f"Missing required fields: {missing}"
            }

        response = await self.client.post(
            f"/users/{user_id}/jira/issues",
            json={
                "project_key": params["project_key"],
                "type": params["type"],
                "summary": params["summary"],
                "description": params.get("description", ""),
                "priority": params.get("priority", "medium"),
                "labels": params.get("labels", []),
                "assignee": params.get("assignee")
            }
        )

        if response.status_code == 201:
            data = response.json()
            return {
                "success": True,
                "task_key": data["key"],
                "task_url": data["url"]
            }
        else:
            return {
                "success": False,
                "error": response.text
            }

    async def _send_email(self, user_id: str, params: dict) -> dict:
        """Send email via external API."""

        required = ["to", "subject", "body"]
        missing = [f for f in required if f not in params]
        if missing:
            return {
                "success": False,
                "error": f"Missing required fields: {missing}"
            }

        response = await self.client.post(
            f"/users/{user_id}/emails/send",
            json={
                "to": params["to"],
                "cc": params.get("cc", []),
                "subject": params["subject"],
                "body": params["body"],
                "reply_to_id": params.get("reply_to_id")  # For threading
            }
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "message_id": data["message_id"]
            }
        else:
            return {
                "success": False,
                "error": response.text
            }

    async def _create_calendar_event(self, user_id: str, params: dict) -> dict:
        """Create calendar event."""

        required = ["title", "start", "end"]
        missing = [f for f in required if f not in params]
        if missing:
            return {
                "success": False,
                "error": f"Missing required fields: {missing}"
            }

        response = await self.client.post(
            f"/users/{user_id}/calendar/events",
            json={
                "title": params["title"],
                "description": params.get("description", ""),
                "start": params["start"],
                "end": params["end"],
                "attendees": params.get("attendees", []),
                "location": params.get("location"),
                "create_meet_link": params.get("create_meet_link", False)
            }
        )

        if response.status_code == 201:
            data = response.json()
            return {
                "success": True,
                "event_id": data["id"],
                "event_url": data["url"],
                "meet_link": data.get("meet_link")
            }
        else:
            return {
                "success": False,
                "error": response.text
            }
```

---

## 7. Complete Request Flow

### 7.1 Chat Endpoint

```python
# main.py

from fastapi import APIRouter, Depends
from agents.orchestrator import OrchestratorAgent
from context_service import ContextService
from action_executor import ActionExecutor

router = APIRouter(prefix="/api/v1")


class ChatRequest(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    message: str
    confirm_actions: Optional[list[str]] = None  # IDs of actions to confirm


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    response: str
    context_used: list[dict]
    pending_actions: list[dict]  # Actions waiting confirmation
    completed_actions: list[dict]  # Actions that were executed
    needs_clarification: bool
    clarification: Optional[dict]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    orchestrator: OrchestratorAgent = Depends(get_orchestrator),
    session_store = Depends(get_session_store)
):
    """
    Main chat endpoint with intelligent context retrieval.
    """

    # Get or create session
    session_id = request.session_id or str(uuid.uuid4())
    session = await session_store.get_or_create(session_id, request.user_id)

    # Build initial state
    state = AgentState(
        user_id=request.user_id,
        session_id=session_id,
        messages=session.get('messages', []),
        context=session.get('context', []),
        pending_actions=session.get('pending_actions', []),
        completed_actions=[]
    )

    # Handle action confirmations if provided
    if request.confirm_actions:
        for action_id in request.confirm_actions:
            action = next(
                (a for a in state.pending_actions if a.get('id') == action_id),
                None
            )
            if action:
                result = await orchestrator.action_executor.execute(
                    request.user_id,
                    action['type'],
                    action['params']
                )
                state.completed_actions.append({**action, "result": result})
                state.pending_actions.remove(action)

    # Run orchestrator
    result_state = await orchestrator.run(request.message, state)

    # Save session
    await session_store.save(session_id, {
        'messages': result_state.messages,
        'context': result_state.context,
        'pending_actions': result_state.pending_actions
    })

    # Generate message ID
    message_id = str(uuid.uuid4())

    return ChatResponse(
        session_id=session_id,
        message_id=message_id,
        response=result_state.final_response or "",
        context_used=[
            {
                "id": item['id'],
                "source": item['source'],
                "title": item.get('title'),
                "relevance": item.get('relevance_score')
            }
            for item in result_state.context[:5]
        ],
        pending_actions=[
            {
                "id": str(uuid.uuid4()),
                "type": action['type'],
                "description": _describe_action(action),
                "params": action['params']
            }
            for action in result_state.pending_actions
        ],
        completed_actions=result_state.completed_actions,
        needs_clarification=result_state.needs_clarification,
        clarification=result_state.clarification_question
    )


def _describe_action(action: dict) -> str:
    """Human-readable action description."""
    action_type = action['type']
    params = action['params']

    if action_type == "create_jira_task":
        return f"Create Jira task: {params.get('summary', 'Untitled')}"
    elif action_type == "send_email":
        return f"Send email to {params.get('to', 'unknown')}: {params.get('subject', 'No subject')}"
    elif action_type == "create_calendar_event":
        return f"Create event: {params.get('title', 'Untitled')}"
    else:
        return f"Execute {action_type}"
```

### 7.2 Clarification Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLARIFICATION FLOW                            │
└─────────────────────────────────────────────────────────────────┘

User: "Create tasks from John's email"
                │
                ▼
┌─────────────────────────────────────────┐
│ Orchestrator retrieves context          │
│ Finds 3 emails from "John"              │
└─────────────────────────────────────────┘
                │
                ▼
┌─────────────────────────────────────────┐
│ Orchestrator needs clarification:       │
│ "Which John? I found emails from:"      │
│ 1. John Smith (john@company.com)        │
│ 2. John Doe (johnd@client.com)          │
└─────────────────────────────────────────┘
                │
                ▼
Response to User:
{
  "response": "I found emails from multiple Johns. Which one did you mean?",
  "needs_clarification": true,
  "clarification": {
    "question": "Which John did you mean?",
    "options": [
      "John Smith (john@company.com) - 5 recent emails",
      "John Doe (johnd@client.com) - 2 recent emails"
    ],
    "required_for": "identify correct email thread"
  }
}
                │
                ▼
User responds: "John Smith"
                │
                ▼
┌─────────────────────────────────────────┐
│ Orchestrator continues with context     │
│ Retrieves John Smith's emails           │
│ Extracts tasks                          │
│ Prepares for confirmation               │
└─────────────────────────────────────────┘
                │
                ▼
Response to User:
{
  "response": "I found John Smith's proposal email. I've extracted 3 tasks:",
  "pending_actions": [
    {"id": "act_1", "type": "create_jira_task", "description": "Create: Setup CI/CD"},
    {"id": "act_2", "type": "create_jira_task", "description": "Create: User Auth"},
    {"id": "act_3", "type": "create_jira_task", "description": "Create: Payment Integration"}
  ]
}
                │
                ▼
User confirms: confirm_actions: ["act_1", "act_2", "act_3"]
                │
                ▼
┌─────────────────────────────────────────┐
│ Action Executor creates all 3 tasks     │
│ Returns task keys and URLs              │
└─────────────────────────────────────────┘
                │
                ▼
Final Response:
{
  "response": "Done! Created 3 tasks in Jira:\n- PROJ-101: Setup CI/CD\n- PROJ-102: User Auth\n- PROJ-103: Payment Integration",
  "completed_actions": [
    {"type": "create_jira_task", "result": {"task_key": "PROJ-101", "url": "..."}},
    ...
  ]
}
```

---

## 8. Summary: Key Decisions

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| **DB Integration** | REST API contract | Clean separation, schema independence |
| **NOT NL2SQL** | ❌ Rejected | Security, coupling, performance risks |
| **Sync Strategy** | Webhooks + batch | Real-time for new, batch for initial |
| **Embedding Update** | Content-hash check | Only re-embed if content changed |
| **Agent Framework** | Custom + OpenAI SDK | Full control, lightweight, native function calling |
| **Orchestration** | Single orchestrator + specialists | Clear responsibilities, reusable |
| **Action Execution** | Separate executor | Single point of external mutation |
| **Clarification** | Explicit loop | Never guess, always confirm |

---

*Document Version: 1.0*
*Companion to: TECHNICAL_SPECIFICATION.md*

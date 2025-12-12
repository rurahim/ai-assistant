# AI Assistant - Intelligent Context System
## Technical Specification v1.0

---

## 1. Overview

### Purpose
Build an intelligent agent system that retrieves relevant context from multiple integrated sources (Gmail, GDrive, Calendar, MS Outlook/OneDrive, Jira) to accomplish complex tasks.

### Key Principle
**Frontend/Backend team manages integrations and raw data storage. This system reads from their DB and creates/manages embeddings for intelligent context retrieval.**

### Sync Configuration
| Source | Sync Period | Strategy |
|--------|-------------|----------|
| Gmail | 1 month | Hybrid (metadata + summary embeddings) |
| Google Drive | 6 months | Full embed with chunking |
| Google Calendar | 1 month | Real-time fetch + light index |
| MS Outlook | 1 month | Hybrid (same as Gmail) |
| MS OneDrive | 6 months | Full embed with chunking |
| Jira | 3 months | Full embed (title + description) |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT REQUEST                               │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR AGENT                              │
│  • Parse intent  • Plan execution  • Coordinate specialists          │
└─────────────────────────────────────────────────────────────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
             ┌───────────┐  ┌───────────┐  ┌───────────┐
             │  Email    │  │ Document  │  │   Task    │
             │  Agent    │  │   Agent   │  │   Agent   │
             └───────────┘  └───────────┘  └───────────┘
                    │              │              │
                    └──────────────┼──────────────┘
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    UNIFIED CONTEXT MANAGER                           │
│  • Query embeddings  • Retrieve context  • Rank relevance            │
└─────────────────────────────────────────────────────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  WORKING MEMORY  │    │  SEMANTIC MEMORY │    │  EPISODIC MEMORY │
│     (Redis)      │    │    (pgvector)    │    │   (PostgreSQL)   │
│ • Current session│    │ • Embeddings     │    │ • Past events    │
│ • Active context │    │ • Similarity     │    │ • Interactions   │
└──────────────────┘    └──────────────────┘    └──────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL DATA SOURCES                             │
│      (Read-only from Frontend/Backend team's database)               │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │  Gmail  │ │ GDrive  │ │Calendar │ │   MS    │ │  Jira   │       │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Memory Hierarchy

### 3.1 Working Memory (Redis)
**Purpose**: Current session context, fast access
**TTL**: Session duration + 30 minutes

```python
# Redis Key Structure
working:{user_id}:{session_id}:context     # Current context
working:{user_id}:{session_id}:entities    # Active entities
working:{user_id}:preferences              # Cached preferences (TTL: 1 hour)
working:{user_id}:recent_items             # Recently accessed (TTL: 15 min)
```

### 3.2 Episodic Memory (PostgreSQL)
**Purpose**: Past interactions, events, user actions
**Retention**: 6 months

Stores:
- Chat history with AI responses
- User actions (created tasks, sent emails, edited docs)
- Feedback on AI suggestions
- Session summaries

### 3.3 Semantic Memory (PostgreSQL + pgvector)
**Purpose**: Embeddings for similarity search
**Model**: `text-embedding-3-small` (1536 dimensions)

Stores:
- Document chunks with embeddings
- Email summaries with embeddings
- Task embeddings
- Entity embeddings (people, projects, topics)

### 3.4 Temporal Memory (PostgreSQL)
**Purpose**: Time-based patterns and deadlines
**Use Case**: "What did I discuss last week?", deadline awareness

Indexes:
- Timestamps on all items
- Recurring patterns
- Deadline/due date extraction

### 3.5 Procedural Memory (PostgreSQL)
**Purpose**: Learned user preferences and patterns
**Updates**: After each interaction with feedback

Stores:
- Tone preferences per context
- Common recipients
- Preferred response length
- Working hours patterns

---

## 4. Database Schema

### 4.1 Core Tables

```sql
-- Users (links to frontend/backend auth system)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_user_id VARCHAR(255) UNIQUE NOT NULL,  -- From frontend auth
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Integration sync status
CREATE TABLE integration_sync (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,  -- gmail, gdrive, calendar, outlook, onedrive, jira
    last_sync_at TIMESTAMPTZ,
    sync_cursor VARCHAR(500),  -- For incremental sync
    items_synced INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, syncing, completed, failed
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, source_type)
);

-- Knowledge items (unified content storage)
CREATE TABLE knowledge_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,
    source_id VARCHAR(255) NOT NULL,  -- Original ID from source system
    content_type VARCHAR(50) NOT NULL,  -- email, document, task, event, etc.

    -- Content
    title VARCHAR(500),
    summary TEXT,  -- AI-generated summary for emails/long docs
    content TEXT,  -- Full content or chunk

    -- Metadata
    metadata JSONB DEFAULT '{}',
    /*
      Email: {from, to, cc, thread_id, labels, is_reply}
      Document: {mime_type, folder_id, chunk_index, total_chunks}
      Task: {project_key, status, assignee, priority}
      Event: {attendees, location, recurrence}
    */

    -- Timestamps
    source_created_at TIMESTAMPTZ,
    source_updated_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ DEFAULT NOW(),

    -- Indexing
    UNIQUE(user_id, source_type, source_id),
    INDEX idx_knowledge_user_source (user_id, source_type),
    INDEX idx_knowledge_created (user_id, source_created_at DESC)
);

-- Embeddings (pgvector)
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_item_id UUID REFERENCES knowledge_items(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    embedding vector(1536) NOT NULL,
    embedding_model VARCHAR(50) DEFAULT 'text-embedding-3-small',

    -- For chunked documents
    chunk_index INTEGER DEFAULT 0,
    chunk_text TEXT,  -- The text that was embedded

    created_at TIMESTAMPTZ DEFAULT NOW(),

    INDEX idx_embedding_user (user_id)
);

-- Create HNSW index for fast similarity search
CREATE INDEX idx_embedding_vector ON embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Entities (people, projects, topics)
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    entity_type VARCHAR(50) NOT NULL,  -- person, project, topic, company
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255),  -- Lowercase, trimmed for matching

    metadata JSONB DEFAULT '{}',
    /*
      Person: {emails: [], job_title, company, relationship}
      Project: {key, source, status}
      Topic: {keywords: [], frequency}
    */

    mention_count INTEGER DEFAULT 1,
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, entity_type, normalized_name)
);

-- Entity mentions (links entities to knowledge items)
CREATE TABLE entity_mentions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID REFERENCES entities(id) ON DELETE CASCADE,
    knowledge_item_id UUID REFERENCES knowledge_items(id) ON DELETE CASCADE,
    mention_context TEXT,  -- Surrounding text
    created_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(entity_id, knowledge_item_id)
);

-- Chat sessions
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_type VARCHAR(50),  -- email, document, task, general
    title VARCHAR(255),
    context_summary TEXT,

    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat messages
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES chat_sessions(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    role VARCHAR(20) NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,

    -- Context used for this message
    context_items JSONB DEFAULT '[]',  -- [{knowledge_item_id, relevance_score}]

    -- For assistant messages
    tokens_used INTEGER,
    model_used VARCHAR(50),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- User preferences (procedural memory)
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,

    preference_type VARCHAR(50) NOT NULL,
    preference_key VARCHAR(100) NOT NULL,
    preference_value JSONB NOT NULL,

    confidence FLOAT DEFAULT 0.5,  -- Increases with consistent usage
    sample_count INTEGER DEFAULT 1,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(user_id, preference_type, preference_key)
);

-- User feedback
CREATE TABLE user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    message_id UUID REFERENCES chat_messages(id),
    knowledge_item_id UUID REFERENCES knowledge_items(id),

    feedback_type VARCHAR(50) NOT NULL,  -- rating, edit, accept, reject
    feedback_value JSONB NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 4.2 Indexes for Performance

```sql
-- Full-text search on content
CREATE INDEX idx_knowledge_fts ON knowledge_items
    USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(content, '')));

-- Time-based queries
CREATE INDEX idx_knowledge_time ON knowledge_items (user_id, source_created_at DESC);
CREATE INDEX idx_messages_time ON chat_messages (session_id, created_at);

-- Entity lookups
CREATE INDEX idx_entity_name ON entities (user_id, normalized_name);
CREATE INDEX idx_entity_type ON entities (user_id, entity_type);
```

---

## 5. API Endpoints

### 5.1 Sync Management

#### POST `/api/v1/sync/initial`
Trigger initial sync for a user (first-time setup).

**Request:**
```json
{
    "user_id": "usr_123",
    "sources": ["gmail", "gdrive", "calendar", "outlook", "jira"],
    "options": {
        "gmail_days": 30,
        "document_months": 6,
        "calendar_days": 30,
        "jira_months": 3
    }
}
```

**Response:**
```json
{
    "sync_id": "sync_abc123",
    "status": "started",
    "sources": [
        {"source": "gmail", "status": "syncing", "estimated_items": 500},
        {"source": "gdrive", "status": "queued", "estimated_items": 150}
    ]
}
```

#### GET `/api/v1/sync/status/{user_id}`
Get sync status for all sources.

**Response:**
```json
{
    "user_id": "usr_123",
    "sources": [
        {
            "source": "gmail",
            "status": "completed",
            "items_synced": 487,
            "last_sync": "2024-01-15T10:30:00Z"
        },
        {
            "source": "gdrive",
            "status": "syncing",
            "progress": 65,
            "items_synced": 98
        }
    ]
}
```

#### POST `/api/v1/sync/incremental`
Trigger incremental sync (new/changed items).

**Request:**
```json
{
    "user_id": "usr_123",
    "sources": ["gmail", "jira"]  // Optional, defaults to all
}
```

---

### 5.2 Context & Chat

#### POST `/api/v1/chat`
Main chat endpoint with intelligent context retrieval.

**Request:**
```json
{
    "user_id": "usr_123",
    "session_id": "sess_456",  // Optional, creates new if omitted
    "message": "Create Jira tasks from the proposal John sent last week",
    "options": {
        "max_context_items": 10,
        "include_sources": ["gmail", "gdrive", "jira"]
    }
}
```

**Response:**
```json
{
    "session_id": "sess_456",
    "message_id": "msg_789",
    "response": "I found John's proposal email from January 10th with the attached project plan. I've identified 5 potential Jira tasks:\n\n1. **Setup CI/CD Pipeline** - Epic\n2. ...",
    "context_used": [
        {
            "id": "ki_001",
            "source": "gmail",
            "title": "Re: Q1 Project Proposal",
            "relevance": 0.94,
            "snippet": "Hi, please find attached the project plan..."
        },
        {
            "id": "ki_002",
            "source": "gdrive",
            "title": "Q1_Project_Plan.docx",
            "relevance": 0.89
        }
    ],
    "suggested_actions": [
        {
            "action": "create_jira_tasks",
            "label": "Create these 5 tasks in Jira",
            "payload": { "tasks": [...] }
        }
    ]
}
```

#### POST `/api/v1/context/retrieve`
Retrieve relevant context without chat (for custom integrations).

**Request:**
```json
{
    "user_id": "usr_123",
    "query": "project proposal from John",
    "filters": {
        "sources": ["gmail", "gdrive"],
        "date_from": "2024-01-01",
        "date_to": "2024-01-15"
    },
    "limit": 10
}
```

**Response:**
```json
{
    "items": [
        {
            "id": "ki_001",
            "source": "gmail",
            "content_type": "email",
            "title": "Re: Q1 Project Proposal",
            "summary": "John sent project proposal with 5 milestones...",
            "relevance_score": 0.94,
            "metadata": {
                "from": "john@company.com",
                "date": "2024-01-10T14:30:00Z",
                "thread_id": "thread_xyz"
            }
        }
    ],
    "entities_found": [
        {"type": "person", "name": "John Smith", "email": "john@company.com"}
    ]
}
```

---

### 5.3 Entity Management

#### GET `/api/v1/entities/{user_id}`
List all entities for a user.

**Query Params:** `type`, `limit`, `offset`

**Response:**
```json
{
    "entities": [
        {
            "id": "ent_001",
            "type": "person",
            "name": "John Smith",
            "metadata": {
                "emails": ["john@company.com"],
                "company": "Acme Inc",
                "relationship": "client"
            },
            "mention_count": 47,
            "last_seen": "2024-01-15T10:00:00Z"
        }
    ],
    "total": 156
}
```

#### GET `/api/v1/entities/{user_id}/{entity_id}/context`
Get all context related to an entity.

**Response:**
```json
{
    "entity": {
        "id": "ent_001",
        "name": "John Smith"
    },
    "related_items": [
        {
            "source": "gmail",
            "count": 23,
            "recent": [...]
        },
        {
            "source": "jira",
            "count": 8,
            "recent": [...]
        }
    ]
}
```

---

### 5.4 Preferences

#### GET `/api/v1/preferences/{user_id}`
Get learned user preferences.

**Response:**
```json
{
    "preferences": {
        "email_tone": {
            "value": "professional",
            "confidence": 0.85
        },
        "response_length": {
            "value": "medium",
            "confidence": 0.72
        },
        "working_hours": {
            "value": {"start": "09:00", "end": "18:00", "timezone": "UTC"},
            "confidence": 0.90
        },
        "frequent_recipients": [
            {"email": "john@company.com", "count": 47},
            {"email": "team@company.com", "count": 32}
        ]
    }
}
```

#### PUT `/api/v1/preferences/{user_id}`
Manually update preferences.

**Request:**
```json
{
    "email_tone": "casual",
    "response_length": "short"
}
```

---

### 5.5 Webhooks (Real-time Sync)

#### POST `/api/v1/webhooks/item-created`
Called by frontend/backend when new item is created.

**Request:**
```json
{
    "user_id": "usr_123",
    "source": "gmail",
    "source_id": "msg_new123",
    "content_type": "email",
    "data": {
        "subject": "New meeting request",
        "from": "client@example.com",
        "body": "...",
        "date": "2024-01-15T11:00:00Z"
    }
}
```

#### POST `/api/v1/webhooks/item-updated`
Called when existing item is modified.

**Request:**
```json
{
    "user_id": "usr_123",
    "source": "jira",
    "source_id": "PROJ-123",
    "changes": {
        "status": {"from": "To Do", "to": "In Progress"},
        "assignee": {"from": null, "to": "john@company.com"}
    }
}
```

#### POST `/api/v1/webhooks/item-deleted`
Called when item is deleted.

---

## 6. Context Retrieval Algorithm

### 6.1 Flow

```
User Query
    │
    ▼
┌─────────────────────────────┐
│ 1. QUERY ANALYSIS           │
│ • Extract intent            │
│ • Identify entities         │
│ • Detect time references    │
│ • Determine source hints    │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 2. PARALLEL RETRIEVAL       │
│ • Semantic search (embed)   │
│ • Entity lookup             │
│ • Time-based filter         │
│ • Full-text search          │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 3. ENTITY EXPANSION         │
│ • Find related entities     │
│ • Get entity's items        │
│ • Cross-reference threads   │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 4. RELEVANCE SCORING        │
│ • Semantic similarity       │
│ • Recency boost             │
│ • Entity match bonus        │
│ • Source priority           │
└─────────────────────────────┘
    │
    ▼
┌─────────────────────────────┐
│ 5. CONTEXT ASSEMBLY         │
│ • Rank by score             │
│ • Deduplicate               │
│ • Fit token budget          │
│ • Format for LLM            │
└─────────────────────────────┘
```

### 6.2 Scoring Formula

```python
def calculate_relevance(item, query_embedding, query_entities, query_time):
    # Base semantic similarity (0-1)
    semantic_score = cosine_similarity(item.embedding, query_embedding)

    # Recency boost (0-0.2)
    days_old = (now - item.source_created_at).days
    recency_score = max(0, 0.2 - (days_old / 365) * 0.2)

    # Entity match bonus (0-0.3)
    entity_matches = len(set(item.entities) & set(query_entities))
    entity_score = min(0.3, entity_matches * 0.1)

    # Source priority (0-0.1)
    source_priority = {
        'gmail': 0.1,      # Usually most relevant for tasks
        'gdrive': 0.08,
        'jira': 0.07,
        'calendar': 0.05,
    }
    source_score = source_priority.get(item.source, 0.05)

    # Final score
    return semantic_score * 0.5 + recency_score + entity_score + source_score
```

---

## 7. User Journeys

### 7.1 First-Time User Setup

```
┌──────────────────────────────────────────────────────────────────┐
│ JOURNEY: First-Time User Onboarding                              │
└──────────────────────────────────────────────────────────────────┘

User Action                          System Response
─────────────────────────────────────────────────────────────────────
1. User logs in for first time   →   Frontend authenticates user
                                      Backend creates user record

2. User connects Gmail           →   Frontend handles OAuth
                                      Backend stores tokens
                                      Calls POST /api/v1/sync/initial

3. System starts sync            →   Background job reads emails (30 days)
                                      Creates embeddings for each email
                                      Extracts entities (people, topics)
                                      Progress shown via GET /sync/status

4. User connects GDrive          →   Same flow, syncs 6 months of docs
                                      Documents chunked and embedded

5. All syncs complete            →   User notified "Ready to use"
                                      Context engine fully populated

6. User sends first message:     →   POST /api/v1/chat
   "What did John email about?"      Finds all emails from/about John
                                      Returns summary with sources
```

### 7.2 Complex Task: Email → Jira → Document

```
┌──────────────────────────────────────────────────────────────────┐
│ JOURNEY: Create Jira Tasks from Email with GDrive Context        │
└──────────────────────────────────────────────────────────────────┘

User: "Create Jira tasks from the proposal John sent last week"

─────────────────────────────────────────────────────────────────────
STEP 1: Query Analysis
─────────────────────────────────────────────────────────────────────
• Intent: create_jira_tasks
• Entities: John (person)
• Time: last week (7 days)
• Source hint: email (proposal sent)
• Related: gdrive (proposal document)

─────────────────────────────────────────────────────────────────────
STEP 2: Context Retrieval
─────────────────────────────────────────────────────────────────────
Parallel queries:

  a) Semantic search:
     Query: "proposal from John"
     Results: 3 emails, 2 documents

  b) Entity lookup:
     Entity: John Smith (john@company.com)
     Recent items: 5 emails, 1 Jira task

  c) Time filter:
     Range: last 7 days
     Matches: 2 emails, 1 document

─────────────────────────────────────────────────────────────────────
STEP 3: Entity Expansion
─────────────────────────────────────────────────────────────────────
From John's emails, found:
  • Thread: "Q1 Project Proposal" (3 messages)
  • Attachment reference: "Q1_Project_Plan.docx"
  • Related project: "PROJ" (Jira)

Cross-reference:
  • Found Q1_Project_Plan.docx in GDrive
  • Found existing PROJ Jira project

─────────────────────────────────────────────────────────────────────
STEP 4: Relevance Scoring
─────────────────────────────────────────────────────────────────────
Ranked results:
  1. Email "Re: Q1 Project Proposal" (0.94) - has attachment ref
  2. GDrive "Q1_Project_Plan.docx" (0.89) - the actual proposal
  3. Email "Q1 Project Proposal" (0.82) - original thread start
  4. Jira "PROJ-100: Q1 Planning" (0.71) - related existing task

─────────────────────────────────────────────────────────────────────
STEP 5: Context Assembly
─────────────────────────────────────────────────────────────────────
Context for LLM:

  [Email Thread Summary]
  John sent Q1 Project Proposal on Jan 10. Key points:
  - 5 milestones planned
  - Deadline: March 31
  - Budget: $50,000

  [Document Content - Q1_Project_Plan.docx]
  ## Milestones
  1. Setup CI/CD Pipeline - 2 weeks
  2. User Authentication Module - 3 weeks
  3. Payment Integration - 2 weeks
  4. Testing & QA - 2 weeks
  5. Deployment - 1 week

  [Existing Jira Context]
  Project: PROJ
  Existing tasks: 12 open, 5 completed

─────────────────────────────────────────────────────────────────────
STEP 6: Response Generation
─────────────────────────────────────────────────────────────────────
AI Response:
  "I found John's proposal from January 10th. Based on the
   Q1_Project_Plan.docx, I've identified 5 tasks to create
   in Jira project PROJ:

   1. **PROJ-XXX: Setup CI/CD Pipeline**
      Type: Task | Priority: High | Estimate: 2 weeks

   2. **PROJ-XXX: User Authentication Module**
      Type: Story | Priority: High | Estimate: 3 weeks
      ...

   Should I create these tasks?"

─────────────────────────────────────────────────────────────────────
STEP 7: User Confirms
─────────────────────────────────────────────────────────────────────
User: "Yes, create them"

System:
  • Calls Jira API (via backend) to create 5 tasks
  • Stores interaction in episodic memory
  • Updates entities (John linked to PROJ project)
  • Response: "Created 5 tasks in PROJ. Here are the links..."
```

### 7.3 Calendar-Aware Response

```
┌──────────────────────────────────────────────────────────────────┐
│ JOURNEY: Schedule Meeting with Context                           │
└──────────────────────────────────────────────────────────────────┘

User: "Schedule a follow-up meeting with John about the proposal"

─────────────────────────────────────────────────────────────────────
Context Retrieved:
─────────────────────────────────────────────────────────────────────
• Recent John interactions (last 7 days)
• Proposal document context
• John's typical meeting times (from past calendar)
• User's calendar availability (real-time fetch)
• Previous meeting notes with John

─────────────────────────────────────────────────────────────────────
Response:
─────────────────────────────────────────────────────────────────────
"Based on your previous meetings with John (usually Tuesdays 2pm),
 and your calendar availability, I suggest:

 📅 Tuesday, Jan 23 at 2:00 PM (1 hour)
 📍 Google Meet (John's preference from past meetings)
 📝 Agenda: Q1 Proposal Follow-up
    - Review milestone progress
    - Discuss budget allocation
    - Confirm March 31 deadline

 Should I send the invite?"
```

---

## 8. Embedding Strategy

### 8.1 Per-Source Strategy

| Source | Strategy | Reasoning |
|--------|----------|-----------|
| **Gmail** | Hybrid | Emails vary in importance; embed summary, fetch full on-demand |
| **GDrive** | Full + Chunk | Documents need semantic search; chunk at 500-800 tokens |
| **Calendar** | Light Index | Too dynamic; index metadata, real-time fetch details |
| **Jira** | Full Embed | Tasks are structured; embed title + description |
| **Outlook** | Hybrid | Same as Gmail |
| **OneDrive** | Full + Chunk | Same as GDrive |

### 8.2 Chunking Strategy

```python
def chunk_document(content: str, chunk_size: int = 600, overlap: int = 100):
    """
    Chunk document with overlap for context preservation.
    Target: 500-800 tokens per chunk (roughly 2000-3200 chars)
    """
    chunks = []
    sentences = split_into_sentences(content)

    current_chunk = []
    current_size = 0

    for sentence in sentences:
        sentence_size = len(sentence.split())

        if current_size + sentence_size > chunk_size:
            # Save current chunk
            chunks.append({
                'text': ' '.join(current_chunk),
                'index': len(chunks)
            })

            # Start new chunk with overlap
            overlap_start = max(0, len(current_chunk) - 2)
            current_chunk = current_chunk[overlap_start:]
            current_size = sum(len(s.split()) for s in current_chunk)

        current_chunk.append(sentence)
        current_size += sentence_size

    # Don't forget last chunk
    if current_chunk:
        chunks.append({
            'text': ' '.join(current_chunk),
            'index': len(chunks)
        })

    return chunks
```

### 8.3 Email Summary Generation

```python
async def generate_email_summary(email: dict) -> str:
    """Generate concise summary for embedding."""
    prompt = f"""Summarize this email in 2-3 sentences, capturing:
- Main topic/request
- Key people mentioned
- Any deadlines or action items

From: {email['from']}
Subject: {email['subject']}
Body: {email['body'][:2000]}
"""

    response = await openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150
    )

    return response.choices[0].message.content
```

---

## 9. Real-Time Sync Flow

### 9.1 New Item Flow

```
External System (Gmail/Jira/etc)
         │
         │ (Frontend/Backend webhook)
         ▼
┌─────────────────────────────┐
│ POST /webhooks/item-created │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│ 1. Validate & Parse         │
│ 2. Create knowledge_item    │
│ 3. Extract entities         │
│ 4. Generate embedding       │
│ 5. Update Redis cache       │
│ 6. Emit event (optional)    │
└─────────────────────────────┘
         │
         ▼
   Item available for
   context retrieval
   (< 5 seconds)
```

### 9.2 Item Update Flow

```
┌─────────────────────────────┐
│ POST /webhooks/item-updated │
└─────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ 1. Find existing knowledge_item     │
│ 2. Compare content hash             │
│    - If unchanged: update metadata  │
│    - If changed: regenerate embed   │
│ 3. Update entity mentions           │
│ 4. Invalidate Redis cache           │
└─────────────────────────────────────┘
```

---

## 10. Implementation Phases

### Phase 1: Foundation (Week 1-2)
- [ ] Set up PostgreSQL with pgvector extension
- [ ] Set up Redis
- [ ] Create database schema and migrations
- [ ] Implement basic CRUD for knowledge_items
- [ ] Create embedding generation service
- [ ] Basic API endpoints (sync status, health)

### Phase 2: Sync Engine (Week 3-4)
- [ ] Initial sync for Gmail (read from frontend DB)
- [ ] Initial sync for GDrive
- [ ] Initial sync for Jira
- [ ] Webhook endpoints for real-time updates
- [ ] Background job queue (Celery/RQ)
- [ ] Sync status tracking

### Phase 3: Context Engine (Week 5-6)
- [ ] Semantic search implementation
- [ ] Entity extraction and storage
- [ ] Entity expansion logic
- [ ] Relevance scoring algorithm
- [ ] Context assembly with token budgeting
- [ ] Redis caching for hot data

### Phase 4: Chat Integration (Week 7-8)
- [ ] Chat session management
- [ ] Context-aware response generation
- [ ] Action suggestion system
- [ ] Message history storage
- [ ] Working memory (Redis) integration

### Phase 5: Intelligence Layer (Week 9-10)
- [ ] Preference learning from feedback
- [ ] Temporal pattern detection
- [ ] Cross-source linking (email → doc → task)
- [ ] Proactive suggestions
- [ ] Analytics and usage tracking

### Phase 6: Optimization (Week 11-12)
- [ ] Query performance tuning
- [ ] Embedding index optimization
- [ ] Caching strategy refinement
- [ ] Load testing
- [ ] Documentation and handoff

---

## 11. Tech Stack Summary

| Component | Technology |
|-----------|------------|
| **API Framework** | FastAPI |
| **Database** | PostgreSQL 15+ with pgvector |
| **Cache** | Redis 7+ |
| **Embeddings** | OpenAI text-embedding-3-small |
| **LLM** | GPT-4o / GPT-4o-mini |
| **Task Queue** | Celery with Redis broker |
| **ORM** | SQLAlchemy 2.0 + asyncpg |
| **Migrations** | Alembic |

---

## 12. Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/ai_assistant
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
CHAT_MODEL=gpt-4o-mini

# Sync Settings
GMAIL_SYNC_DAYS=30
DOCUMENT_SYNC_MONTHS=6
CALENDAR_SYNC_DAYS=30
JIRA_SYNC_MONTHS=3

# Performance
MAX_CONTEXT_ITEMS=10
MAX_CONTEXT_TOKENS=4000
EMBEDDING_BATCH_SIZE=100
CACHE_TTL_SECONDS=3600
```

---

## Appendix A: Sample SQL Queries

### Find relevant context

```sql
-- Semantic search with filters
SELECT
    ki.id,
    ki.source_type,
    ki.title,
    ki.summary,
    1 - (e.embedding <=> $1) as similarity
FROM knowledge_items ki
JOIN embeddings e ON e.knowledge_item_id = ki.id
WHERE ki.user_id = $2
  AND ki.source_type = ANY($3)
  AND ki.source_created_at >= $4
ORDER BY e.embedding <=> $1
LIMIT 10;
```

### Get entity context

```sql
-- All items mentioning an entity
SELECT
    ki.*,
    em.mention_context
FROM entity_mentions em
JOIN knowledge_items ki ON ki.id = em.knowledge_item_id
WHERE em.entity_id = $1
ORDER BY ki.source_created_at DESC
LIMIT 20;
```

---

## Appendix B: Error Codes

| Code | Description |
|------|-------------|
| `SYNC_001` | Sync already in progress |
| `SYNC_002` | Source not connected |
| `SYNC_003` | Sync timeout |
| `CTX_001` | No relevant context found |
| `CTX_002` | Token budget exceeded |
| `EMB_001` | Embedding generation failed |
| `ENT_001` | Entity not found |

---

*Document Version: 1.0*
*Last Updated: 2024-01*

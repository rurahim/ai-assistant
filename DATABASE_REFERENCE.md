# AI Employee V2 - Database Reference Guide

> Use this document while chatting with your AI assistant to understand what data is available.

---

## Quick Overview

| Storage | Purpose | Data Types |
|---------|---------|------------|
| **PostgreSQL** | Persistent storage | Users, Knowledge, Embeddings, Entities, Chat, Preferences |
| **Redis** | Working memory & cache | Session context, Cached preferences, Recent items |

**Database URL:** `postgresql://ai_assistant:ai_assistant_secret@localhost:5433/ai_assistant_db`
**Redis URL:** `redis://localhost:6379/0`

---

## Memory Types

| Memory Type | Storage | Description |
|-------------|---------|-------------|
| **Semantic Memory** | `knowledge_items` + `embeddings` | Long-term facts: emails, documents, tasks, events |
| **Episodic Memory** | `chat_sessions` + `chat_messages` | Conversation history |
| **Procedural Memory** | `user_preferences` | Learned user preferences (email tone, working hours, etc.) |
| **Working Memory** | Redis | Short-term session context (30 min TTL) |
| **Entity Memory** | `entities` + `entity_mentions` | People, projects, topics, companies |

---

## Database Tables

### 1. USERS

Stores registered users.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `external_user_id` | String(255) | External auth system ID (unique) |
| `email` | String(255) | User email |
| `name` | String(255) | User full name |
| `preferences` | JSONB | Stored preferences object |
| `created_at` | DateTime | Account creation time |
| `updated_at` | DateTime | Last update time |

**Relationships:**
- Has many: knowledge_items, embeddings, entities, chat_sessions, user_preferences, user_feedback, integration_syncs

---

### 2. KNOWLEDGE_ITEMS

Unified storage for all user content (semantic memory).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID | Foreign key to users |
| `source_type` | String(50) | Source: `gmail`, `gdrive`, `calendar`, `outlook`, `onedrive`, `jira` |
| `source_id` | String(255) | Original ID from source system |
| `content_type` | String(50) | Type: `email`, `document`, `task`, `event` |
| `title` | String(500) | Content title |
| `summary` | Text | AI-generated summary |
| `content` | Text | Full content text |
| `metadata` | JSONB | Source-specific metadata (see below) |
| `source_created_at` | DateTime | Original creation date |
| `source_updated_at` | DateTime | Original update date |
| `synced_at` | DateTime | When synced to DB |

**Metadata by Content Type:**

**Email metadata:**
```json
{
  "from": "sender@email.com",
  "to": ["recipient@email.com"],
  "cc": ["cc@email.com"],
  "thread_id": "thread123",
  "labels": ["inbox", "important"],
  "is_reply": false
}
```

**Document metadata:**
```json
{
  "mime_type": "application/pdf",
  "folder_id": "folder123",
  "chunk_index": 0,
  "total_chunks": 5
}
```

**Task metadata (Jira):**
```json
{
  "project_key": "PROJ",
  "status": "In Progress",
  "assignee": "user@email.com",
  "priority": "High"
}
```

**Event metadata (Calendar):**
```json
{
  "attendees": ["person1@email.com", "person2@email.com"],
  "location": "Conference Room A",
  "recurrence": "WEEKLY"
}
```

---

### 3. EMBEDDINGS

Vector storage for semantic similarity search.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `knowledge_item_id` | UUID | Foreign key to knowledge_items |
| `user_id` | UUID | Foreign key to users |
| `embedding` | Vector(1536) | OpenAI text-embedding-3-small vector |
| `embedding_model` | String(50) | Model name (default: text-embedding-3-small) |
| `chunk_index` | Integer | For chunked documents (default: 0) |
| `chunk_text` | Text | Original text of chunk (max 5000 chars) |
| `created_at` | DateTime | Creation time |

**Index:** HNSW index with cosine distance (m=16, ef_construction=64)

---

### 4. ENTITIES

Extracted entities: people, projects, topics, companies.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID | Foreign key to users |
| `entity_type` | String(50) | Type: `person`, `project`, `topic`, `company` |
| `name` | String(255) | Display name |
| `normalized_name` | String(255) | Lowercase, trimmed for matching |
| `metadata` | JSONB | Type-specific metadata (see below) |
| `mention_count` | Integer | How many times mentioned |
| `last_seen_at` | DateTime | Most recent mention |
| `created_at` | DateTime | First seen |

**Metadata by Entity Type:**

**Person metadata:**
```json
{
  "emails": ["john@company.com"],
  "job_title": "Software Engineer",
  "company": "Acme Corp",
  "relationship": "colleague"
}
```

**Project metadata:**
```json
{
  "key": "PROJ-123",
  "source": "jira",
  "status": "active"
}
```

**Topic metadata:**
```json
{
  "keywords": ["machine learning", "AI", "neural networks"],
  "frequency": 15
}
```

**Company metadata:**
```json
{
  "domain": "acme.com",
  "industry": "Technology"
}
```

---

### 5. ENTITY_MENTIONS

Links entities to knowledge items where they appear.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `entity_id` | UUID | Foreign key to entities |
| `knowledge_item_id` | UUID | Foreign key to knowledge_items |
| `mention_context` | Text | Surrounding text for context |
| `created_at` | DateTime | Creation time |

---

### 6. CHAT_SESSIONS

Stores conversation sessions (episodic memory).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID | Foreign key to users |
| `session_type` | String(50) | Type: `email`, `document`, `task`, `general` |
| `title` | String(255) | User-defined session title |
| `context_summary` | Text | AI summary of session context |
| `metadata` | JSONB | Session-specific data |
| `created_at` | DateTime | Session start time |
| `updated_at` | DateTime | Last activity time |

---

### 7. CHAT_MESSAGES

Individual messages in chat sessions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `session_id` | UUID | Foreign key to chat_sessions |
| `user_id` | UUID | Foreign key to users |
| `role` | String(20) | Role: `user`, `assistant`, `system` |
| `content` | Text | Message content |
| `context_items` | JSONB | Knowledge items used (see below) |
| `tokens_used` | Integer | Tokens used (assistant messages) |
| `model_used` | String(50) | Model name used |
| `pending_actions` | JSONB | Array of pending actions |
| `created_at` | DateTime | Message time |

**context_items format:**
```json
[
  {"knowledge_item_id": "uuid", "relevance_score": 0.95},
  {"knowledge_item_id": "uuid", "relevance_score": 0.87}
]
```

**pending_actions format:**
```json
[
  {
    "action_type": "send_email",
    "status": "pending",
    "data": {"to": "recipient@email.com", "subject": "..."}
  }
]
```

---

### 8. USER_PREFERENCES

Learned user preferences (procedural memory).

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID | Foreign key to users |
| `preference_type` | String(50) | Type category (see below) |
| `preference_key` | String(100) | Specific preference name |
| `preference_value` | JSONB | Preference value |
| `confidence` | Float | Confidence score (0.0 - 1.0) |
| `sample_count` | Integer | Number of observations |
| `created_at` | DateTime | First learned |
| `updated_at` | DateTime | Last updated |

**Common preference_type values:**
- `email_tone` - Formal, casual, friendly
- `response_length` - Brief, detailed, comprehensive
- `working_hours` - Start/end times, timezone
- `interaction` - Message style preferences
- `topic_interest` - Topics user frequently discusses

**Example:**
```json
{
  "preference_type": "email_tone",
  "preference_key": "default_style",
  "preference_value": "professional",
  "confidence": 0.85,
  "sample_count": 12
}
```

---

### 9. USER_FEEDBACK

User feedback on AI responses for learning.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID | Foreign key to users |
| `message_id` | UUID | Foreign key to chat_messages (nullable) |
| `knowledge_item_id` | UUID | Foreign key to knowledge_items (nullable) |
| `feedback_type` | String(50) | Type: `rating`, `edit`, `accept`, `reject` |
| `feedback_value` | JSONB | Feedback data |
| `created_at` | DateTime | Feedback time |

---

### 10. INTEGRATION_SYNCS

Tracks sync status for each data source.

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID | Foreign key to users |
| `source_type` | String(50) | Source: `gmail`, `gdrive`, `calendar`, `outlook`, `onedrive`, `jira` |
| `last_sync_at` | DateTime | Last sync completion time |
| `sync_cursor` | String(500) | Cursor for incremental sync |
| `items_synced` | Integer | Items synced in last run |
| `status` | String(20) | Status: `pending`, `syncing`, `completed`, `failed` |
| `error_message` | Text | Error details if failed |
| `created_at` | DateTime | First sync time |
| `updated_at` | DateTime | Last status update |

---

## Redis Keys

### Working Memory (30 min TTL)
```
working:{user_id}:{session_id}:context
```
Contains: Active entities, recent topics, conversation context

### Cached Preferences (1 hour TTL)
```
prefs:{user_id}
```
Contains: User preferences object

### Recently Accessed Items (15 min TTL)
```
recent:{user_id}:items
```
Contains: List of recently accessed knowledge item IDs

---

## Data Sources

| Source | Content Types | Sync Window |
|--------|--------------|-------------|
| **Gmail** | Emails | Last 30 days |
| **Google Drive** | Documents | Last 6 months |
| **Outlook** | Emails | Last 30 days |
| **OneDrive** | Documents | Last 6 months |
| **Google Calendar** | Events | Last 30 days |
| **Jira** | Tasks/Issues | Last 3 months |

---

## Context Retrieval Strategies

When the AI retrieves context, it uses multiple strategies:

1. **Semantic Search** - Vector similarity on embeddings
2. **Entity-based Search** - Filter by extracted entities
3. **Full-text Search** - PostgreSQL GIN index on content
4. **Keyword Search** - Simple substring matching (fallback)
5. **Temporal Search** - Most recent items
6. **Source Filtering** - By content type (emails, documents, tasks, events)

**Configuration:**
- Max context items: 10
- Max context tokens: 4000
- Embedding dimensions: 1536

---

## API Endpoints Reference

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/chat` | Send message, get AI response |
| GET | `/api/v1/chat/sessions/{user_id}` | List chat sessions |
| GET | `/api/v1/chat/sessions/{user_id}/{session_id}/messages` | Get session messages |

### Sync
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/sync/initial` | Start initial sync |
| GET | `/api/v1/sync/status/{user_id}` | Get sync status |
| POST | `/api/v1/sync/incremental/{user_id}` | Trigger incremental sync |

### Entities
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/entities/{user_id}` | List entities |
| GET | `/api/v1/entities/{user_id}/search/{query}` | Search entities |

### Preferences
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/preferences/{user_id}` | Get all preferences |
| PUT | `/api/v1/preferences/{user_id}` | Update preference |
| GET | `/api/v1/preferences/{user_id}/working-hours` | Get working hours |
| GET | `/api/v1/preferences/{user_id}/email` | Get email preferences |

---

## Quick Reference Queries

**Find user's recent emails:**
```sql
SELECT * FROM knowledge_items
WHERE user_id = 'USER_UUID'
  AND source_type = 'gmail'
ORDER BY source_created_at DESC LIMIT 10;
```

**Find frequently mentioned people:**
```sql
SELECT * FROM entities
WHERE user_id = 'USER_UUID'
  AND entity_type = 'person'
ORDER BY mention_count DESC LIMIT 10;
```

**Get user's learned preferences:**
```sql
SELECT * FROM user_preferences
WHERE user_id = 'USER_UUID'
ORDER BY confidence DESC;
```

**Get recent chat history:**
```sql
SELECT * FROM chat_messages
WHERE session_id = 'SESSION_UUID'
ORDER BY created_at DESC LIMIT 50;
```

---

## Data Flow

```
External Sources (Gmail, Drive, Jira, etc.)
           |
           v
    [SyncService] ──────────────────────────────────────┐
           |                                            |
           v                                            v
    [KnowledgeItem] ──────────────────────> [IntegrationSync]
           |                                   (status tracking)
           |
     ┌─────┴─────┐
     |           |
     v           v
[Embedding]  [Entity] ──> [EntityMention]
(vectors)    (people,      (links to content)
             projects)
     |
     v
[ContextService] <── retrieves relevant context
     |
     v
[Redis Cache] <── working memory
     |
     v
[ChatSession/Message] <── conversation history
     |
     v
[PreferenceService] <── learns from interactions
     |
     v
[UserPreference] <── stored learned preferences
```

---

*Last Updated: December 2024*

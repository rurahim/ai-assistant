# AI Assistant API - Multi-Agent System

A sophisticated multi-agent AI assistant API that provides intelligent responses, performs actions (emails, meetings, tasks, documents), and maintains conversational context across sessions.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Quick Start](#quick-start)
- [API Endpoints](#api-endpoints)
  - [Main Chat Endpoint](#main-chat-endpoint)
  - [Session Management](#session-management)
  - [Action Confirmation](#action-confirmation)
  - [Data Sync Endpoints](#data-sync-endpoints)
  - [Webhook Endpoints](#webhook-endpoints)
  - [Entity Endpoints](#entity-endpoints)
  - [Preferences Endpoints](#preferences-endpoints)
  - [External Data Endpoints](#external-data-endpoints)
  - [Health Endpoints](#health-endpoints)
- [Request/Response Formats](#requestresponse-formats)
- [Agent System](#agent-system)
- [Action Types](#action-types)
- [Session Lifecycle](#session-lifecycle)
- [Flow Examples](#flow-examples)
- [Error Handling](#error-handling)
- [Backend Integration Guide](#backend-integration-guide)
- [Rate Limits](#rate-limits)
- [Environment Variables](#environment-variables)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT REQUEST                                 │
│                POST /api/v1/chat                                            │
│                {user_id, session_id, message, attachments?}                 │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TRIAGE AGENT (LLM)                                │
│  • Classifies intent using lightweight LLM                                  │
│  • Determines: QA / Action / Clarification needed                           │
│  • Routes to specialist agent(s)                                            │
│  • Coordinates multi-agent workflows                                        │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  MEMORY AGENT   │   │  EMAIL AGENT    │   │ CALENDAR AGENT  │
│  (Always first) │   │                 │   │                 │
│                 │   │ • Summarize     │   │ • Create meeting│
│ • RAG retrieval │   │ • Draft reply   │   │ • Find slots    │
│ • Entity lookup │   │ • Action items  │   │ • Check schedule│
│ • Context fetch │   │                 │   │                 │
└────────┬────────┘   └─────────────────┘   └─────────────────┘
         │
         │            ┌─────────────────┐   ┌─────────────────┐
         │            │   JIRA AGENT    │   │ DOCUMENT AGENT  │
         │            │                 │   │                 │
         │            │ • Create task   │   │ • Draft proposal│
         │            │ • Update status │   │ • Generate PDF  │
         │            │ • Sprint info   │   │ • Summarize doc │
         └────────────┴─────────────────┴───┴─────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RESPONSE FORMATTER                                   │
│  • Standardizes JSON output                                                 │
│  • Sets response_type: answer | action | clarification                      │
│  • Attaches action payloads for backend execution                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Memory Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                   WORKING MEMORY (Redis)                        │
│  Current session context, pending actions, recent entities      │
│  TTL: Session duration                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                  EPISODIC MEMORY (PostgreSQL)                   │
│  Chat history, past decisions, user corrections                 │
│  TTL: 30-90 days                                                │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                 SEMANTIC MEMORY (PostgreSQL + pgvector)         │
│  Knowledge items, embeddings, entities, preferences             │
│  TTL: Permanent                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Base URL
```
http://localhost:8000/api/v1
```

### Authentication
All requests require `user_id` in the request body. Session tracking uses `session_id`.

### Minimal Example

```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "55cdf147-9803-490e-b37e-255a4e55a4da",
    "message": "What emails did I receive from Farhan last week?"
  }'
```

---

## API Endpoints

### Main Chat Endpoint

#### `POST /api/v1/chat`

The primary endpoint for all interactions. Handles Q&A, actions, and multi-turn conversations.

**Request:**
```json
{
  "user_id": "string (required)",
  "session_id": "string (optional - auto-generated if not provided)",
  "message": "string (required)",
  "attachments": [
    {
      "type": "email | email_thread | document",
      "content": { },
      "source_id": "string (optional - reference existing item)"
    }
  ],
  "confirm_action": "string (optional - action_id to confirm)"
}
```

**Response:**
```json
{
  "response_type": "answer | action | clarification",
  "message": "string",
  "session_id": "string",
  "action": { },
  "clarifications": [ ],
  "sources": [ ],
  "metadata": { }
}
```

---

### Session Management

#### `GET /api/v1/sessions/{user_id}`

Get all sessions for a user.

```bash
curl "http://localhost:8000/api/v1/sessions/55cdf147-9803-490e-b37e-255a4e55a4da"
```

#### `GET /api/v1/sessions/{user_id}/{session_id}`

Get session details with message history.

#### `DELETE /api/v1/sessions/{user_id}/{session_id}`

Delete a session.

---

### Action Confirmation

#### `POST /api/v1/chat` with `confirm_action`

To confirm a pending action, send the action_id:

```json
{
  "user_id": "55cdf147-...",
  "session_id": "existing-session-id",
  "message": "yes",
  "confirm_action": "act_a1b2c3d4"
}
```

---

### Data Sync Endpoints

#### Initial Setup Flow

Before using the chat endpoint, you need to sync user data. Here's the typical flow:

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. External DB has users from your frontend (OAuth tokens, etc) │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. POST /api/v1/external/sync                                   │
│    Syncs users/accounts from external DB to local               │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. GET /api/v1/sync/users                                       │
│    Lists all users available for sync with their providers      │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. POST /api/v1/sync/all  (bulk) OR                             │
│    POST /api/v1/sync/initial (per-user)                         │
│    Syncs emails, calendar, Jira, etc. into knowledge base       │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. GET /api/v1/sync/status                                      │
│    Monitor sync progress for all users                          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. POST /api/v1/chat                                            │
│    Users can now chat with their data!                          │
└─────────────────────────────────────────────────────────────────┘
```

#### `GET /api/v1/sync/users`

List all users available for sync from the external database.

**Query Parameters:** `limit` (default: 100), `offset` (default: 0)

**Response:**
```json
{
  "users": [
    {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "john@example.com",
      "name": "John Smith",
      "connected_providers": ["google", "jira"]
    }
  ],
  "total": 5,
  "limit": 100,
  "offset": 0
}
```

#### `POST /api/v1/sync/all`

Initiate sync for ALL users at once. Useful for initial setup.

**Request:**
```json
{
  "sources": ["gmail", "gdrive", "jira", "calendar"],
  "config": {
    "gmail_days": 30,
    "document_months": 6,
    "jira_months": 3,
    "calendar_days": 30
  }
}
```

**Response:**
```json
{
  "status": "started",
  "message": "Bulk sync started for 5 users",
  "sources": ["gmail", "gdrive", "jira", "calendar"],
  "users_queued": 5,
  "users": [
    {"user_id": "550e8400-...", "email": "john@example.com"},
    {"user_id": "660f9511-...", "email": "jane@example.com"}
  ]
}
```

#### `GET /api/v1/sync/status`

Get sync status for ALL users (aggregated view).

**Response:**
```json
{
  "summary": {
    "total_users": 5,
    "completed": 3,
    "syncing": 1,
    "failed": 0,
    "not_started": 1
  },
  "users": [
    {
      "user_id": "550e8400-...",
      "email": "john@example.com",
      "overall_status": "completed",
      "sources": {
        "gmail": {"status": "completed", "items_synced": 150, "last_sync_at": "..."},
        "calendar": {"status": "completed", "items_synced": 45, "last_sync_at": "..."}
      }
    }
  ]
}
```

#### `POST /api/v1/sync/initial`

Initiate initial sync for a SINGLE user.

**Request:**
```json
{
  "user_id": "external-user-id",
  "sources": ["gmail", "gdrive", "jira", "calendar"],
  "config": {
    "gmail_days": 30,
    "document_months": 6,
    "jira_months": 3,
    "calendar_days": 30
  }
}
```

**Response:**
```json
{
  "sync_id": "uuid",
  "user_id": "external-user-id",
  "status": "started",
  "sources": ["gmail", "gdrive", "jira", "calendar"],
  "message": "Initial sync started for 4 sources"
}
```

**Valid Sources:** `gmail`, `gdrive`, `jira`, `calendar`, `outlook`, `onedrive`

#### `GET /api/v1/sync/status/{user_id}`

Get sync status for a SINGLE user.

**Response:**
```json
{
  "user_id": "external-user-id",
  "sources": [
    {
      "source": "gmail",
      "status": "completed",
      "items_synced": 150,
      "last_sync_at": "2025-12-22T10:30:00Z",
      "error_message": null
    },
    {
      "source": "jira",
      "status": "syncing",
      "items_synced": 0,
      "last_sync_at": null,
      "error_message": null
    }
  ],
  "overall_status": "syncing"
}
```

**Status Values:** `pending`, `syncing`, `completed`, `failed`, `partial_failure`

#### `POST /api/v1/sync/incremental/{user_id}`

Trigger incremental sync for a user. Only syncs items updated since last sync.

**Query Parameters:**
- `sources` (optional): List of sources to sync. If not provided, syncs all completed sources.

**Response:**
```json
{
  "user_id": "external-user-id",
  "sources": ["gmail", "calendar"],
  "status": "started",
  "message": "Incremental sync started for 2 sources"
}
```

#### `DELETE /api/v1/sync/{user_id}/{source}`

Clear synced data for a specific source.

**Response:**
```json
{
  "user_id": "external-user-id",
  "source": "gmail",
  "deleted_items": 150,
  "message": "Cleared 150 items from gmail"
}
```

---

### Webhook Endpoints

Webhooks allow real-time updates when items are created, updated, or deleted in source systems.

#### `POST /api/v1/webhooks/item-created`

Handle item creation webhook.

**Request:**
```json
{
  "user_id": "external-user-id",
  "source": "gmail",
  "source_id": "msg_123abc",
  "content_type": "email",
  "event_type": "item_created",
  "data": {
    "subject": "Meeting Tomorrow",
    "from": "sender@example.com",
    "body": "..."
  }
}
```

**Response:**
```json
{
  "processed": true,
  "item_id": "msg_123abc"
}
```

#### `POST /api/v1/webhooks/item-updated`

Handle item update webhook. Same request/response format as `item-created`.

#### `POST /api/v1/webhooks/item-deleted`

Handle item deletion webhook.

**Request:**
```json
{
  "user_id": "external-user-id",
  "source": "gmail",
  "source_id": "msg_123abc",
  "event_type": "item_deleted"
}
```

#### `POST /api/v1/webhooks/batch`

Handle batch webhook for multiple items.

**Request:**
```json
[
  {"user_id": "...", "source": "gmail", "source_id": "msg_1", "event_type": "item_created", "data": {...}},
  {"user_id": "...", "source": "gmail", "source_id": "msg_2", "event_type": "item_updated", "data": {...}}
]
```

**Response:**
```json
{
  "processed": 2,
  "failed": 0,
  "errors": []
}
```

---

### Entity Endpoints

Entities are people, projects, and other named items extracted from user data.

#### `GET /api/v1/entities/{user_id}`

List entities for a user.

**Query Parameters:**
- `entity_type` (optional): Filter by type (`person`, `project`, `organization`)
- `limit` (default: 50)
- `offset` (default: 0)

**Response:**
```json
{
  "entities": [
    {
      "id": "uuid",
      "name": "Farhan Ahmad",
      "type": "person",
      "normalized_name": "farhan ahmad",
      "metadata": {"email": "farhan@example.com", "title": "CTO"},
      "mention_count": 45,
      "last_seen_at": "2025-12-22T10:00:00Z",
      "created_at": "2025-12-01T08:00:00Z"
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

#### `GET /api/v1/entities/{user_id}/{entity_id}`

Get a specific entity.

#### `GET /api/v1/entities/{user_id}/{entity_id}/context`

Get all context related to an entity (emails, meetings, tasks mentioning this entity).

**Response:**
```json
{
  "entity": {...},
  "recent_items": [
    {"type": "email", "title": "Re: Project Update", "date": "2025-12-20"},
    {"type": "meeting", "title": "Sync Call", "date": "2025-12-19"}
  ],
  "relationships": [
    {"entity": "Project Alpha", "type": "project", "strength": 0.85}
  ]
}
```

#### `POST /api/v1/entities/{user_id}`

Create a new entity manually.

**Request:**
```json
{
  "name": "John Smith",
  "type": "person",
  "metadata": {"email": "john@example.com", "department": "Engineering"}
}
```

#### `PATCH /api/v1/entities/{user_id}/{entity_id}`

Update an entity.

**Request:**
```json
{
  "name": "John D. Smith",
  "metadata": {"title": "Senior Engineer"}
}
```

#### `DELETE /api/v1/entities/{user_id}/{entity_id}`

Delete an entity.

#### `GET /api/v1/entities/{user_id}/search/{query}`

Search entities by name.

**Query Parameters:**
- `entity_type` (optional): Filter by type
- `limit` (default: 10)

**Response:**
```json
{
  "query": "john",
  "results": [
    {"id": "uuid", "name": "John Smith", "type": "person", "metadata": {...}, "mention_count": 12}
  ]
}
```

---

### Preferences Endpoints

User preferences for email style, working hours, and other settings.

#### `GET /api/v1/preferences/{user_id}`

Get all preferences for a user.

**Response:**
```json
{
  "user_id": "external-user-id",
  "preferences": {
    "email": {
      "tone": {"value": "professional", "confidence": 0.9},
      "signature": {"value": "Best regards,\nJohn", "confidence": 1.0}
    },
    "scheduling": {
      "default_meeting_duration": {"value": 30, "confidence": 0.85}
    }
  }
}
```

#### `GET /api/v1/preferences/{user_id}/{preference_type}`

Get preferences of a specific type.

#### `PUT /api/v1/preferences/{user_id}`

Update a specific preference.

**Request:**
```json
{
  "preference_type": "email",
  "preference_key": "tone",
  "value": "casual"
}
```

#### `PUT /api/v1/preferences/{user_id}/working-hours`

Update user's working hours.

**Request:**
```json
{
  "start": "09:00",
  "end": "17:00",
  "timezone": "America/New_York"
}
```

#### `GET /api/v1/preferences/{user_id}/working-hours`

Get user's working hours.

#### `PUT /api/v1/preferences/{user_id}/email`

Update email preferences.

**Request:**
```json
{
  "tone": "professional",
  "length": "brief",
  "signature": "Best,\nJohn",
  "include_greeting": true
}
```

#### `GET /api/v1/preferences/{user_id}/email`

Get email preferences.

#### `GET /api/v1/preferences/{user_id}/frequent-contacts`

Get frequently contacted people.

**Query Parameters:**
- `limit` (default: 10)

**Response:**
```json
{
  "user_id": "external-user-id",
  "frequent_contacts": [
    {"email": "farhan@example.com", "name": "Farhan Ahmad", "count": 45},
    {"email": "team@example.com", "name": "Team", "count": 30}
  ]
}
```

#### `DELETE /api/v1/preferences/{user_id}/{preference_type}/{preference_key}`

Delete a specific preference.

---

### External Data Endpoints

Read-only access to synced external data (emails, calendar, Jira, etc.).

#### `GET /api/v1/external/health`

Health check for external database connection.

#### `GET /api/v1/external/sync-status`

Get row counts for all synced tables.

**Response:**
```json
[
  {"table": "users", "count": 5},
  {"table": "emails", "count": 1500},
  {"table": "calendar_events", "count": 200},
  {"table": "jira_issues", "count": 350}
]
```

#### `GET /api/v1/external/users`

Get all synced users.

**Query Parameters:** `limit`, `offset`

#### `GET /api/v1/external/users/{user_id}`

Get a specific user.

#### `GET /api/v1/external/users/{user_id}/accounts`

Get all accounts (Gmail, Jira, etc.) for a user.

#### `GET /api/v1/external/accounts`

Get all synced accounts.

**Query Parameters:** `provider`, `limit`, `offset`

#### `GET /api/v1/external/calendar-events`

Get synced calendar events.

**Query Parameters:** `account_id`, `limit`, `offset`

#### `GET /api/v1/external/emails`

Get synced emails.

**Query Parameters:** `account_id`, `is_read`, `limit`, `offset`

#### `GET /api/v1/external/contacts`

Get synced contacts.

**Query Parameters:** `account_id`, `limit`, `offset`

#### `GET /api/v1/external/tasks`

Get synced tasks.

**Query Parameters:** `account_id`, `status`, `limit`, `offset`

#### `GET /api/v1/external/jira-boards`

Get synced Jira boards.

**Query Parameters:** `account_id`, `limit`, `offset`

#### `GET /api/v1/external/jira-issues`

Get synced Jira issues.

**Query Parameters:** `account_id`, `status`, `assignee`, `limit`, `offset`

#### `GET /api/v1/external/online-meetings`

Get synced online meetings.

**Query Parameters:** `account_id`, `limit`, `offset`

#### `POST /api/v1/external/sync`

Trigger a sync from the external database.

---

### Health Endpoints

#### `GET /health`

Basic health check (root level, not under /api/v1).

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

#### `GET /ready`

Readiness check - verifies Redis and database connections.

**Response:**
```json
{
  "status": "ready",
  "redis": "connected",
  "database": "connected"
}
```

---

## Request/Response Formats

### Standard Response Structure

Every response follows this structure:

```json
{
  "response_type": "answer | action | clarification",
  "message": "Human-readable response text",
  "session_id": "uuid",

  "action": {
    "id": "act_xxxxxxxx",
    "type": "send_email | create_meeting | create_jira_task | create_document",
    "status": "needs_confirmation | ready",
    "payload": { },
    "preview": "Human-readable preview of the action",
    "missing_fields": ["field1", "field2"]
  },

  "clarifications": [
    {
      "field": "field_name",
      "question": "Natural language question",
      "options": ["Option 1", "Option 2"],
      "required": true
    }
  ],

  "sources": [
    {
      "id": "uuid",
      "type": "email | calendar | jira | document",
      "title": "Source title",
      "date": "ISO date",
      "relevance": 0.95
    }
  ],

  "metadata": {
    "agents_used": ["triage", "memory", "email"],
    "tokens_used": 1234,
    "processing_time_ms": 850,
    "intent": "action_email",
    "confidence": 0.92
  }
}
```

### Response Types

| Type | Description | Action Required |
|------|-------------|-----------------|
| `answer` | Direct answer to a question | Display message |
| `action` | Action ready/pending | Show preview, await confirmation |
| `clarification` | Missing information | Show questions, collect answers |

---

## Agent System

### Triage Agent (Orchestrator)

**Purpose:** LLM-powered intent classification and routing.

**Capabilities:**
- Analyzes user intent using lightweight LLM (gpt-4o-mini)
- Routes to appropriate specialist agent(s)
- Handles multi-step workflows
- Manages conversation flow

**Intent Categories:**

| Category | Description | Routed To |
|----------|-------------|-----------|
| `qa_simple` | Direct question with factual answer | Memory Agent |
| `qa_complex` | Analysis, summarization, comparison | Memory + Domain Agent |
| `action_email` | Send, reply, draft email | Memory + Email Agent |
| `action_meeting` | Schedule, modify, cancel meeting | Memory + Calendar Agent |
| `action_jira` | Create, update, query tasks | Memory + Jira Agent |
| `action_document` | Generate, edit documents | Memory + Document Agent |
| `clarification` | Ambiguous request | Return clarification questions |
| `chitchat` | Greeting, thanks, off-topic | Direct response |

### Memory Agent

**Purpose:** Sole owner of database access and context retrieval.

**Tools:**
| Tool | Description |
|------|-------------|
| `retrieve_semantic` | Vector similarity search |
| `retrieve_by_entity` | Find items mentioning specific people |
| `retrieve_by_date` | Date range queries |
| `retrieve_episodic` | Past conversation context |
| `resolve_entity` | "Farhan" → farhan@hcms.ai |
| `get_preferences` | User preferences (email signature, etc.) |

### Email Agent

**Purpose:** Email drafting, summarization, action extraction.

**Tools:**
| Tool | Description |
|------|-------------|
| `draft_email` | Create email draft |
| `summarize_thread` | Summarize email conversation |
| `extract_action_items` | Find tasks from emails |
| `suggest_reply` | Generate reply suggestions |

**Actions Produced:** `send_email`

### Calendar Agent

**Purpose:** Meeting scheduling and calendar management.

**Tools:**
| Tool | Description |
|------|-------------|
| `create_meeting` | Schedule new meeting |
| `find_available_slots` | Check availability |
| `check_conflicts` | Detect scheduling conflicts |
| `get_upcoming` | List upcoming events |

**Actions Produced:** `create_meeting`, `update_meeting`, `cancel_meeting`

### Jira Agent

**Purpose:** Task/ticket management.

**Tools:**
| Tool | Description |
|------|-------------|
| `create_task` | Create new Jira issue |
| `update_task` | Update existing issue |
| `get_sprint_status` | Sprint overview |
| `search_tasks` | Query tasks |

**Actions Produced:** `create_jira_task`, `update_jira_task`

### Document Agent

**Purpose:** Document generation and analysis.

**Tools:**
| Tool | Description |
|------|-------------|
| `draft_document` | Generate document content |
| `apply_template` | Use predefined templates |
| `summarize_document` | Summarize long documents |
| `generate_proposal` | Create proposals from context |

**Actions Produced:** `create_document`

---

## Action Types

### send_email

```json
{
  "id": "act_a1b2c3d4",
  "type": "send_email",
  "status": "needs_confirmation",
  "payload": {
    "to": ["farhan@hcms.ai"],
    "cc": ["team@hcms.ai"],
    "bcc": [],
    "subject": "Re: Project Update",
    "body": "Hi Farhan,\n\nThanks for the update...",
    "reply_to_id": "msg_xyz123",
    "attachments": []
  },
  "preview": "Email to Farhan Ahmad\nSubject: Re: Project Update\n\nHi Farhan,\nThanks for the update..."
}
```

### create_meeting

```json
{
  "id": "act_b2c3d4e5",
  "type": "create_meeting",
  "status": "needs_confirmation",
  "payload": {
    "title": "Succession Planning Discussion",
    "description": "Follow-up on succession planning project",
    "start_time": "2025-12-21T15:00:00+05:00",
    "end_time": "2025-12-21T15:30:00+05:00",
    "attendees": ["farhan@hcms.ai", "muhammad.ismaeel@hcms.ai"],
    "location": "",
    "video_conference": true,
    "reminder_minutes": 15
  },
  "preview": "Meeting: Succession Planning Discussion\nDate: Dec 21, 2025 at 3:00 PM\nDuration: 30 minutes\nWith: Farhan Ahmad, Muhammad Ismaeel"
}
```

### create_jira_task

```json
{
  "id": "act_c3d4e5f6",
  "type": "create_jira_task",
  "status": "needs_confirmation",
  "payload": {
    "project_key": "SUCC",
    "issue_type": "Task",
    "summary": "Implement pipeline validation logic",
    "description": "Add validation for succession planning pipeline...",
    "assignee": "muhammad.ismaeel@hcms.ai",
    "priority": "High",
    "labels": ["succession-planning", "backend"],
    "due_date": "2025-12-25"
  },
  "preview": "Jira Task: Implement pipeline validation logic\nProject: SUCC\nAssignee: Muhammad Ismaeel\nPriority: High"
}
```

### create_document

```json
{
  "id": "act_d4e5f6g7",
  "type": "create_document",
  "status": "needs_confirmation",
  "payload": {
    "title": "NEP AI Leadership Assessment - Technical Proposal",
    "format": "pdf",
    "template": "technical_proposal",
    "content": {
      "sections": [
        {"title": "Executive Summary", "content": "..."},
        {"title": "Technical Approach", "content": "..."},
        {"title": "Timeline", "content": "..."}
      ]
    },
    "output_destination": "gdrive"
  },
  "preview": "Document: NEP AI Leadership Assessment - Technical Proposal\nFormat: PDF\nSections: Executive Summary, Technical Approach, Timeline"
}
```

---

## Session Lifecycle

### How Sessions Work

1. **Creation:** Auto-created on first message if `session_id` not provided
2. **Continuation:** Provide `session_id` to continue conversation
3. **Context:** Each session maintains conversation history and pending actions
4. **Expiry:** Sessions expire after 24 hours of inactivity

### Pending Actions

Actions remain pending until confirmed. They are stored in the session.

```json
{
  "session_id": "sess_abc123",
  "pending_actions": [
    {
      "id": "act_a1b2c3d4",
      "type": "send_email",
      "created_at": "2025-12-20T10:30:00Z",
      "expires_at": "2025-12-20T11:30:00Z"
    }
  ]
}
```

---

## Flow Examples

### Example 1: Simple Question

**Request:**
```json
{
  "user_id": "55cdf147-9803-490e-b37e-255a4e55a4da",
  "message": "What emails did Farhan send me this week?"
}
```

**Response:**
```json
{
  "response_type": "answer",
  "message": "Farhan sent you 3 emails this week:\n\n1. **Dec 18** - Updated invitation: HCMS daily update/sync @ Thu Dec 18, 2025 10pm\n2. **Dec 18** - Updated invitation: HCMS daily update/sync @ Thu Jan 1, 2026 8pm\n3. **Dec 17** - Updated invitation: HCMS daily update/sync @ Wed Dec 17, 2025 7pm\n\nAll are meeting invitation updates for the daily HCMS sync.",
  "session_id": "sess_new123",
  "sources": [
    {"id": "email_001", "type": "email", "title": "Updated invitation: HCMS daily update/sync", "date": "2025-12-18"},
    {"id": "email_002", "type": "email", "title": "Updated invitation: HCMS daily update/sync", "date": "2025-12-18"},
    {"id": "email_003", "type": "email", "title": "Updated invitation: HCMS daily update/sync", "date": "2025-12-17"}
  ],
  "metadata": {
    "agents_used": ["triage", "memory"],
    "intent": "qa_simple",
    "confidence": 0.95
  }
}
```

---

### Example 2: Create Meeting (Action)

**Request:**
```json
{
  "user_id": "55cdf147-9803-490e-b37e-255a4e55a4da",
  "message": "Schedule a meeting with Farhan tomorrow at 3pm to discuss succession planning"
}
```

**Response:**
```json
{
  "response_type": "action",
  "message": "I'll schedule a meeting with Farhan Ahmad tomorrow at 3:00 PM to discuss Succession Planning. Here's a preview:",
  "session_id": "sess_abc123",
  "action": {
    "id": "act_meet_001",
    "type": "create_meeting",
    "status": "needs_confirmation",
    "payload": {
      "title": "Succession Planning Discussion",
      "start_time": "2025-12-21T15:00:00+05:00",
      "end_time": "2025-12-21T15:30:00+05:00",
      "attendees": ["farhan@hcms.ai"],
      "description": "Discussion about Succession Planning project",
      "video_conference": true
    },
    "preview": "📅 Meeting: Succession Planning Discussion\n📆 Dec 21, 2025 at 3:00 PM (30 min)\n👥 Attendees: Farhan Ahmad (farhan@hcms.ai)\n🔗 Video conference will be added"
  },
  "metadata": {
    "agents_used": ["triage", "memory", "calendar"],
    "intent": "action_meeting",
    "confidence": 0.94
  }
}
```

**Confirmation Request:**
```json
{
  "user_id": "55cdf147-9803-490e-b37e-255a4e55a4da",
  "session_id": "sess_abc123",
  "message": "yes, create it",
  "confirm_action": "act_meet_001"
}
```

**Confirmation Response:**
```json
{
  "response_type": "action",
  "message": "Meeting scheduled successfully!",
  "session_id": "sess_abc123",
  "action": {
    "id": "act_meet_001",
    "type": "create_meeting",
    "status": "ready",
    "payload": {
      "title": "Succession Planning Discussion",
      "start_time": "2025-12-21T15:00:00+05:00",
      "end_time": "2025-12-21T15:30:00+05:00",
      "attendees": ["farhan@hcms.ai"],
      "description": "Discussion about Succession Planning project",
      "video_conference": true
    }
  }
}
```

**Backend Action:** When `status: "ready"`, execute the action using Google Calendar API / Microsoft Graph API.

---

### Example 3: Missing Information (Clarification)

**Request:**
```json
{
  "user_id": "55cdf147-9803-490e-b37e-255a4e55a4da",
  "message": "Create a task for the project"
}
```

**Response:**
```json
{
  "response_type": "clarification",
  "message": "I'd be happy to create a task. I need a few more details:",
  "session_id": "sess_def456",
  "clarifications": [
    {
      "field": "project",
      "question": "Which project should this task be in?",
      "options": ["Succession Planning", "NEP AI", "NLP Engine"],
      "required": true
    },
    {
      "field": "summary",
      "question": "What should the task title be?",
      "options": null,
      "required": true
    },
    {
      "field": "assignee",
      "question": "Who should this be assigned to?",
      "options": ["Me", "Farhan Ahmad", "Muhammad Ismaeel", "Usman Mustafa"],
      "required": false
    }
  ],
  "metadata": {
    "agents_used": ["triage", "memory"],
    "intent": "action_jira",
    "confidence": 0.88
  }
}
```

**Follow-up with Answers:**
```json
{
  "user_id": "55cdf147-9803-490e-b37e-255a4e55a4da",
  "session_id": "sess_def456",
  "message": "Succession Planning, 'Implement validation logic', assign to Ismaeel"
}
```

---

### Example 4: Email with Attachment (Hybrid)

**Request with ad-hoc email content:**
```json
{
  "user_id": "55cdf147-9803-490e-b37e-255a4e55a4da",
  "message": "Summarize this email and draft a reply",
  "attachments": [
    {
      "type": "email",
      "content": {
        "from": "client@example.com",
        "to": ["rauf.rahim@hcms.ai"],
        "subject": "Project Timeline Concerns",
        "body": "Hi Rauf,\n\nI wanted to discuss some concerns about the project timeline...",
        "date": "2025-12-20T09:00:00Z"
      }
    }
  ]
}
```

**Response:**
```json
{
  "response_type": "action",
  "message": "**Summary:**\nThe client has concerns about the project timeline and is asking for clarification on deliverables.\n\n**Draft Reply:**",
  "session_id": "sess_ghi789",
  "action": {
    "id": "act_email_001",
    "type": "send_email",
    "status": "needs_confirmation",
    "payload": {
      "to": ["client@example.com"],
      "subject": "Re: Project Timeline Concerns",
      "body": "Hi,\n\nThank you for reaching out about the timeline concerns. I understand the importance of clarity on deliverables.\n\n[Details to add based on your input]\n\nBest regards,\nRauf"
    },
    "preview": "To: client@example.com\nSubject: Re: Project Timeline Concerns\n\nHi,\n\nThank you for reaching out..."
  }
}
```

---

### Example 5: Multi-Step Workflow

**Request:**
```json
{
  "user_id": "55cdf147-9803-490e-b37e-255a4e55a4da",
  "message": "Schedule a meeting with Farhan about succession planning and create a Jira task to prepare the agenda"
}
```

**Response:**
```json
{
  "response_type": "action",
  "message": "I'll help you with both:\n\n1. **Meeting** with Farhan about Succession Planning\n2. **Jira Task** to prepare the agenda\n\nPlease review:",
  "session_id": "sess_jkl012",
  "action": {
    "id": "act_multi_001",
    "type": "multi_action",
    "status": "needs_confirmation",
    "payload": {
      "actions": [
        {
          "id": "act_meet_002",
          "type": "create_meeting",
          "payload": {
            "title": "Succession Planning Discussion",
            "attendees": ["farhan@hcms.ai"],
            "start_time": null,
            "duration_minutes": 30
          },
          "missing_fields": ["start_time"]
        },
        {
          "id": "act_jira_001",
          "type": "create_jira_task",
          "payload": {
            "project_key": "SUCC",
            "summary": "Prepare agenda for Succession Planning meeting",
            "assignee": "rauf.rahim@hcms.ai",
            "priority": "Medium"
          }
        }
      ]
    },
    "missing_fields": ["meeting_time"]
  },
  "clarifications": [
    {
      "field": "meeting_time",
      "question": "When should the meeting be scheduled?",
      "options": ["Tomorrow 3pm", "This week", "Next Monday"],
      "required": true
    }
  ]
}
```

---

## Error Handling

### Error Response Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": { }
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `USER_NOT_FOUND` | 404 | User ID does not exist |
| `SESSION_NOT_FOUND` | 404 | Session ID does not exist |
| `SESSION_EXPIRED` | 410 | Session has expired |
| `ACTION_NOT_FOUND` | 404 | Action ID not found in session |
| `ACTION_EXPIRED` | 410 | Action has expired |
| `INVALID_REQUEST` | 400 | Malformed request body |
| `CONTEXT_ERROR` | 500 | Failed to retrieve context |
| `AGENT_ERROR` | 500 | Agent processing failed |
| `RATE_LIMITED` | 429 | Too many requests |

### Example Error Response

```json
{
  "error": {
    "code": "ACTION_EXPIRED",
    "message": "The action 'act_meet_001' has expired. Please create a new request.",
    "details": {
      "action_id": "act_meet_001",
      "created_at": "2025-12-20T10:00:00Z",
      "expired_at": "2025-12-20T11:00:00Z"
    }
  }
}
```

---

## Backend Integration Guide

### Handling Responses

```python
response = api.chat(user_id, message)

if response["response_type"] == "answer":
    # Just display the message
    display(response["message"])

elif response["response_type"] == "clarification":
    # Show clarification questions to user
    for q in response["clarifications"]:
        answer = prompt_user(q["question"], q["options"])
        # Send follow-up with answers

elif response["response_type"] == "action":
    action = response["action"]

    if action["status"] == "needs_confirmation":
        # Show preview and ask for confirmation
        if user_confirms(action["preview"]):
            # Send confirmation request
            api.chat(user_id, "yes",
                     session_id=response["session_id"],
                     confirm_action=action["id"])

    elif action["status"] == "ready":
        # Execute the action
        if action["type"] == "send_email":
            gmail_api.send(action["payload"])
        elif action["type"] == "create_meeting":
            calendar_api.create(action["payload"])
        elif action["type"] == "create_jira_task":
            jira_api.create(action["payload"])
        elif action["type"] == "create_document":
            docs_api.create(action["payload"])
```

### Webhook Alternative

Instead of polling, you can register a webhook to receive action confirmations:

```json
POST /api/v1/webhooks
{
  "user_id": "55cdf147-...",
  "url": "https://your-backend.com/ai-actions",
  "events": ["action.ready", "action.expired"]
}
```

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| `/api/v1/chat` | 60 requests/minute per user |
| `/api/v1/sessions` | 30 requests/minute per user |

---

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5433/external_data_db

# Redis (for working memory)
REDIS_URL=redis://localhost:6379/0

# OpenAI
OPENAI_API_KEY=sk-...
CHAT_MODEL=gpt-4o-mini
CHAT_MODEL_ADVANCED=gpt-4o

# Session Settings
SESSION_TTL_HOURS=24
ACTION_TTL_MINUTES=60
```

---

## Changelog

### v2.0.0 (Current)
- Multi-agent architecture with LLM-based triage
- Standardized action/response format
- Session-based conversation management
- Memory Agent for centralized RAG

### v1.0.0 (Previous)
- Single chat endpoint with basic RAG
- Simple query analysis

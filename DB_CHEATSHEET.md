# DB Quick Cheatsheet

## Tables at a Glance

| Table | What it stores |
|-------|---------------|
| `users` | User accounts |
| `knowledge_items` | Emails, docs, tasks, events |
| `embeddings` | Vector embeddings (1536 dim) |
| `entities` | People, projects, topics, companies |
| `entity_mentions` | Where entities appear |
| `chat_sessions` | Conversation sessions |
| `chat_messages` | Individual messages |
| `user_preferences` | Learned preferences |
| `user_feedback` | Thumbs up/down, edits |
| `integration_syncs` | Sync status per source |

## Source Types
`gmail` | `gdrive` | `calendar` | `outlook` | `onedrive` | `jira`

## Content Types
`email` | `document` | `task` | `event`

## Entity Types
`person` | `project` | `topic` | `company`

## Preference Types
`email_tone` | `response_length` | `working_hours` | `interaction` | `topic_interest`

## Message Roles
`user` | `assistant` | `system`

## Sync Statuses
`pending` | `syncing` | `completed` | `failed`

## Feedback Types
`rating` | `edit` | `accept` | `reject`

## Key Fields

### knowledge_items
- `source_type` - where data came from
- `content_type` - what kind of data
- `title` - item title
- `content` - full text
- `summary` - AI summary
- `metadata` - JSON with source-specific data

### entities
- `entity_type` - person/project/topic/company
- `name` - display name
- `mention_count` - popularity
- `metadata` - emails, job_title, company, etc.

### user_preferences
- `preference_type` - category
- `preference_key` - specific setting
- `preference_value` - the value (JSON)
- `confidence` - 0.0 to 1.0

### chat_messages
- `role` - who sent it
- `content` - message text
- `context_items` - knowledge used
- `pending_actions` - actions to execute

## Redis Keys
```
working:{user_id}:{session_id}:context  (30 min TTL)
prefs:{user_id}                          (1 hour TTL)
recent:{user_id}:items                   (15 min TTL)
```

## Common Metadata

**Email:**
`from`, `to`, `cc`, `thread_id`, `labels`, `is_reply`

**Document:**
`mime_type`, `folder_id`, `chunk_index`, `total_chunks`

**Task (Jira):**
`project_key`, `status`, `assignee`, `priority`

**Event:**
`attendees`, `location`, `recurrence`

**Person Entity:**
`emails`, `job_title`, `company`, `relationship`

## API Prefixes
- Chat: `/api/v1/chat`
- Sync: `/api/v1/sync`
- Entities: `/api/v1/entities`
- Preferences: `/api/v1/preferences`
- Webhooks: `/api/v1/webhooks`

# AI Assistant - User Journeys & Use Cases
## Complete Technical Flow Documentation

---

## Table of Contents

1. [Email → Jira Tasks from GDrive Proposal](#use-case-1-email--jira-tasks-from-gdrive-proposal)
2. [Draft Email Reply with Context](#use-case-2-draft-email-reply-with-context)
3. [Schedule Meeting from Email Thread](#use-case-3-schedule-meeting-from-email-thread)
4. [Create Document from Multiple Sources](#use-case-4-create-document-from-multiple-sources)
5. [Find and Summarize Project Status](#use-case-5-find-and-summarize-project-status)
6. [Follow-up Reminder from Past Conversation](#use-case-6-follow-up-reminder-from-past-conversation)
7. [Onboard New Team Member Context](#use-case-7-onboard-new-team-member-context)
8. [Weekly Report Generation](#use-case-8-weekly-report-generation)
9. [Cross-Platform Task Handoff](#use-case-9-cross-platform-task-handoff)
10. [Smart Email Categorization & Actions](#use-case-10-smart-email-categorization--actions)

---

## Use Case 1: Email → Jira Tasks from GDrive Proposal

### Scenario
User is reading an email from a client about a new project. The email references a proposal PDF stored in Google Drive. User wants to create Jira tasks based on the proposal requirements.

### User Input
```
"Create Jira tasks from the proposal Sarah sent about the mobile app project"
```

### Complete Technical Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STEP 1: REQUEST RECEIVED                           │
└─────────────────────────────────────────────────────────────────────────────┘

POST /api/v1/chat
{
    "user_id": "usr_123",
    "message": "Create Jira tasks from the proposal Sarah sent about the mobile app project"
}

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        STEP 2: ORCHESTRATOR RECEIVES                         │
│                                                                              │
│  OrchestratorAgent.run() called with:                                       │
│  - task: "Create Jira tasks from the proposal Sarah sent..."                │
│  - state: AgentState(user_id="usr_123", session_id="new", ...)              │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      STEP 3: INTENT CLASSIFICATION                           │
│                                                                              │
│  Orchestrator's first LLM call analyzes:                                    │
│  - Primary intent: CREATE_JIRA_TASKS                                        │
│  - Required context: email (Sarah), document (proposal), jira (project)     │
│  - Entities detected: "Sarah" (person), "mobile app project" (project)      │
│                                                                              │
│  LLM decides to call tool: retrieve_context                                 │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 4: CONTEXT RETRIEVAL (PARALLEL)                     │
└─────────────────────────────────────────────────────────────────────────────┘

Tool Call #1: retrieve_context
{
    "query": "proposal Sarah mobile app project",
    "sources": ["gmail", "gdrive", "jira"],
    "entity_filter": "Sarah",
    "time_filter": "last_month",
    "limit": 15
}

                    ┌───────────────┴───────────────┐
                    │                               │
                    ▼                               ▼
        ┌─────────────────────┐         ┌─────────────────────┐
        │  EMBEDDING SEARCH   │         │   ENTITY LOOKUP     │
        │                     │         │                     │
        │  1. Embed query:    │         │  1. Find "Sarah"    │
        │     "proposal Sarah │         │     in entities     │
        │      mobile app"    │         │     table           │
        │                     │         │                     │
        │  2. Vector search   │         │  2. Get her email:  │
        │     in pgvector:    │         │     sarah@client.com│
        │                     │         │                     │
        │  SELECT * FROM      │         │  3. Find all items  │
        │  embeddings         │         │     mentioning her  │
        │  ORDER BY embedding │         │                     │
        │  <=> $query_embed   │         │                     │
        │  LIMIT 15           │         │                     │
        └─────────┬───────────┘         └──────────┬──────────┘
                  │                                │
                  └────────────────┬───────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONTEXT SERVICE: MERGE & RANK                          │
│                                                                             │
│  Results merged and scored:                                                 │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ ID: ki_001 | Source: GMAIL | Score: 0.94                               │ │
│  │ Title: "Mobile App Project Proposal"                                   │ │
│  │ From: sarah@client.com                                                 │ │
│  │ Date: 2024-01-10                                                       │ │
│  │ Summary: "Sarah sent proposal for mobile app. Attached PDF with        │ │
│  │           requirements. Deadline Q2. Budget $150k."                    │ │
│  │ Metadata: {thread_id: "th_abc", has_attachment: true}                  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ ID: ki_002 | Source: GDRIVE | Score: 0.91                              │ │
│  │ Title: "Mobile_App_Proposal_v2.pdf"                                    │ │
│  │ Chunks: 5 (all retrieved)                                              │ │
│  │ Content: [Full proposal text across 5 chunks]                          │ │
│  │ Metadata: {pages: 12, folder: "/Client Projects/Acme"}                 │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ ID: ki_003 | Source: JIRA | Score: 0.78                                │ │
│  │ Title: "MOBILE-1: Mobile App Project Setup"                            │ │
│  │ Status: To Do | Project: MOBILE                                        │ │
│  │ Description: "Initial project setup for mobile app development"        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ ID: ki_004 | Source: GMAIL | Score: 0.72                               │ │
│  │ Title: "Re: Mobile App Project Proposal"                               │ │
│  │ Summary: "Follow-up discussion about timeline and resources"           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   STEP 5: ORCHESTRATOR ANALYZES CONTEXT                     │
│                                                                             │
│  LLM receives context and decides:                                          │
│  - Found email from Sarah with proposal reference ✓                         │
│  - Found proposal PDF in GDrive ✓                                           │
│  - Found existing Jira project "MOBILE" ✓                                   │
│  - Need to extract tasks from proposal → delegate to TaskAgent              │
│                                                                             │
│  Tool Call: delegate_to_specialist                                          │
│  {                                                                          │
│      "specialist": "task",                                                  │
│      "task": "Extract Jira tasks from this proposal",                       │
│      "context_ids": ["ki_002"]  // The PDF                                  │
│  }                                                                          │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      STEP 6: TASK AGENT PROCESSING                           │
│                                                                              │
│  TaskAgent.run() with proposal content:                                     │
│                                                                              │
│  System Prompt: "You are a Jira task specialist..."                         │
│                                                                              │
│  Context Provided:                                                          │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ [GDRIVE] Mobile_App_Proposal_v2.pdf                                    │ │
│  │                                                                         │ │
│  │ ## Project Overview                                                     │ │
│  │ Mobile application for iOS and Android platforms...                    │ │
│  │                                                                         │ │
│  │ ## Requirements                                                         │ │
│  │ 1. User Authentication (OAuth, Social Login)                           │ │
│  │ 2. Product Catalog with search and filters                             │ │
│  │ 3. Shopping Cart functionality                                         │ │
│  │ 4. Payment Integration (Stripe, Apple Pay)                             │ │
│  │ 5. Push Notifications                                                  │ │
│  │ 6. Offline Mode support                                                │ │
│  │                                                                         │ │
│  │ ## Timeline                                                             │ │
│  │ Phase 1: Core features (8 weeks)                                       │ │
│  │ Phase 2: Payment & notifications (4 weeks)                             │ │
│  │ Phase 3: Polish & launch (4 weeks)                                     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  TaskAgent calls tool: extract_tasks                                        │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    STEP 7: TASK EXTRACTION (LLM CALL)                        │
│                                                                              │
│  OpenAI API Call:                                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ model: "gpt-4o-mini"                                                   │ │
│  │ messages: [                                                             │ │
│  │   {role: "system", content: "Extract Jira tasks..."},                  │ │
│  │   {role: "user", content: "Extract tasks from:\n{proposal_text}"}      │ │
│  │ ]                                                                       │ │
│  │ response_format: {"type": "json_object"}                               │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  LLM Response:                                                              │
│  {                                                                           │
│    "tasks": [                                                               │
│      {                                                                       │
│        "summary": "Implement User Authentication",                          │
│        "description": "OAuth and social login (Google, Apple, Facebook)",  │
│        "type": "story",                                                     │
│        "priority": "high",                                                  │
│        "labels": ["authentication", "phase-1"],                            │
│        "estimated_days": 10                                                 │
│      },                                                                      │
│      {                                                                       │
│        "summary": "Build Product Catalog",                                  │
│        "description": "Product listing with search, filters, categories",  │
│        "type": "story",                                                     │
│        "priority": "high",                                                  │
│        "labels": ["catalog", "phase-1"],                                   │
│        "estimated_days": 14                                                 │
│      },                                                                      │
│      {                                                                       │
│        "summary": "Implement Shopping Cart",                                │
│        "description": "Add to cart, update quantity, remove items",        │
│        "type": "story",                                                     │
│        "priority": "high",                                                  │
│        "labels": ["cart", "phase-1"],                                      │
│        "estimated_days": 7                                                  │
│      },                                                                      │
│      {                                                                       │
│        "summary": "Integrate Payment Gateway",                              │
│        "description": "Stripe and Apple Pay integration",                  │
│        "type": "story",                                                     │
│        "priority": "medium",                                               │
│        "labels": ["payments", "phase-2"],                                  │
│        "estimated_days": 10                                                 │
│      },                                                                      │
│      {                                                                       │
│        "summary": "Setup Push Notifications",                               │
│        "description": "Firebase Cloud Messaging for iOS/Android",          │
│        "type": "story",                                                     │
│        "priority": "medium",                                               │
│        "labels": ["notifications", "phase-2"],                             │
│        "estimated_days": 5                                                  │
│      },                                                                      │
│      {                                                                       │
│        "summary": "Implement Offline Mode",                                 │
│        "description": "Local caching and sync when online",                │
│        "type": "story",                                                     │
│        "priority": "low",                                                  │
│        "labels": ["offline", "phase-1"],                                   │
│        "estimated_days": 8                                                  │
│      }                                                                       │
│    ]                                                                         │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│              STEP 8: ORCHESTRATOR NEEDS MORE INFORMATION                     │
│                                                                              │
│  Orchestrator reviews extracted tasks and realizes:                         │
│  - Tasks extracted ✓                                                        │
│  - Project key needed (found MOBILE from context)                           │
│  - Assignees not specified → need to ask user                               │
│                                                                              │
│  Tool Call: ask_user                                                        │
│  {                                                                           │
│      "question": "I found 6 tasks from Sarah's proposal. Before creating   │
│                   them in Jira project MOBILE, I need to know:",           │
│      "options": null,  // Free-form response needed                         │
│      "required_for": "task assignment and sprint planning"                 │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       STEP 9: RESPONSE TO USER                               │
│                                                                              │
│  API Response:                                                              │
│  {                                                                           │
│    "session_id": "sess_abc123",                                             │
│    "response": "I found Sarah's proposal for the Mobile App Project and    │
│                 extracted 6 tasks:\n\n                                      │
│                 **Phase 1 (8 weeks):**\n                                    │
│                 1. Implement User Authentication (10 days)\n                │
│                 2. Build Product Catalog (14 days)\n                        │
│                 3. Implement Shopping Cart (7 days)\n                       │
│                 4. Implement Offline Mode (8 days)\n\n                      │
│                 **Phase 2 (4 weeks):**\n                                    │
│                 5. Integrate Payment Gateway (10 days)\n                    │
│                 6. Setup Push Notifications (5 days)\n\n                    │
│                 Before I create these in Jira project MOBILE:\n            │
│                 - Who should be assigned to these tasks?\n                  │
│                 - Should I create them in a specific sprint?\n              │
│                 - Any additional labels or components?",                    │
│                                                                              │
│    "needs_clarification": true,                                             │
│    "clarification": {                                                       │
│      "question": "Who should be assigned and which sprint?",                │
│      "required_for": "task assignment and sprint planning"                 │
│    },                                                                        │
│    "context_used": [                                                        │
│      {"id": "ki_001", "source": "gmail", "title": "Mobile App Proposal"},  │
│      {"id": "ki_002", "source": "gdrive", "title": "Mobile_App_Proposal"}  │
│    ],                                                                        │
│    "pending_actions": []                                                    │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        STEP 10: USER RESPONDS                                │
│                                                                              │
│  User: "Assign Phase 1 to John and Phase 2 to Mike. Put them in Sprint 5." │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                STEP 11: ORCHESTRATOR PROCESSES RESPONSE                      │
│                                                                              │
│  Additional context retrieval for assignees:                                │
│                                                                              │
│  Entity Lookup:                                                             │
│  - "John" → john@company.com (from entities table)                         │
│  - "Mike" → mike@company.com (from entities table)                         │
│                                                                              │
│  Tool Call: execute_action (6 times, for each task)                         │
│  {                                                                           │
│    "action_type": "create_jira_task",                                       │
│    "params": {                                                              │
│      "project_key": "MOBILE",                                               │
│      "summary": "Implement User Authentication",                            │
│      "description": "OAuth and social login...",                           │
│      "type": "story",                                                       │
│      "priority": "high",                                                    │
│      "assignee": "john@company.com",                                        │
│      "sprint": "Sprint 5",                                                  │
│      "labels": ["authentication", "phase-1"]                               │
│    },                                                                        │
│    "confirm_first": true                                                    │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   STEP 12: CONFIRMATION REQUEST                              │
│                                                                              │
│  API Response:                                                              │
│  {                                                                           │
│    "response": "I'll create these 6 tasks in MOBILE Sprint 5:\n\n          │
│                 **Assigned to John:**\n                                     │
│                 1. Implement User Authentication\n                          │
│                 2. Build Product Catalog\n                                  │
│                 3. Implement Shopping Cart\n                                │
│                 4. Implement Offline Mode\n\n                               │
│                 **Assigned to Mike:**\n                                     │
│                 5. Integrate Payment Gateway\n                              │
│                 6. Setup Push Notifications\n\n                             │
│                 Confirm to create?",                                        │
│                                                                              │
│    "pending_actions": [                                                     │
│      {"id": "act_1", "type": "create_jira_task", "description": "..."},    │
│      {"id": "act_2", "type": "create_jira_task", "description": "..."},    │
│      {"id": "act_3", "type": "create_jira_task", "description": "..."},    │
│      {"id": "act_4", "type": "create_jira_task", "description": "..."},    │
│      {"id": "act_5", "type": "create_jira_task", "description": "..."},    │
│      {"id": "act_6", "type": "create_jira_task", "description": "..."}     │
│    ]                                                                         │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      STEP 13: USER CONFIRMS                                  │
│                                                                              │
│  POST /api/v1/chat                                                          │
│  {                                                                           │
│    "user_id": "usr_123",                                                    │
│    "session_id": "sess_abc123",                                             │
│    "message": "Yes, create them",                                           │
│    "confirm_actions": ["act_1", "act_2", "act_3", "act_4", "act_5", "act_6"]│
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   STEP 14: ACTION EXECUTOR RUNS                              │
│                                                                              │
│  For each pending action:                                                   │
│                                                                              │
│  ActionExecutor.execute("create_jira_task", params)                         │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │  EXTERNAL API CALL (to Frontend/Backend Service)                       │ │
│  │                                                                         │ │
│  │  POST https://internal-api.company.com/v1/users/usr_123/jira/issues    │ │
│  │  Authorization: Bearer {api_key}                                        │ │
│  │  Content-Type: application/json                                         │ │
│  │                                                                         │ │
│  │  {                                                                      │ │
│  │    "project_key": "MOBILE",                                             │ │
│  │    "type": "story",                                                     │ │
│  │    "summary": "Implement User Authentication",                          │ │
│  │    "description": "OAuth and social login (Google, Apple, Facebook).\n │ │
│  │                    \n## Acceptance Criteria\n- User can sign up...",    │ │
│  │    "priority": "high",                                                  │ │
│  │    "assignee": "john@company.com",                                      │ │
│  │    "labels": ["authentication", "phase-1"],                             │ │
│  │    "sprint": "Sprint 5"                                                 │ │
│  │  }                                                                      │ │
│  │                                                                         │ │
│  │  Response: 201 Created                                                  │ │
│  │  {                                                                      │ │
│  │    "id": "10234",                                                       │ │
│  │    "key": "MOBILE-42",                                                  │ │
│  │    "url": "https://company.atlassian.net/browse/MOBILE-42"             │ │
│  │  }                                                                      │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  Repeat for all 6 tasks...                                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      STEP 15: FINAL RESPONSE                                 │
│                                                                              │
│  {                                                                           │
│    "response": "Done! Created 6 tasks in MOBILE Sprint 5:\n\n              │
│                 **Assigned to John:**\n                                     │
│                 - [MOBILE-42](https://...): User Authentication\n          │
│                 - [MOBILE-43](https://...): Product Catalog\n              │
│                 - [MOBILE-44](https://...): Shopping Cart\n                │
│                 - [MOBILE-45](https://...): Offline Mode\n\n               │
│                 **Assigned to Mike:**\n                                     │
│                 - [MOBILE-46](https://...): Payment Gateway\n              │
│                 - [MOBILE-47](https://...): Push Notifications\n\n         │
│                 Total estimated: 54 days",                                  │
│                                                                              │
│    "completed_actions": [                                                   │
│      {"type": "create_jira_task", "result": {"key": "MOBILE-42", ...}},    │
│      {"type": "create_jira_task", "result": {"key": "MOBILE-43", ...}},    │
│      ...                                                                    │
│    ]                                                                         │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   STEP 16: POST-ACTION UPDATES                               │
│                                                                              │
│  1. Store interaction in episodic memory:                                   │
│     INSERT INTO chat_messages (session_id, role, content, context_items)   │
│                                                                              │
│  2. Update user preferences (procedural memory):                            │
│     - John assigned to auth tasks → preference learned                      │
│     - Mike assigned to integration tasks → preference learned               │
│                                                                              │
│  3. Update entities:                                                        │
│     - Link "Sarah" to "MOBILE" project                                     │
│     - Link "John" and "Mike" to "MOBILE" project                           │
│                                                                              │
│  4. Webhook received (when Jira updates):                                   │
│     POST /webhooks/item-created                                             │
│     → New tasks embedded in AI DB for future context                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Agents Involved
| Agent | Role | Actions |
|-------|------|---------|
| **Orchestrator** | Coordinates flow | Context retrieval, delegation, user Q&A |
| **TaskAgent** | Extract tasks | Parse proposal, structure Jira tasks |
| **ActionExecutor** | Create tasks | Call external Jira API |

### Embedding Interactions
| Step | Type | Details |
|------|------|---------|
| Query embedding | Semantic | `"proposal Sarah mobile app"` → vector |
| Email retrieval | Hybrid | Matched by entity + semantic similarity |
| PDF retrieval | Full embed | All 5 chunks retrieved and merged |
| Jira retrieval | Full embed | Found existing project context |

---

## Use Case 2: Draft Email Reply with Context

### Scenario
User receives an email asking about project status. AI drafts a reply using context from Jira tasks, recent emails, and calendar.

### User Input
```
"Help me reply to David's email about the Q1 project status"
```

### Complete Technical Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER REQUEST                                    │
│  "Help me reply to David's email about the Q1 project status"               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR: INTENT CLASSIFICATION                       │
│                                                                              │
│  Intent: DRAFT_EMAIL_REPLY                                                  │
│  Required context:                                                          │
│  - David's email (what to reply to)                                         │
│  - Q1 project status (Jira)                                                 │
│  - Recent communications with David                                         │
│  - Any upcoming meetings about Q1                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PARALLEL CONTEXT RETRIEVAL                                │
│                                                                              │
│  Query 1: retrieve_context                                                  │
│  {                                                                           │
│    "query": "David email Q1 project status",                                │
│    "sources": ["gmail"],                                                    │
│    "entity_filter": "David",                                                │
│    "time_filter": "last_week",                                              │
│    "limit": 5                                                               │
│  }                                                                           │
│                                                                              │
│  Query 2: retrieve_context                                                  │
│  {                                                                           │
│    "query": "Q1 project status tasks progress",                             │
│    "sources": ["jira"],                                                     │
│    "time_filter": "last_month",                                             │
│    "limit": 10                                                              │
│  }                                                                           │
│                                                                              │
│  Query 3: retrieve_context                                                  │
│  {                                                                           │
│    "query": "Q1 project meeting David",                                     │
│    "sources": ["calendar"],                                                 │
│    "time_filter": "next_week",                                              │
│    "limit": 3                                                               │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CONTEXT RETRIEVED                                    │
│                                                                              │
│  FROM GMAIL (David's email):                                                │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ From: david@partner.com                                                │ │
│  │ Subject: Q1 Project Status Update Request                              │ │
│  │ Date: Today, 10:30 AM                                                  │ │
│  │                                                                         │ │
│  │ "Hi, Could you provide an update on the Q1 project? Specifically:      │ │
│  │  1. Current completion percentage                                      │ │
│  │  2. Any blockers or risks                                              │ │
│  │  3. Expected completion date                                           │ │
│  │  Our stakeholders are asking. Thanks, David"                           │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  FROM JIRA (Project status):                                                │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Project: Q1-LAUNCH                                                     │ │
│  │ Total tasks: 24                                                        │ │
│  │ Completed: 18 (75%)                                                    │ │
│  │ In Progress: 4                                                         │ │
│  │ Blocked: 2 (API integration waiting on vendor)                         │ │
│  │                                                                         │ │
│  │ Blocked Tasks:                                                         │ │
│  │ - Q1-15: Payment API Integration (blocked by vendor delay)            │ │
│  │ - Q1-18: Third-party Auth (waiting on credentials)                    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                              │
│  FROM CALENDAR (Upcoming):                                                  │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Q1 Project Review Meeting                                              │ │
│  │ Thursday, 2:00 PM                                                      │ │
│  │ Attendees: You, David, Sarah, Mike                                     │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   DELEGATE TO EMAIL AGENT                                    │
│                                                                              │
│  delegate_to_specialist:                                                    │
│  {                                                                           │
│    "specialist": "email",                                                   │
│    "task": "Draft reply to David's Q1 status request",                      │
│    "context_ids": ["ki_email_david", "ki_jira_status", "ki_calendar_mtg"]  │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EMAIL AGENT PROCESSING                                  │
│                                                                              │
│  EmailAgent System Prompt:                                                  │
│  "You are an email specialist. Draft professional replies..."              │
│                                                                              │
│  User Preferences Retrieved (from procedural memory):                       │
│  - Tone: professional                                                       │
│  - Length: medium                                                           │
│  - Always include specific data points                                      │
│  - Sign with "Best regards"                                                 │
│                                                                              │
│  Tool Call: draft_email                                                     │
│  {                                                                           │
│    "reply_to": "david@partner.com",                                         │
│    "subject": "Re: Q1 Project Status Update Request",                       │
│    "context": {combined context},                                           │
│    "tone": "professional",                                                  │
│    "include_data": true                                                     │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      LLM GENERATES DRAFT                                     │
│                                                                              │
│  OpenAI API Call:                                                           │
│  {                                                                           │
│    model: "gpt-4o",                                                         │
│    messages: [                                                              │
│      {role: "system", content: "Draft professional email..."},             │
│      {role: "user", content: "Reply to David about Q1 status using:        │
│                                - 75% complete (18/24 tasks)                │
│                                - 2 blocked tasks (vendor issues)           │
│                                - Meeting Thursday 2pm                      │
│                                Match user's professional tone..."}         │
│    ]                                                                        │
│  }                                                                           │
│                                                                              │
│  Generated Draft:                                                           │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │ Hi David,                                                              │ │
│  │                                                                         │ │
│  │ Thanks for reaching out. Here's the current status on the Q1 project: │ │
│  │                                                                         │ │
│  │ **Progress:** 75% complete (18 of 24 tasks finished)                   │ │
│  │                                                                         │ │
│  │ **Current Blockers:**                                                  │ │
│  │ 1. Payment API Integration - waiting on vendor to provide updated     │ │
│  │    documentation (ETA: end of this week)                               │ │
│  │ 2. Third-party Auth - credentials pending from partner team           │ │
│  │                                                                         │ │
│  │ **Expected Completion:** On track for March 31st, assuming blockers   │ │
│  │ are resolved by next week.                                             │ │
│  │                                                                         │ │
│  │ We have a project review meeting scheduled for Thursday at 2 PM -     │ │
│  │ happy to discuss in more detail there.                                 │ │
│  │                                                                         │ │
│  │ Best regards,                                                          │ │
│  │ [Your name]                                                            │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RESPONSE TO USER                                        │
│                                                                              │
│  {                                                                           │
│    "response": "Here's a draft reply to David:\n\n---\n{draft}\n---\n\n    │
│                 I included:\n                                               │
│                 - Current progress (75%)\n                                  │
│                 - The 2 blockers from Jira\n                                │
│                 - Reference to Thursday's meeting\n\n                       │
│                 Would you like me to:\n                                     │
│                 1. Send this as-is\n                                        │
│                 2. Make it more detailed\n                                  │
│                 3. Make it shorter\n                                        │
│                 4. Adjust the tone",                                        │
│                                                                              │
│    "pending_actions": [                                                     │
│      {                                                                       │
│        "id": "act_send_email",                                              │
│        "type": "send_email",                                                │
│        "description": "Send reply to david@partner.com",                   │
│        "params": {                                                          │
│          "to": "david@partner.com",                                         │
│          "subject": "Re: Q1 Project Status Update Request",                │
│          "body": "{draft}",                                                 │
│          "reply_to_id": "msg_david_123"                                    │
│        }                                                                     │
│      }                                                                       │
│    ]                                                                         │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      USER CONFIRMS                                           │
│                                                                              │
│  User: "Send it"                                                            │
│  confirm_actions: ["act_send_email"]                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ACTION EXECUTOR                                         │
│                                                                              │
│  POST https://internal-api.company.com/v1/users/usr_123/emails/send         │
│  {                                                                           │
│    "to": "david@partner.com",                                               │
│    "subject": "Re: Q1 Project Status Update Request",                       │
│    "body": "{draft}",                                                       │
│    "reply_to_id": "msg_david_123"                                          │
│  }                                                                           │
│                                                                              │
│  Response: {"message_id": "msg_reply_456", "status": "sent"}               │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FINAL RESPONSE                                          │
│                                                                              │
│  "Email sent to David! The reply is now in your sent folder."              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Agents Involved
| Agent | Role |
|-------|------|
| **Orchestrator** | Retrieve multi-source context |
| **EmailAgent** | Draft professional reply |
| **ActionExecutor** | Send via external API |

---

## Use Case 3: Schedule Meeting from Email Thread

### Scenario
User wants to schedule a meeting based on an email discussion about availability.

### User Input
```
"Schedule the team sync that Lisa mentioned in her email"
```

### Technical Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CONTEXT RETRIEVAL                                 │
└─────────────────────────────────────────────────────────────────────────────┘

retrieve_context:
{
    "query": "Lisa team sync meeting schedule",
    "sources": ["gmail"],
    "entity_filter": "Lisa",
    "time_filter": "last_week"
}

Results:
┌────────────────────────────────────────────────────────────────────────────┐
│ Email from Lisa (2 days ago):                                              │
│ "Hi team, Let's schedule a sync to discuss the roadmap.                   │
│  I'm available:                                                            │
│  - Tuesday 2-4pm                                                           │
│  - Wednesday 10am-12pm                                                     │
│  - Thursday after 3pm                                                      │
│  Can someone send out the invite? Attendees: Me, John, Sarah, Mike"       │
└────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CALENDAR AVAILABILITY CHECK                               │
│                                                                              │
│  retrieve_context:                                                          │
│  {                                                                           │
│    "query": "calendar availability",                                        │
│    "sources": ["calendar"],                                                 │
│    "time_filter": "next_week"                                               │
│  }                                                                           │
│                                                                              │
│  User's calendar checked:                                                   │
│  - Tuesday 2-4pm: FREE ✓                                                    │
│  - Wednesday 10am-12pm: BUSY (another meeting)                             │
│  - Thursday after 3pm: FREE ✓                                               │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR ASKS USER                                  │
│                                                                              │
│  "I found Lisa's email about the team sync. Based on her availability      │
│   and your calendar, you're both free:                                      │
│   - Tuesday 2-4pm ✓                                                         │
│   - Thursday after 3pm ✓                                                    │
│                                                                              │
│   Which time works best?"                                                   │
│                                                                              │
│  clarification: {                                                           │
│    "question": "Which time slot?",                                          │
│    "options": ["Tuesday 2pm", "Thursday 3pm"]                              │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
                    User: "Tuesday 2pm, make it 1 hour"
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ENTITY RESOLUTION                                       │
│                                                                              │
│  Resolve attendee emails from entities table:                               │
│  - Lisa → lisa@company.com                                                  │
│  - John → john@company.com                                                  │
│  - Sarah → sarah@company.com                                                │
│  - Mike → mike@company.com                                                  │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PREPARE ACTION                                          │
│                                                                              │
│  execute_action:                                                            │
│  {                                                                           │
│    "action_type": "create_calendar_event",                                  │
│    "params": {                                                              │
│      "title": "Team Sync - Roadmap Discussion",                            │
│      "description": "Sync to discuss the roadmap as mentioned by Lisa",   │
│      "start": "2024-01-16T14:00:00",                                       │
│      "end": "2024-01-16T15:00:00",                                         │
│      "attendees": [                                                         │
│        "lisa@company.com",                                                  │
│        "john@company.com",                                                  │
│        "sarah@company.com",                                                 │
│        "mike@company.com"                                                   │
│      ],                                                                      │
│      "create_meet_link": true                                               │
│    },                                                                        │
│    "confirm_first": true                                                    │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONFIRMATION & EXECUTION                                │
│                                                                              │
│  User confirms → Action Executor calls:                                     │
│                                                                              │
│  POST /users/usr_123/calendar/events                                        │
│  {                                                                           │
│    "title": "Team Sync - Roadmap Discussion",                               │
│    "start": "2024-01-16T14:00:00",                                          │
│    "end": "2024-01-16T15:00:00",                                            │
│    "attendees": ["lisa@...", "john@...", "sarah@...", "mike@..."],         │
│    "create_meet_link": true                                                 │
│  }                                                                           │
│                                                                              │
│  Response:                                                                  │
│  {                                                                           │
│    "id": "evt_789",                                                         │
│    "url": "https://calendar.google.com/event?id=xyz",                      │
│    "meet_link": "https://meet.google.com/abc-def-ghi"                      │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FINAL RESPONSE                                          │
│                                                                              │
│  "Meeting scheduled! 📅                                                     │
│                                                                              │
│   **Team Sync - Roadmap Discussion**                                        │
│   Tuesday, Jan 16 at 2:00 PM (1 hour)                                       │
│                                                                              │
│   Attendees: Lisa, John, Sarah, Mike                                        │
│   Google Meet: https://meet.google.com/abc-def-ghi                         │
│                                                                              │
│   Calendar invites sent to all attendees."                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Use Case 4: Create Document from Multiple Sources

### Scenario
User wants to create a project summary document pulling information from emails, Jira, and existing documents.

### User Input
```
"Create a project status report for the Alpha project including all recent updates"
```

### Technical Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MULTI-SOURCE CONTEXT GATHERING                          │
└─────────────────────────────────────────────────────────────────────────────┘

Parallel retrieval:

1. Jira Tasks:
   SELECT * FROM knowledge_items
   WHERE source_type = 'jira'
   AND metadata->>'project_key' = 'ALPHA'
   ORDER BY source_updated_at DESC

   Results: 15 tasks with status breakdown

2. Recent Emails:
   Semantic search: "Alpha project update status"
   Results: 8 relevant email threads

3. Existing Documents:
   Semantic search: "Alpha project"
   Results: 3 related docs (PRD, Architecture, Timeline)

4. Calendar Events:
   Recent/upcoming Alpha meetings
   Results: 2 past meetings with notes

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DELEGATE TO DOCUMENT AGENT                              │
│                                                                              │
│  DocumentAgent Task:                                                        │
│  "Create comprehensive status report from context"                          │
│                                                                              │
│  Context provided:                                                          │
│  - Jira: 15 tasks (10 done, 3 in progress, 2 blocked)                      │
│  - Emails: Key decisions, stakeholder feedback                              │
│  - Docs: Original requirements, architecture decisions                      │
│  - Meetings: Action items, discussions                                      │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      DOCUMENT GENERATION                                     │
│                                                                              │
│  LLM generates structured document:                                         │
│                                                                              │
│  # Alpha Project Status Report                                              │
│  Generated: January 15, 2024                                                │
│                                                                              │
│  ## Executive Summary                                                       │
│  Project is 67% complete with 2 blockers requiring attention...            │
│                                                                              │
│  ## Progress Overview                                                       │
│  | Status | Count | Percentage |                                            │
│  |--------|-------|------------|                                            │
│  | Done | 10 | 67% |                                                        │
│  | In Progress | 3 | 20% |                                                  │
│  | Blocked | 2 | 13% |                                                      │
│                                                                              │
│  ## Key Accomplishments                                                     │
│  - User authentication module completed (from Jira)                        │
│  - API integration approved by stakeholders (from email)                   │
│  - Architecture review passed (from meeting notes)                         │
│                                                                              │
│  ## Current Blockers                                                        │
│  1. ALPHA-23: Waiting on vendor API documentation                          │
│  2. ALPHA-27: Design approval pending from client                          │
│                                                                              │
│  ## Upcoming Milestones                                                     │
│  - Beta release: February 15 (from timeline doc)                           │
│  - Client demo: February 20 (from calendar)                                │
│                                                                              │
│  ## Risks & Mitigations                                                     │
│  [Extracted from email discussions]                                        │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ASK USER FOR DETAILS                                    │
│                                                                              │
│  "I've drafted a status report for Alpha project. It includes:              │
│   - Progress: 67% complete (10/15 tasks done)                               │
│   - 2 blockers identified                                                   │
│   - Key accomplishments from the past 2 weeks                               │
│   - Upcoming milestones                                                     │
│                                                                              │
│   Would you like me to:                                                     │
│   1. Add more detail to any section?                                        │
│   2. Include specific team member contributions?                            │
│   3. Add budget/resource information?                                       │
│   4. Save it to Google Drive?"                                              │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
                    User: "Add team contributions and save to Drive"
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ENHANCED DOCUMENT                                       │
│                                                                              │
│  Additional query for team data:                                            │
│  SELECT assignee, COUNT(*), status FROM jira_tasks                         │
│  WHERE project = 'ALPHA' GROUP BY assignee, status                         │
│                                                                              │
│  Added section:                                                             │
│  ## Team Contributions                                                      │
│  | Member | Completed | In Progress |                                       │
│  |--------|-----------|-------------|                                       │
│  | John | 4 | 1 |                                                           │
│  | Sarah | 3 | 1 |                                                          │
│  | Mike | 3 | 1 |                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SAVE TO GDRIVE                                          │
│                                                                              │
│  execute_action:                                                            │
│  {                                                                           │
│    "action_type": "create_document",                                        │
│    "params": {                                                              │
│      "title": "Alpha Project Status Report - Jan 2024",                    │
│      "content": "{markdown_content}",                                       │
│      "folder": "/Projects/Alpha/Reports",                                  │
│      "format": "google_doc"                                                │
│    }                                                                         │
│  }                                                                           │
│                                                                              │
│  External API:                                                              │
│  POST /users/usr_123/documents/create                                       │
│  Response: {"id": "doc_xyz", "url": "https://docs.google.com/..."}        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Use Case 5: Find and Summarize Project Status

### Scenario
User asks a question about a project they haven't worked on recently.

### User Input
```
"What's the latest on the Phoenix project? I haven't been involved for a few weeks"
```

### Technical Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BROAD CONTEXT SEARCH                                 │
└─────────────────────────────────────────────────────────────────────────────┘

Search across ALL sources for "Phoenix":

1. JIRA:
   - 8 tasks updated in last 2 weeks
   - 3 moved to Done
   - 1 new blocker added

2. GMAIL:
   - 5 email threads mentioning Phoenix
   - Latest: "Phoenix deployment schedule" (yesterday)

3. GDRIVE:
   - 2 documents updated
   - "Phoenix_Architecture_v3.pdf" modified 3 days ago

4. CALENDAR:
   - "Phoenix Go-Live Planning" meeting happened 5 days ago
   - Next: "Phoenix UAT Kickoff" in 2 days

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      INTELLIGENT SUMMARY                                     │
│                                                                              │
│  LLM synthesizes all context:                                               │
│                                                                              │
│  "Here's what's happened with Phoenix in the last 2 weeks:                  │
│                                                                              │
│   **Progress:**                                                             │
│   - 3 tasks completed (API endpoints, database migration, logging)         │
│   - Architecture document updated with new caching strategy                 │
│                                                                              │
│   **Current Status:**                                                       │
│   - 1 blocker: PHOENIX-45 - Third-party service rate limiting              │
│   - UAT kickoff scheduled for Thursday                                      │
│                                                                              │
│   **Key Decisions (from emails):**                                          │
│   - Deployment moved to AWS instead of GCP (decision by Sarah)             │
│   - Go-live date confirmed: February 28                                     │
│                                                                              │
│   **Recent Meeting (5 days ago):**                                          │
│   - Discussed deployment timeline                                           │
│   - Action item for you: Review security checklist                         │
│                                                                              │
│   Would you like me to:                                                     │
│   - Show details on any specific area?                                      │
│   - Find the security checklist you need to review?                        │
│   - Add you to the UAT kickoff meeting?"                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Use Case 6: Follow-up Reminder from Past Conversation

### Scenario
User mentioned something in a past conversation and AI proactively helps.

### User Input
```
"Remind me what I needed to follow up on from last week"
```

### Technical Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EPISODIC MEMORY SEARCH                                  │
└─────────────────────────────────────────────────────────────────────────────┘

Query chat_messages for past week:

SELECT * FROM chat_messages
WHERE user_id = 'usr_123'
AND created_at > NOW() - INTERVAL '7 days'
AND (content LIKE '%follow up%'
     OR content LIKE '%remind%'
     OR content LIKE '%todo%'
     OR content LIKE '%action item%')

Results:
┌────────────────────────────────────────────────────────────────────────────┐
│ Session: sess_abc (3 days ago)                                             │
│ Context: Discussion about client proposal                                  │
│ AI said: "I'll remind you to send the updated proposal to                 │
│           client@company.com by Friday"                                    │
│ Status: NOT DONE (no email sent detected)                                 │
└────────────────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────────────┐
│ Session: sess_def (5 days ago)                                             │
│ Context: Jira task creation                                                │
│ AI said: "Created PROJ-55. You mentioned you'd assign it after            │
│           checking with Mike"                                              │
│ Status: PROJ-55 still unassigned                                          │
└────────────────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────────────┐
│ Session: sess_ghi (6 days ago)                                             │
│ Context: Meeting scheduling                                                │
│ AI said: "Meeting scheduled. You wanted to prepare slides beforehand"     │
│ Status: Meeting is tomorrow, no slides document found                     │
└────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CROSS-REFERENCE WITH CURRENT STATE                      │
│                                                                              │
│  For each reminder, check if action was taken:                              │
│                                                                              │
│  1. Proposal email:                                                         │
│     - Search sent emails for "proposal" to client@company.com              │
│     - Result: NOT FOUND → Still needs to be done                           │
│                                                                              │
│  2. PROJ-55 assignment:                                                     │
│     - Check Jira for PROJ-55 assignee                                      │
│     - Result: Unassigned → Still needs to be done                          │
│                                                                              │
│  3. Meeting slides:                                                         │
│     - Search GDrive for recent presentation                                │
│     - Result: No slides found → Urgent (meeting tomorrow)                  │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RESPONSE                                                │
│                                                                              │
│  "Here are your pending follow-ups from last week:                          │
│                                                                              │
│   🔴 **URGENT - Meeting slides needed**                                     │
│   Your meeting with the design team is tomorrow at 10am.                   │
│   You mentioned preparing slides. Want me to help create them?             │
│                                                                              │
│   🟡 **Send updated proposal**                                              │
│   You were going to send the revised proposal to client@company.com        │
│   by Friday (today). Should I help draft the email?                        │
│                                                                              │
│   🟢 **Assign PROJ-55**                                                     │
│   Task 'API Documentation' is still unassigned. You wanted to check       │
│   with Mike first. Should I assign it to him now?                          │
│                                                                              │
│   What would you like to tackle first?"                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Use Case 7: Onboard New Team Member Context

### Scenario
User wants to bring a new team member up to speed on a project.

### User Input
```
"Generate an onboarding summary for Alex who's joining the Platform team"
```

### Technical Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      COMPREHENSIVE CONTEXT GATHERING                         │
└─────────────────────────────────────────────────────────────────────────────┘

1. Project Overview (GDrive):
   - PRD documents
   - Architecture docs
   - Team wiki pages

2. Current Work (Jira):
   - Active sprints
   - Backlog priorities
   - Team assignments

3. Key People (Entities):
   - Team members
   - Stakeholders
   - Their roles/responsibilities

4. Recent Decisions (Email + Meetings):
   - Important discussions
   - Decision log
   - Context for current direction

5. Recurring Events (Calendar):
   - Team meetings
   - Standups
   - Reviews

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      GENERATE ONBOARDING DOC                                 │
│                                                                              │
│  # Platform Team Onboarding - Alex                                          │
│                                                                              │
│  ## Team Overview                                                           │
│  The Platform team builds core infrastructure...                           │
│                                                                              │
│  ## Key People                                                              │
│  - **Sarah** (Tech Lead) - Architecture decisions, code reviews            │
│  - **John** (Senior Dev) - API development, mentorship                     │
│  - **Mike** (DevOps) - CI/CD, deployments                                  │
│  - **You report to**: David (Engineering Manager)                          │
│                                                                              │
│  ## Current Projects                                                        │
│  1. **API Gateway Migration** (Priority: High)                             │
│     - Moving from Kong to custom solution                                  │
│     - Your likely first task: PLAT-89 (auth middleware)                   │
│                                                                              │
│  2. **Monitoring Overhaul** (Priority: Medium)                             │
│     - Implementing distributed tracing                                     │
│                                                                              │
│  ## Key Documents to Read                                                   │
│  - [Architecture Overview](link)                                           │
│  - [API Design Guidelines](link)                                           │
│  - [Deployment Runbook](link)                                              │
│                                                                              │
│  ## Recurring Meetings                                                      │
│  - Daily Standup: 9:30am                                                   │
│  - Sprint Planning: Monday 2pm                                             │
│  - Tech Review: Thursday 3pm                                               │
│                                                                              │
│  ## Recent Important Decisions                                              │
│  - Switched to Go for new services (decided Jan 5)                        │
│  - Adopting OpenTelemetry standard (decided Jan 10)                       │
│                                                                              │
│  ## First Week Checklist                                                    │
│  [ ] Set up dev environment (see wiki)                                     │
│  [ ] Get access to AWS, GitHub, Jira                                       │
│  [ ] 1:1 with Sarah (scheduled for Tuesday)                               │
│  [ ] Pick up PLAT-89 starter task                                         │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ACTIONS OFFERED                                         │
│                                                                              │
│  "I've created an onboarding summary for Alex. Would you like me to:       │
│                                                                              │
│   1. Save this to Google Drive and share with Alex                         │
│   2. Schedule a welcome meeting with the team                              │
│   3. Assign PLAT-89 to Alex as a starter task                              │
│   4. Send Alex an email with this information"                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Use Case 8: Weekly Report Generation

### Scenario
User needs to create their weekly status report.

### User Input
```
"Help me write my weekly report for this week"
```

### Technical Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AUTOMATIC DATA GATHERING                                │
└─────────────────────────────────────────────────────────────────────────────┘

Time filter: This week (Mon-Fri)

1. Tasks Completed (Jira):
   SELECT * FROM knowledge_items
   WHERE source = 'jira'
   AND metadata->>'assignee' = user_email
   AND metadata->>'status' = 'Done'
   AND source_updated_at > start_of_week

   Results: 5 tasks completed

2. Emails Sent (Gmail):
   Important threads, decisions made

3. Meetings Attended (Calendar):
   With notes and outcomes

4. Documents Created/Updated (GDrive):
   Contributions to documentation

5. Code Contributions (if GitHub integrated):
   PRs merged, reviews done

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      GENERATED WEEKLY REPORT                                 │
│                                                                              │
│  # Weekly Report - Week of Jan 15, 2024                                     │
│                                                                              │
│  ## Accomplishments                                                         │
│                                                                              │
│  ### Tasks Completed                                                        │
│  - [PROJ-42] Implemented user authentication ✓                             │
│  - [PROJ-45] Fixed payment processing bug ✓                                │
│  - [PROJ-48] Updated API documentation ✓                                   │
│  - [PROJ-51] Code review for Sarah's PR ✓                                  │
│  - [PROJ-53] Database optimization ✓                                       │
│                                                                              │
│  ### Key Meetings                                                           │
│  - Sprint Planning (Mon) - Committed to 5 story points                     │
│  - Architecture Review (Wed) - Approved caching strategy                   │
│  - Client Demo (Thu) - Positive feedback on new features                   │
│                                                                              │
│  ### Collaboration                                                          │
│  - Helped John debug API timeout issues                                    │
│  - Reviewed 3 PRs for team members                                         │
│                                                                              │
│  ## In Progress                                                             │
│  - [PROJ-55] Payment gateway integration (70% done)                        │
│  - [PROJ-58] Performance testing setup                                     │
│                                                                              │
│  ## Blockers                                                                │
│  - Waiting on vendor API credentials for PROJ-55                           │
│                                                                              │
│  ## Next Week Plans                                                         │
│  - Complete payment gateway integration                                    │
│  - Start user notification system                                          │
│  - Attend AWS training (Thursday)                                          │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      USER CUSTOMIZATION                                      │
│                                                                              │
│  "Here's your weekly report draft. I found:                                 │
│   - 5 tasks completed                                                       │
│   - 3 key meetings                                                          │
│   - 1 blocker                                                               │
│                                                                              │
│   Anything you'd like to add or modify?                                     │
│   Should I email this to your manager (David)?"                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Use Case 9: Cross-Platform Task Handoff

### Scenario
User receives an email request and needs to create a task, update documentation, and notify the team.

### User Input
```
"The client just emailed about adding dark mode. Create a task, update the roadmap doc, and let the team know"
```

### Technical Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      MULTI-ACTION ORCHESTRATION                              │
└─────────────────────────────────────────────────────────────────────────────┘

Intent Analysis:
- Action 1: Create Jira task (from email)
- Action 2: Update document (roadmap)
- Action 3: Send notification (email to team)

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      STEP 1: RETRIEVE EMAIL CONTEXT                          │
└─────────────────────────────────────────────────────────────────────────────┘

retrieve_context: "client email dark mode"

Results:
┌────────────────────────────────────────────────────────────────────────────┐
│ From: client@acme.com                                                      │
│ Subject: Feature Request - Dark Mode                                       │
│ "Hi, Our users have been requesting dark mode support. Can you add this   │
│  to the mobile app? Priority: High. Deadline: End of Q1 if possible.      │
│  Let me know the estimate. Thanks, Client"                                │
└────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      STEP 2: CREATE JIRA TASK                                │
└─────────────────────────────────────────────────────────────────────────────┘

TaskAgent extracts and creates:
{
  "project_key": "MOBILE",
  "type": "story",
  "summary": "Implement Dark Mode Support",
  "description": "Add dark mode theme option to mobile app.\n\n
                  **Source:** Client request (email Jan 15)\n
                  **Priority:** High\n
                  **Requested deadline:** End of Q1\n\n
                  **Requirements:**\n
                  - System-wide dark theme\n
                  - User preference toggle\n
                  - Respect system settings",
  "priority": "high",
  "labels": ["client-request", "ui", "q1"]
}

→ Created: MOBILE-67

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      STEP 3: UPDATE ROADMAP DOCUMENT                         │
└─────────────────────────────────────────────────────────────────────────────┘

retrieve_context: "roadmap document mobile app"

Found: "Mobile_App_Roadmap_2024.docx" in GDrive

DocumentAgent updates:
- Adds new row to Q1 features table
- Includes task link MOBILE-67
- Notes client priority

Action: update_document
{
  "document_id": "doc_roadmap_xyz",
  "changes": {
    "section": "Q1 Features",
    "add_row": {
      "feature": "Dark Mode",
      "priority": "High",
      "status": "Planned",
      "jira": "MOBILE-67",
      "notes": "Client requested, high priority"
    }
  }
}

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      STEP 4: NOTIFY TEAM                                     │
└─────────────────────────────────────────────────────────────────────────────┘

EmailAgent drafts notification:

To: mobile-team@company.com
Subject: New High Priority Feature: Dark Mode [MOBILE-67]

"Hi team,

We've received a high-priority request from Acme (our client) to add
dark mode support to the mobile app.

**Task:** [MOBILE-67](link) - Implement Dark Mode Support
**Priority:** High
**Requested deadline:** End of Q1

I've updated the roadmap document with this addition.

Please review and let's discuss estimation in tomorrow's standup.

Thanks"

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CONFIRMATION REQUEST                                    │
│                                                                              │
│  "I've prepared the following actions:                                      │
│                                                                              │
│   ✓ Created Jira task MOBILE-67: 'Implement Dark Mode Support'             │
│   ✓ Updated Mobile_App_Roadmap_2024 with new Q1 feature                    │
│   ⏳ Ready to send team notification email                                  │
│                                                                              │
│   Should I send the notification to mobile-team@company.com?"              │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                            User: "Yes, send it"
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      EXECUTE ALL ACTIONS                                     │
│                                                                              │
│  1. POST /jira/issues → MOBILE-67 created ✓                                │
│  2. PUT /documents/doc_roadmap_xyz → Updated ✓                             │
│  3. POST /emails/send → Team notified ✓                                    │
│                                                                              │
│  Final Response:                                                            │
│  "All done!                                                                 │
│   - Created [MOBILE-67](link): Dark Mode Support                           │
│   - Updated [Roadmap](link) with Q1 feature                                │
│   - Notified mobile-team@company.com                                       │
│                                                                              │
│   Should I also reply to the client with an estimate timeline?"            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Use Case 10: Smart Email Categorization & Actions

### Scenario
User wants to process their inbox efficiently with AI suggestions.

### User Input
```
"Go through my unread emails and suggest actions for each"
```

### Technical Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      FETCH UNREAD EMAILS                                     │
└─────────────────────────────────────────────────────────────────────────────┘

GET /users/usr_123/emails?is_read=false&limit=10

Results: 8 unread emails

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      AI CATEGORIZATION & ANALYSIS                            │
└─────────────────────────────────────────────────────────────────────────────┘

For each email, analyze:
- Sender importance (from entity history)
- Content type (request, FYI, action needed)
- Urgency signals
- Related context in system

Results:

┌────────────────────────────────────────────────────────────────────────────┐
│ 📧 Email 1: "Urgent: Server Down" from ops@company.com                    │
│ Category: 🔴 URGENT - ACTION REQUIRED                                      │
│ Suggested Actions:                                                         │
│ - Check related Jira incidents                                             │
│ - Found: 2 related incidents from last month                              │
│ - Quick reply template ready                                               │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ 📧 Email 2: "Meeting Notes - Product Review" from sarah@company.com       │
│ Category: 📋 FYI - NO ACTION NEEDED                                        │
│ Suggested Actions:                                                         │
│ - Archive after reading                                                    │
│ - Key points extracted and saved                                          │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ 📧 Email 3: "Quote Request" from vendor@external.com                      │
│ Category: 📝 RESPONSE NEEDED                                               │
│ Suggested Actions:                                                         │
│ - Draft reply with our requirements                                        │
│ - Found: Previous vendor communications for context                       │
│ - Deadline: They asked for response by Friday                             │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ 📧 Email 4: "Invitation: Team Lunch" from hr@company.com                  │
│ Category: 📅 CALENDAR                                                      │
│ Suggested Actions:                                                         │
│ - Accept/Decline calendar invite                                           │
│ - You're free at that time                                                │
└────────────────────────────────────────────────────────────────────────────┘

... (4 more emails analyzed)

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      SUMMARY RESPONSE                                        │
│                                                                              │
│  "I've analyzed your 8 unread emails:                                       │
│                                                                              │
│   🔴 **Urgent (1)**                                                         │
│   - Server Down alert from Ops - needs immediate attention                 │
│                                                                              │
│   📝 **Response Needed (3)**                                                │
│   - Vendor quote request (deadline: Friday)                                │
│   - Client question about timeline                                         │
│   - Team lead asking for status update                                     │
│                                                                              │
│   📅 **Calendar (1)**                                                       │
│   - Team lunch invitation (you're free)                                    │
│                                                                              │
│   📋 **FYI Only (3)**                                                       │
│   - Meeting notes, newsletters, automated reports                          │
│                                                                              │
│   Would you like me to:                                                     │
│   1. Handle the urgent server issue first                                  │
│   2. Draft replies for the 3 pending responses                             │
│   3. Accept the lunch invitation                                           │
│   4. Archive the FYI emails"                                               │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                            User: "Draft the replies and accept lunch"
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      BATCH ACTIONS                                           │
│                                                                              │
│  EmailAgent drafts 3 replies with context...                               │
│  Calendar action accepts lunch invite...                                   │
│                                                                              │
│  "Done! Here are the draft replies for your review:                         │
│                                                                              │
│   1. **To Vendor:** [Draft with pricing requirements]                      │
│   2. **To Client:** [Timeline update based on Jira data]                   │
│   3. **To Team Lead:** [Status summary auto-generated]                     │
│                                                                              │
│   ✓ Accepted team lunch for Thursday 12pm                                  │
│                                                                              │
│   Review the drafts and I'll send when you approve."                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Summary: Agent Interaction Patterns

### Common Patterns Across Use Cases

| Pattern | Description | Use Cases |
|---------|-------------|-----------|
| **Context First** | Always retrieve relevant context before action | All |
| **Multi-Source Merge** | Combine data from Gmail, GDrive, Jira, Calendar | 1, 2, 4, 5, 7 |
| **Clarification Loop** | Ask user when information is missing | 1, 3, 6 |
| **Confirmation Gate** | Require confirmation before destructive actions | 1, 2, 3, 9 |
| **Batch Processing** | Handle multiple items efficiently | 8, 10 |
| **Entity Resolution** | Map names to emails/IDs from entity graph | 1, 3, 7 |
| **Preference Learning** | Apply learned user preferences | 2, 8 |
| **Cross-Platform Sync** | Update multiple systems atomically | 9 |

### Embedding Usage Summary

| Source | Embedding Strategy | Retrieval Method |
|--------|-------------------|------------------|
| **Emails** | Summary embeddings | Semantic + entity filter |
| **Documents** | Chunked full-text | Semantic + metadata |
| **Jira Tasks** | Full task embeddings | Semantic + project filter |
| **Calendar** | Light index | Time-based + attendee match |
| **Entities** | Name + context | Exact match + fuzzy search |

### Agent Responsibilities

| Agent | Primary Tasks | Tools Used |
|-------|--------------|------------|
| **Orchestrator** | Intent classification, context retrieval, coordination | retrieve_context, delegate_to_specialist, ask_user, execute_action |
| **EmailAgent** | Draft emails, summarize threads, suggest replies | draft_email, summarize_thread, extract_action_items |
| **TaskAgent** | Create/update Jira tasks, extract tasks from text | extract_tasks, create_task, find_related_tasks |
| **DocumentAgent** | Create/update documents, summarize content | create_document, update_section, summarize_document |
| **ActionExecutor** | Execute confirmed actions via external APIs | (internal execution only) |

---

*Document Version: 1.0*
*Related: TECHNICAL_SPECIFICATION.md, INTEGRATION_AND_AGENTS.md*

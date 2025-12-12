# AI Employee V2 - System Architecture & Query Processing Flow

This document explains the complete flow of how a user query is processed, from receiving the request to generating a response and storing data for future retrieval.

---

## Table of Contents

1. [Overview](#overview)
2. [High-Level Flow Diagram](#high-level-flow-diagram)
3. [Entry Point: Chat API](#entry-point-chat-api)
4. [Context Retrieval System](#context-retrieval-system)
5. [Memory Systems](#memory-systems)
6. [Relevance Scoring & Weightage](#relevance-scoring--weightage)
7. [Orchestrator Agent](#orchestrator-agent)
8. [LLM Response Formulation](#llm-response-formulation)
9. [Data Storage for Future Retrieval](#data-storage-for-future-retrieval)
10. [Complete Query Flow](#complete-query-flow)
11. [Database Models](#database-models)
12. [Configuration](#configuration)

---

## Overview

The AI Employee V2 system processes user queries through a sophisticated multi-stage pipeline:

```
User Query → Context Retrieval → Agent Orchestration → LLM Processing → Response + Storage
```

**Key Components:**
- **Chat API** - Entry point for all user interactions
- **Context Service** - Retrieves relevant information from multiple sources
- **Orchestrator Agent** - Coordinates the entire response generation
- **Specialist Agents** - Handle specific tasks (email, documents, tasks)
- **Memory Systems** - Store and retrieve different types of information
- **LLM Integration** - OpenAI models for understanding and generation

---

## High-Level Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER QUERY                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CHAT API (/api/chat)                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Get/Create  │  │ Get/Create  │  │    Load     │  │  Load Previous      │ │
│  │    User     │→ │   Session   │→ │   History   │→ │  Context Items      │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ORCHESTRATOR AGENT                                   │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        TOOL EXECUTION LOOP                           │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │    │
│  │  │  retrieve_   │  │  delegate_   │  │   ask_user   │               │    │
│  │  │   context    │  │  specialist  │  │              │               │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │    │
│  │  │   prepare_   │  │ find_entity  │  │ get_recent_  │               │    │
│  │  │    action    │  │              │  │ conversations│               │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐
│   CONTEXT SERVICE   │ │  SPECIALIST AGENTS  │ │   ENTITY SERVICE    │
│  ┌───────────────┐  │ │  ┌───────────────┐  │ │  ┌───────────────┐  │
│  │   Semantic    │  │ │  │  Email Agent  │  │ │  │ Entity Lookup │  │
│  │    Search     │  │ │  └───────────────┘  │ │  └───────────────┘  │
│  └───────────────┘  │ │  ┌───────────────┐  │ │  ┌───────────────┐  │
│  ┌───────────────┐  │ │  │Document Agent │  │ │  │   Extraction  │  │
│  │   Episodic    │  │ │  └───────────────┘  │ │  └───────────────┘  │
│  │    Memory     │  │ │  ┌───────────────┐  │ └─────────────────────┘
│  └───────────────┘  │ │  │  Task Agent   │  │
│  ┌───────────────┐  │ │  └───────────────┘  │
│  │  Full-Text    │  │ └─────────────────────┘
│  │    Search     │  │
│  └───────────────┘  │
└─────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LLM RESPONSE GENERATION                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  System Prompt + Context Items + Entities + Conversation History    │    │
│  │                              ↓                                      │    │
│  │                    OpenAI GPT-4o-mini/GPT-4o                        │    │
│  │                              ↓                                      │    │
│  │                    Final Response + Actions                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA STORAGE                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Store     │  │   Store     │  │   Learn     │  │  Update Session     │ │
│  │  Message    │  │  Actions    │  │ Preferences │  │     Context         │ │
│  │    (DB)     │  │  (Redis)    │  │    (DB)     │  │     (Redis)         │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CHAT RESPONSE                                      │
│  {session_id, response, context_used, pending_actions, clarification...}    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Entry Point: Chat API

**File:** `app/api/chat.py`
**Endpoint:** `POST /chat`

### Request Flow

```python
ChatRequest {
    user_id: str           # External user identifier
    message: str           # User's query
    session_id: str?       # Optional session for continuity
    confirm_actions: list? # Action IDs to execute
    clarification_response: str?  # Response to clarification question
}
```

### Processing Steps

1. **User Management**
   ```python
   user = await get_or_create_user(db, request.user_id)
   ```
   - Looks up user by `external_user_id`
   - Creates new user if not found

2. **Session Management**
   ```python
   session = await get_or_create_session(db, user, request.session_id)
   ```
   - Retrieves existing session or creates new one
   - Sessions track conversation continuity

3. **Action Confirmation** (if `confirm_actions` provided)
   ```python
   pending = await working_memory.get_pending_actions(user_id, session_id)
   results = await executor.execute_batch(user_id, actions_to_execute)
   ```
   - Retrieves pending actions from Redis
   - Executes confirmed actions via external APIs

4. **Load Conversation History**
   ```python
   # Last 10 messages for context
   history_messages = await db.execute(
       select(ChatMessage)
       .where(session_id == session.id)
       .order_by(created_at.desc())
       .limit(10)
   )
   ```

5. **Load Previous Context** (for follow-up messages)
   ```python
   # Get context from most recent assistant message
   for m in reversed(history_messages):
       if m.role == "assistant" and m.context_items:
           context_ids = [c.get("id") for c in m.context_items]
           items = await db.execute(
               select(KnowledgeItem).where(id.in_(context_ids))
           )
           previous_context_items = [format_item(i) for i in items]
           break
   ```

6. **Build Agent State**
   ```python
   state = AgentState(
       user_id=str(user.id),
       session_id=str(session.id),
       message=request.message,
       conversation_history=[...],
       context_items=previous_context_items,
   )
   ```

---

## Context Retrieval System

**File:** `app/services/context_service.py`

The context service retrieves relevant information using multiple retrieval strategies.

### Retrieval Methods

#### 1. Semantic Search (Primary)

Uses embedding vectors for similarity matching.

```python
async def _semantic_search(self, db, user_id, query, sources, time_filter, limit):
    # 1. Create query embedding
    query_embedding = await self.embedding_service.create_embedding(query)

    # 2. Vector similarity search using pgvector
    stmt = select(
        KnowledgeItem,
        Embedding.chunk_text,
        (1 - Embedding.embedding.cosine_distance(query_embedding)).label("similarity")
    ).join(Embedding)
    .where(KnowledgeItem.user_id == user_id)
    .order_by(desc("similarity"))
    .limit(limit)

    # 3. Return items with similarity scores
    return [{"item": item, "semantic_score": similarity} for item, similarity in results]
```

**How Embeddings Work:**
- Text is converted to 1536-dimensional vectors using OpenAI's `text-embedding-3-small`
- Similar content has vectors that are close together in vector space
- Cosine similarity measures how close two vectors are (0 = unrelated, 1 = identical)

#### 2. Full-Text Search (PostgreSQL FTS)

```python
async def _fulltext_search(self, db, user_id, query, limit):
    # Uses PostgreSQL's built-in text search
    tsquery = func.plainto_tsquery('english', query)
    tsvector = func.to_tsvector('english', KnowledgeItem.title + ' ' + KnowledgeItem.content)

    stmt = select(KnowledgeItem, func.ts_rank(tsvector, tsquery))
    .where(tsvector.op('@@')(tsquery))
    .order_by(desc(func.ts_rank(tsvector, tsquery)))
```

#### 3. Entity-Based Search

```python
async def _entity_search(self, db, user_id, entity_filter, limit):
    # Find entity by name
    entity = await entity_service.find_entity(db, user_id, entity_filter)

    # Get all knowledge items mentioning this entity
    stmt = select(KnowledgeItem)
    .join(EntityMention)
    .where(EntityMention.entity_id == entity.id)
```

#### 4. Keyword Search (Fallback)

```python
async def _keyword_search(self, db, user_id, query, limit):
    # Extract keywords (words >= 3 chars)
    keywords = [w for w in query.split() if len(w) >= 3][:5]

    # ILIKE search on title, content, summary
    conditions = [
        or_(
            KnowledgeItem.title.ilike(f"%{kw}%"),
            KnowledgeItem.content.ilike(f"%{kw}%"),
        )
        for kw in keywords
    ]
```

#### 5. Temporal Search (for "last", "latest", "recent" queries)

```python
async def _get_most_recent(self, db, user_id, sources, limit):
    # Direct date-based retrieval
    stmt = select(KnowledgeItem)
    .where(user_id == user_id)
    .order_by(source_created_at.desc())
    .limit(limit)

    # Balanced retrieval for multiple sources
    if len(sources) > 1:
        per_source_limit = max(2, limit // len(sources))
        for source in sources:
            # Query each source separately
            items_per_source = await query_source(source, per_source_limit)
```

### Content Type Auto-Detection

```python
CONTENT_TYPE_KEYWORDS = {
    "email": ["gmail", "outlook"],
    "document": ["gdrive", "onedrive", "document", "doc", "file"],
    "task": ["jira", "task", "ticket", "issue"],
    "meeting": ["calendar", "event", "meeting"],
}

def _detect_content_type_sources(self, query):
    query_lower = query.lower()
    detected = []
    for content_type, keywords in CONTENT_TYPE_KEYWORDS.items():
        if any(kw in query_lower for kw in keywords):
            detected.extend(SOURCE_MAPPING[content_type])
    return detected
```

### Combined Retrieval Flow

```python
async def retrieve_with_memory(self, db, user_id, query, session_id,
                                sources, time_filter, entity_filter,
                                include_episodic, limit):

    # 1. Auto-detect content type from query
    detected_sources = self._detect_content_type_sources(query)
    is_temporal = self._is_temporal_query(query)

    # 2. Disable episodic if specific content requested
    if detected_sources or is_temporal:
        include_episodic = False

    # 3. Get temporal results if applicable
    temporal_results = []
    if is_temporal:
        temporal_results = await self._get_most_recent(...)

    # 4. Get semantic search results
    base_results = await self._semantic_search(...)

    # 5. Combine temporal + semantic
    all_results = temporal_results + base_results

    # 6. Add entity search if filter provided
    if entity_filter:
        entity_results = await self._entity_search(...)
        all_results.extend(entity_results)

    # 7. Add full-text search results
    fts_results = await self._fulltext_search(...)
    all_results.extend(fts_results)

    # 8. Merge and deduplicate
    merged = self._merge_results(all_results)

    # 9. Calculate final relevance scores
    for item in merged:
        item["relevance_score"] = self._calculate_relevance(item)

    # 10. Add episodic memory if enabled
    if include_episodic:
        episodic = await self._get_episodic_memory(...)
        merged.extend(episodic)

    # 11. Sort by relevance and limit
    merged.sort(key=lambda x: x["relevance_score"], reverse=True)
    return merged[:limit]
```

---

## Memory Systems

The system uses four types of memory:

### 1. Semantic Memory (Long-term Knowledge)

**Storage:** PostgreSQL + pgvector

**What it stores:**
- Emails (Gmail, Outlook)
- Documents (Google Drive, OneDrive)
- Tasks (Jira)
- Calendar events

**How it works:**
```
Content → Chunking → Embedding → Vector Storage → Similarity Search
```

**Models:**
- `KnowledgeItem` - Main content storage
- `Embedding` - Vector embeddings (1536 dimensions)

### 2. Episodic Memory (Past Conversations)

**Storage:** PostgreSQL

**What it stores:**
- Past conversation sessions
- Previous questions and answers
- Context used in previous interactions

**How it works:**
```python
# Get relevant past conversations
sessions = await db.execute(
    select(ChatSession)
    .where(user_id == user_id)
    .order_by(updated_at.desc())
    .limit(5)
)

for session in sessions:
    messages = await get_session_messages(session.id, limit=20)
    # Score based on word overlap with current query
    overlap_score = calculate_word_overlap(query, messages)
```

**Relevance Calculation:**
```python
episodic_score = ((word_overlap / query_words) * 0.4 + recency * 0.3) * 0.5
# Capped at 0.5 so actual data always ranks higher
```

### 3. Entity Memory (Relationships)

**Storage:** PostgreSQL

**What it stores:**
- People (contacts, team members)
- Projects (Jira projects, folders)
- Topics (extracted from content)
- Companies

**Models:**
- `Entity` - Entity information
- `EntityMention` - Links entities to knowledge items

**How it works:**
```python
# Entity extraction from different sources
def extract_entities(item):
    if item.content_type == "email":
        # Extract from, to, cc
        entities = parse_email_headers(item.metadata)
    elif item.content_type == "task":
        # Extract project, assignee, reporter
        entities = parse_jira_fields(item.metadata)
    return entities

# Entity lookup
entity = await db.execute(
    select(Entity)
    .where(normalized_name.ilike(f"%{name.lower()}%"))
    .order_by(mention_count.desc())
)
```

### 4. Working Memory (Session State)

**Storage:** Redis

**What it stores:**
- Current session context
- Pending actions awaiting confirmation
- Cached user preferences
- Recently accessed items

**Key Structure:**
```
working:{user_id}:{session_id}:context        → Session state
working:{user_id}:{session_id}:pending_actions → Actions queue
working:{user_id}:preferences                  → User prefs cache
working:{user_id}:recent_items                 → Recent access
```

**TTL Values:**
- Session context: 30 minutes
- Preferences: 1 hour
- Recent items: 15 minutes

---

## Relevance Scoring & Weightage

**File:** `app/services/context_service.py` - `_calculate_relevance()`

### Scoring Formula

```python
final_score = (
    semantic_score * 0.5 +    # Base semantic similarity (50% weight)
    recency_score +           # Freshness bonus (0-0.2)
    entity_score +            # Entity match bonus (0-0.3)
    source_score +            # Source priority (0-0.1)
    fts_score                 # Full-text rank (0-0.1)
)
```

### Component Details

#### Semantic Score (50% weight)
```python
# Cosine similarity from embedding vectors
semantic_score = 1 - cosine_distance(query_embedding, item_embedding)
# Range: 0.0 to 1.0
# Example: 0.85 means 85% similar
```

#### Recency Score (up to 0.2)
```python
days_old = (now - item.source_created_at).days
recency_score = max(0, 0.2 - (days_old / 365) * 0.2)
# Today = 0.2, 6 months ago = 0.1, 1 year ago = 0.0
```

#### Entity Score (up to 0.3)
```python
# If query mentions entities that appear in item
entity_matches = intersection(query_entities, item_entities)
entity_score = min(0.3, len(entity_matches) * 0.1)
# 1 match = 0.1, 2 matches = 0.2, 3+ matches = 0.3
```

#### Source Priority Score (up to 0.1)
```python
SOURCE_PRIORITY = {
    "gmail": 0.10,      # Highest - most actionable
    "outlook": 0.10,
    "gdrive": 0.08,
    "onedrive": 0.08,
    "jira": 0.07,
    "calendar": 0.05,   # Lowest
}
```

#### Full-Text Search Score (up to 0.1)
```python
# PostgreSQL ts_rank score normalized
fts_score = min(0.1, ts_rank_value * 0.05)
```

### Example Calculation

```
Query: "What did Sarah say about the Q4 budget?"

Item: Email from Sarah about Q4 Planning
- Semantic similarity: 0.78
- Age: 5 days old → recency: 0.197
- Entity "Sarah" matched → entity: 0.1
- Source: gmail → source: 0.1
- FTS rank: 0.8 → fts: 0.04

Final Score = (0.78 * 0.5) + 0.197 + 0.1 + 0.1 + 0.04
            = 0.39 + 0.197 + 0.1 + 0.1 + 0.04
            = 0.827
```

### Special Cases

#### Temporal Queries
```python
# For "last email", "recent documents" etc.
if is_temporal_query:
    relevance_score = 0.9  # High fixed score
    # Results sorted by date, not semantic similarity
```

#### Episodic Memory Cap
```python
# Past conversations capped at 0.5
episodic_score = min(0.5, calculated_score)
# Ensures actual data always ranks higher than conversation history
```

---

## Orchestrator Agent

**File:** `app/agents/orchestrator.py`

The orchestrator is the main coordinator that decides how to respond to user queries.

### System Prompt Goals

1. Understand user intent
2. Retrieve relevant context
3. Delegate complex tasks to specialists
4. Ask clarifying questions when needed
5. Prepare and confirm actions

### Available Tools

| Tool | Purpose | Parameters |
|------|---------|------------|
| `retrieve_context` | Search knowledge base | query, sources, time_filter, entity_filter |
| `delegate_to_specialist` | Hand off to specialist | specialist, task, context_ids |
| `ask_user` | Request clarification | question, options, required_for |
| `prepare_action` | Queue action for confirmation | action_type, params, description |
| `find_entity` | Look up person/project | name |
| `get_recent_conversations` | Get past chat history | limit, include_context |

### Tool Execution Loop

```python
async def run_with_tools(self, state):
    messages = self.build_messages(state)

    for iteration in range(MAX_ITERATIONS):  # Max 10
        # 1. Call LLM with tools
        response = await self.chat(messages, use_tools=True)

        # 2. Check for tool calls
        if not response.tool_calls:
            # No more tools needed, return response
            return AgentResponse(message=response.content)

        # 3. Execute each tool
        for tool_call in response.tool_calls:
            tool = self.tools[tool_call.name]
            args = json.loads(tool_call.arguments)
            result = await tool.handler(state, **args)

            # 4. Add result to message thread
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })

        # 5. Continue loop for follow-up

    return final_response
```

### Tool Handlers

#### retrieve_context
```python
async def _handle_retrieve_context(self, state, query, sources, time_filter, entity_filter):
    result = await self.context_service.retrieve_with_memory(
        db=self.db,
        user_id=state.user_id,
        query=query,
        sources=sources,
        time_filter=time_filter,
        entity_filter=entity_filter,
        include_episodic=True,
        limit=10,
    )

    # Update state with retrieved context
    state.context_items.extend(result["items"])
    state.entities.extend(result["entities"])

    return {
        "found": result["total"],
        "items": [format_item(i) for i in result["items"][:5]],
        "entities": result["entities"],
    }
```

#### delegate_to_specialist
```python
async def _handle_delegate(self, state, specialist, task, context_ids):
    # Get relevant context items
    relevant_context = [
        item for item in state.context_items
        if item.get("id") in context_ids
    ]

    # Create specialist agent
    if specialist == "email":
        agent = EmailAgent(db=self.db)
    elif specialist == "document":
        agent = DocumentAgent(db=self.db)
    elif specialist == "task":
        agent = TaskAgent(db=self.db)

    # Run specialist
    response = await agent.run(specialist_state)

    # Merge pending actions
    state.pending_actions.extend(response.pending_actions)

    return {"specialist": specialist, "result": response.message}
```

#### ask_user
```python
async def _handle_ask_user(self, state, question, options, required_for):
    # Store clarification request in state
    state.metadata["needs_clarification"] = True
    state.metadata["clarification_question"] = question
    state.metadata["clarification_options"] = options

    return {"status": "question_prepared", "question": question}
```

#### prepare_action
```python
async def _handle_prepare_action(self, state, action_type, params, description):
    action = {
        "id": f"act_{uuid4()[:8]}",
        "type": action_type,  # send_email, create_task, etc.
        "params": params,
        "description": description,
        "status": "pending_confirmation",
    }

    state.pending_actions.append(action)

    return {"action_id": action["id"], "status": "prepared_for_confirmation"}
```

---

## LLM Response Formulation

**File:** `app/agents/base.py`

### Message Building

```python
def build_messages(self, state):
    messages = []

    # 1. System prompt
    messages.append({
        "role": "system",
        "content": self.system_prompt
    })

    # 2. Conversation history
    for msg in state.conversation_history[-10:]:
        messages.append({
            "role": msg["role"],
            "content": msg["content"]
        })

    # 3. Current message with context
    user_content = state.message

    # Add formatted context items
    if state.context_items:
        user_content += "\n\n## Relevant Context:\n"
        for item in state.context_items[:5]:
            user_content += f"\n[{item['source'].upper()}] {item['title']}\n"
            user_content += f"{item['summary'] or item['content'][:500]}\n"
            user_content += "---\n"

    # Add formatted entities
    if state.entities:
        user_content += "\n\n## Known Entities:\n"
        for entity in state.entities[:10]:
            user_content += f"- {entity['name']} ({entity['type']})"
            if entity.get('metadata', {}).get('email'):
                user_content += f": {entity['metadata']['email']}"
            user_content += "\n"

    messages.append({
        "role": "user",
        "content": user_content
    })

    return messages
```

### LLM Call

```python
async def chat(self, messages, use_tools=False):
    kwargs = {
        "model": self.model,  # gpt-4o-mini or gpt-4o
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 2000,
    }

    if use_tools and self.tools:
        kwargs["tools"] = [tool.schema for tool in self.tools.values()]
        kwargs["tool_choice"] = "auto"

    response = await openai.chat.completions.create(**kwargs)

    return {
        "content": response.choices[0].message.content,
        "tool_calls": response.choices[0].message.tool_calls,
        "tokens": response.usage.total_tokens,
    }
```

### Response Generation Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT TO LLM                              │
├─────────────────────────────────────────────────────────────────┤
│ System: You are an AI assistant that helps with email, docs...  │
├─────────────────────────────────────────────────────────────────┤
│ History: [Last 10 messages from conversation]                    │
├─────────────────────────────────────────────────────────────────┤
│ User: "What did Sarah say about the budget?"                    │
│                                                                  │
│ ## Relevant Context:                                             │
│ [GMAIL] Q4 Budget Discussion                                     │
│ Sarah mentioned we need to increase marketing spend by 15%...    │
│ ---                                                              │
│ [GDRIVE] Budget Spreadsheet Q4                                   │
│ Marketing: $50,000, Engineering: $120,000...                     │
│                                                                  │
│ ## Known Entities:                                               │
│ - Sarah Johnson (person): sarah@company.com                      │
│ - Q4 Budget (project)                                            │
├─────────────────────────────────────────────────────────────────┤
│ Tools: [retrieve_context, delegate_to_specialist, ask_user...]   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LLM PROCESSING                              │
│  - Understands query in context of conversation                  │
│  - References provided context items                             │
│  - Decides if tools needed or can answer directly                │
│  - Formulates natural language response                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        OUTPUT                                    │
│ "Based on the email from Sarah Johnson on December 3rd,          │
│  she mentioned that the marketing budget needs to increase       │
│  by 15% for Q4 to support the new product launch campaign.       │
│  The current budget spreadsheet shows $50,000 allocated          │
│  to marketing."                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Storage for Future Retrieval

### After Response Generation

```python
# In chat.py after orchestrator.run()

# 1. Store assistant message with context references
assistant_message = ChatMessage(
    session_id=session.id,
    user_id=user.id,
    role="assistant",
    content=response.message,
    context_items=[
        {"id": item.get("id"), "relevance": item.get("relevance_score")}
        for item in state.context_items
    ],
    pending_actions=response.pending_actions,
    tokens_used=response.tokens_used,
    model_used=response.model_used,
)
db.add(assistant_message)

# 2. Store pending actions in Redis for quick access
for action in response.pending_actions:
    await working_memory.add_pending_action(
        str(user.id), str(session.id), action
    )

# 3. Learn preferences from this interaction
await _learn_from_conversation(
    db=db,
    user=user,
    message=request.message,
    response_content=response.message,
    preference_service=preference_service,
)

# 4. Update session context in Redis
await working_memory.update_session_context(
    user_id=str(user.id),
    session_id=str(session.id),
    updates={
        "last_message": request.message,
        "last_response": response.message[:500],
        "entities_mentioned": [e.get("name") for e in state.entities[:5]],
        "context_used_count": len(state.context_items),
    }
)

# 5. Commit to database
await db.commit()
```

### Preference Learning

```python
async def _learn_from_conversation(db, user, message, response_content, preference_service):
    # Track message length preference
    msg_length = len(message.split())
    if msg_length < 10:
        await preference_service.update_preference(
            db, str(user.id), "interaction", "message_style", "brief"
        )
    elif msg_length > 50:
        await preference_service.update_preference(
            db, str(user.id), "interaction", "message_style", "detailed"
        )

    # Track topics of interest
    topic_keywords = {
        "email": ["email", "mail", "send", "reply", "inbox"],
        "calendar": ["meeting", "schedule", "calendar", "event"],
        "tasks": ["task", "jira", "ticket", "issue", "todo"],
        "documents": ["document", "doc", "file", "drive"],
    }

    message_lower = message.lower()
    for topic, keywords in topic_keywords.items():
        if any(kw in message_lower for kw in keywords):
            await preference_service.update_preference(
                db, str(user.id), "topics", topic, True
            )

    # Track time-of-day usage
    hour = datetime.now().hour
    time_of_day = (
        "morning" if 5 <= hour < 12 else
        "afternoon" if 12 <= hour < 17 else
        "evening" if 17 <= hour < 21 else
        "night"
    )
    await preference_service.update_preference(
        db, str(user.id), "usage", "active_time", time_of_day
    )
```

### Feedback Loop

```python
# When user provides feedback on a response
async def learn_from_feedback(db, user_id, feedback_type, feedback_value, message_id):
    # Rating feedback
    if feedback_type == "rating":
        rating = feedback_value.get("rating")
        if rating >= 4:
            # Positive - reinforce current preferences
            await preference_service.reinforce_preferences(db, user_id)
        elif rating <= 2:
            # Negative - adjust preferences
            await preference_service.adjust_preferences(db, user_id, message_id)

    # Edit feedback - user modified the response
    elif feedback_type == "edit":
        original = feedback_value.get("original")
        edited = feedback_value.get("edited")

        if len(edited) < len(original) * 0.7:
            # User wanted shorter response
            await preference_service.update_preference(
                db, user_id, "response", "length", "concise"
            )
        elif len(edited) > len(original) * 1.3:
            # User wanted longer response
            await preference_service.update_preference(
                db, user_id, "response", "length", "detailed"
            )
```

### How Stored Data Improves Future Responses

```
┌─────────────────────────────────────────────────────────────────┐
│                    FUTURE QUERY                                  │
│              "Send a follow-up to Sarah"                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA RETRIEVAL                                │
│                                                                  │
│  1. Previous context (from last assistant message):              │
│     - Email about Q4 Budget from Sarah                           │
│     - Budget spreadsheet reference                               │
│                                                                  │
│  2. Entity memory:                                               │
│     - Sarah Johnson: sarah@company.com                           │
│     - Previous interactions: 15 mentions                         │
│                                                                  │
│  3. User preferences:                                            │
│     - message_style: brief                                       │
│     - email_tone: professional                                   │
│                                                                  │
│  4. Episodic memory:                                             │
│     - Last conversation about Sarah was about budget             │
│     - User asked about Q4 planning                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INFORMED RESPONSE                             │
│                                                                  │
│  "I'll draft a follow-up email to Sarah Johnson                  │
│   (sarah@company.com) about the Q4 budget discussion.            │
│                                                                  │
│   **Pending Action:**                                            │
│   Send email to sarah@company.com                                │
│   Subject: Re: Q4 Budget Discussion - Follow Up                  │
│   [Confirm to send]"                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Complete Query Flow

```
USER: "Create Jira tasks based on my last email"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: CHAT API RECEIVES REQUEST                                │
│ - Create/get user and session                                    │
│ - Load conversation history (0 messages if new session)          │
│ - Build AgentState                                               │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: ORCHESTRATOR STARTS                                      │
│ - Load user preferences                                          │
│ - First LLM call with system prompt + user message               │
│ - LLM decides: "I need to retrieve context first"                │
│ - Returns tool_call: retrieve_context(query="last email")        │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: CONTEXT RETRIEVAL                                        │
│ - Detect "email" keyword → sources = ["gmail", "outlook"]        │
│ - Detect "last" keyword → temporal query = True                  │
│ - Skip semantic search, use _get_most_recent()                   │
│ - Return 5 most recent emails with 0.9 relevance                 │
│ - Update state.context_items                                     │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: SECOND LLM CALL                                          │
│ - LLM sees retrieved emails in context                           │
│ - Decides: "Need to delegate to task specialist"                 │
│ - Returns tool_call: delegate_to_specialist(                     │
│       specialist="task",                                         │
│       task="Create tasks from email content"                     │
│   )                                                              │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: TASK AGENT RUNS                                          │
│ - Receives context (5 emails)                                    │
│ - LLM extracts potential tasks from email content                │
│ - Realizes: "I don't know the Jira project key"                  │
│ - Uses ask_user tool: "Which project should I use?"              │
│ - Returns with needs_clarification=True                          │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: ORCHESTRATOR COMPLETES                                   │
│ - Receives specialist response                                   │
│ - Sees needs_clarification=True                                  │
│ - Sets response.needs_clarification=True                         │
│ - Sets response.clarification_question                           │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: STORE DATA                                               │
│ - Store user message in ChatMessage                              │
│ - Store assistant response with context_items                    │
│ - Update user preferences (topics: tasks)                        │
│ - Update session context in Redis                                │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: RETURN RESPONSE                                          │
│ {                                                                │
│   "session_id": "abc-123",                                       │
│   "response": "I found 5 recent emails...",                      │
│   "needs_clarification": true,                                   │
│   "clarification": {                                             │
│     "question": "Which Jira project should I use?",              │
│     "options": ["PROJECT-A", "PROJECT-B"]                        │
│   },                                                             │
│   "context_used": [                                              │
│     {"source": "gmail", "title": "Q4 Planning", "relevance": 0.9}│
│   ],                                                             │
│   "pending_actions": []                                          │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
USER PROVIDES CLARIFICATION: "Use PROJECT-A"
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 9: FOLLOW-UP REQUEST                                        │
│ - Load previous context from last assistant message              │
│ - 5 emails now in state.context_items                            │
│ - Add clarification to message                                   │
│ - Run orchestrator again                                         │
│ - Task agent now has project key                                 │
│ - Creates pending actions for task creation                      │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 10: RETURN WITH PENDING ACTIONS                             │
│ {                                                                │
│   "response": "I'll create these tasks in PROJECT-A:",           │
│   "pending_actions": [                                           │
│     {                                                            │
│       "id": "act_12345678",                                      │
│       "type": "create_task",                                     │
│       "description": "Create: Review Q4 budget proposal",        │
│       "params": {"project": "PROJECT-A", "summary": "..."}       │
│     }                                                            │
│   ]                                                              │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
USER CONFIRMS: confirm_actions=["act_12345678"]
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 11: EXECUTE ACTIONS                                         │
│ - Retrieve pending actions from Redis                            │
│ - Execute via ActionExecutor → External Jira API                 │
│ - Remove from pending                                            │
│ - Return completed_actions                                       │
└─────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│ FINAL RESPONSE                                                   │
│ {                                                                │
│   "response": "Tasks created successfully!",                     │
│   "completed_actions": [                                         │
│     {"id": "act_12345678", "result": "PROJ-123 created"}         │
│   ]                                                              │
│ }                                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Database Models

### Core Models Summary

```
User
├── KnowledgeItem (emails, docs, tasks, events)
│   ├── Embedding (vector chunks)
│   └── EntityMention (links to entities)
├── Entity (people, projects, topics)
│   └── EntityMention
├── ChatSession (conversations)
│   └── ChatMessage (individual messages)
├── UserPreference (learned preferences)
└── UserFeedback (feedback on responses)
```

### Key Fields

| Model | Key Fields | Purpose |
|-------|-----------|---------|
| `KnowledgeItem` | source_type, source_id, content_type, title, content, item_metadata | Unified content storage |
| `Embedding` | embedding (1536 dims), chunk_index, chunk_text | Vector search |
| `Entity` | entity_type, normalized_name, mention_count | Relationship tracking |
| `ChatMessage` | role, content, context_items[], pending_actions[] | Conversation history |
| `UserPreference` | preference_type, preference_key, preference_value, confidence | Learned behavior |

### Database Indexes

```sql
-- Fast user + source filtering
CREATE INDEX idx_knowledge_user_source ON knowledge_items(user_id, source_type);

-- Temporal queries
CREATE INDEX idx_knowledge_created ON knowledge_items(user_id, source_created_at DESC);

-- Unique constraint for deduplication
CREATE UNIQUE INDEX idx_knowledge_unique ON knowledge_items(user_id, source_type, source_id);

-- Vector similarity search (HNSW)
CREATE INDEX idx_embedding_vector ON embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

---

## Configuration

### Key Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `EMBEDDING_MODEL` | text-embedding-3-small | OpenAI embedding model |
| `CHAT_MODEL` | gpt-4o-mini | LLM for orchestration |
| `EMBEDDING_DIMENSIONS` | 1536 | Vector size |
| `MAX_CONTEXT_ITEMS` | 10 | Max items in context |
| `MAX_CONTEXT_TOKENS` | 4000 | Token limit for context |
| `EXTERNAL_DATA_ENABLED` | False | Use external APIs or internal DB |

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/aiemployee

# Redis
REDIS_URL=redis://localhost:6379

# OpenAI
OPENAI_API_KEY=sk-...

# External APIs (optional)
GMAIL_CLIENT_ID=...
JIRA_API_TOKEN=...
```

---

## Summary

The AI Employee V2 system processes queries through:

1. **Entry** - Chat API receives request, manages user/session
2. **Context** - Multi-strategy retrieval (semantic, temporal, entity, FTS)
3. **Scoring** - Weighted relevance calculation (semantic 50%, recency 20%, entity 30%)
4. **Orchestration** - Tool-based agent loop with LLM
5. **Generation** - Context-aware response with proper references
6. **Storage** - Messages, context refs, preferences, actions stored for future use

The system continuously learns from interactions, building better context retrieval and personalized responses over time.

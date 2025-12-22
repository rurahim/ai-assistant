# Context Retrieval & LLM Integration: Complete Technical Deep Dive

This document explains **every granular detail** of how context is fetched from the database and fed to the LLM in this AI Assistant system.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Data Flow Pipeline](#2-data-flow-pipeline)
3. [Memory Architecture](#3-memory-architecture)
4. [Embedding Generation](#4-embedding-generation)
5. [Retrieval Strategies](#5-retrieval-strategies)
6. [Relevance Scoring Mathematics](#6-relevance-scoring-mathematics)
7. [Episodic Memory System](#7-episodic-memory-system)
8. [Context Formatting for LLM](#8-context-formatting-for-llm)
9. [Complete Code Flow](#9-complete-code-flow)

---

## 1. System Overview

### Architecture Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER REQUEST                                   │
│                    "What did Sarah send me last week?"                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CHAT API ENDPOINT                                │
│                         app/api/chat.py:132                              │
│  - Receives request                                                      │
│  - Gets/creates user & session                                           │
│  - Initializes services                                                  │
│  - Calls OrchestratorAgent                                               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       ORCHESTRATOR AGENT                                 │
│                   app/agents/orchestrator.py:93                          │
│  - Parses user intent                                                    │
│  - Decides which tools to call                                           │
│  - Calls retrieve_context tool                                           │
│  - Builds final prompt                                                   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        CONTEXT SERVICE                                   │
│                 app/services/context_service.py:25                       │
│  - Semantic search (embeddings)                                          │
│  - Full-text search (PostgreSQL tsvector)                                │
│  - Entity search                                                         │
│  - Keyword search (fallback)                                             │
│  - Episodic memory (chat history)                                        │
│  - Relevance scoring                                                     │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      POSTGRESQL + PGVECTOR                               │
│  Tables:                                                                 │
│  - knowledge_items: Stores emails, docs, tasks, events                   │
│  - embeddings: Vector storage (1536 dimensions)                          │
│  - entities: People, projects, topics                                    │
│  - chat_sessions / chat_messages: Conversation history                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Configuration (app/config.py)

| Setting | Value | Purpose |
|---------|-------|---------|
| `embedding_model` | `text-embedding-3-small` | OpenAI model for vector generation |
| `embedding_dimensions` | `1536` | Vector size (fixed by model) |
| `chat_model` | `gpt-4o-mini` | Primary LLM for responses |
| `max_context_items` | `10` | Maximum items to include in prompt |
| `max_context_tokens` | `4000` | Token budget for context |

---

## 2. Data Flow Pipeline

### Step-by-Step Request Processing

```
1. HTTP POST /chat
   │
   ├── Request Body:
   │   {
   │     "user_id": "user_123",
   │     "session_id": "sess_abc",  // optional
   │     "message": "What did Sarah send me last week?"
   │   }
   │
   ▼
2. chat() function (chat.py:132)
   │
   ├── get_or_create_user(db, request.user_id)
   ├── get_or_create_session(db, user, request.session_id)
   ├── Store user message in ChatMessage table
   ├── Get conversation history (last 10 messages)
   │
   ▼
3. Build AgentState (chat.py:224)
   │
   │   AgentState {
   │     user_id: "user_123",
   │     session_id: "sess_abc",
   │     message: "What did Sarah send me last week?",
   │     conversation_history: [...],
   │     context_items: [],  // Empty initially
   │     entities: []
   │   }
   │
   ▼
4. OrchestratorAgent.run(state) (orchestrator.py:514)
   │
   ├── Load user preferences
   ├── run_with_tools(state) → Tool execution loop
   │
   ▼
5. LLM decides to call retrieve_context tool
   │
   │   Tool Call:
   │   {
   │     "name": "retrieve_context",
   │     "arguments": {
   │       "query": "Sarah sent last week",
   │       "sources": ["gmail", "outlook"],
   │       "time_filter": "last_week"
   │     }
   │   }
   │
   ▼
6. _handle_retrieve_context (orchestrator.py:270)
   │
   ├── Calls ContextService.retrieve_with_memory()
   │
   ▼
7. ContextService.retrieve_with_memory() (context_service.py:831)
   │
   ├── Detect content type from query keywords
   ├── Check if temporal query ("last", "recent", etc.)
   ├── Run parallel retrieval strategies
   ├── Add episodic memory
   ├── Score and rank results
   │
   ▼
8. Return context to orchestrator
   │
   ▼
9. LLM generates final response using context
   │
   ▼
10. Response returned to user
```

---

## 3. Memory Architecture

The system implements **4 types of memory**:

### 3.1 Semantic Memory (Long-term Knowledge)

**Storage:** `knowledge_items` + `embeddings` tables

**Contents:**
- Emails (Gmail, Outlook)
- Documents (Google Drive, OneDrive)
- Tasks (Jira)
- Calendar Events

**Schema (knowledge_items):**
```sql
CREATE TABLE knowledge_items (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    source_type VARCHAR(50),      -- gmail, gdrive, jira, calendar
    source_id VARCHAR(255),       -- Original ID from source
    content_type VARCHAR(50),     -- email, document, task, event
    title VARCHAR(500),
    summary TEXT,                 -- AI-generated summary
    content TEXT,                 -- Full content
    metadata JSONB,               -- Source-specific metadata
    source_created_at TIMESTAMP,
    synced_at TIMESTAMP
);
```

**Schema (embeddings):**
```sql
CREATE TABLE embeddings (
    id UUID PRIMARY KEY,
    knowledge_item_id UUID REFERENCES knowledge_items(id),
    user_id UUID REFERENCES users(id),
    embedding VECTOR(1536),       -- pgvector type
    embedding_model VARCHAR(50),  -- text-embedding-3-small
    chunk_index INTEGER,          -- For chunked documents
    chunk_text TEXT
);

-- HNSW index for fast similarity search
CREATE INDEX idx_embedding_vector ON embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
```

### 3.2 Episodic Memory (Conversation History)

**Storage:** `chat_sessions` + `chat_messages` tables

**Purpose:** Remember what was discussed in previous conversations

**Retrieval:** Uses semantic similarity + session weighting

### 3.3 Working Memory (Current Session)

**Storage:** Redis

**Purpose:** Track current session state, pending actions

### 3.4 Procedural Memory (User Preferences)

**Storage:** Redis + Database

**Purpose:** Remember user preferences (message style, active times, etc.)

---

## 4. Embedding Generation

### 4.1 Model Specifications

**Model:** `text-embedding-3-small` (OpenAI)

| Property | Value |
|----------|-------|
| Dimensions | 1536 |
| Max Input Tokens | ~8191 |
| Max Characters (approx) | ~30,000 |

### 4.2 Embedding Creation Process (embedding_service.py)

```python
async def create_embedding(self, text: str) -> Optional[list[float]]:
    # Step 1: Clean and truncate text
    text = self._clean_text(text)  # Remove excess whitespace
    # Truncate to ~30,000 chars (≈8000 tokens)

    # Step 2: Call OpenAI API
    response = await self.openai.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )

    # Step 3: Return 1536-dimensional vector
    return response.data[0].embedding  # list[float] of length 1536
```

### 4.3 Text Cleaning (_clean_text method)

```python
def _clean_text(self, text: str) -> str:
    # Remove excessive whitespace
    text = " ".join(text.split())

    # Truncate to token limit
    max_chars = 30000  # ~8000 tokens
    if len(text) > max_chars:
        text = text[:max_chars] + "..."

    return text
```

### 4.4 Batch Embedding for Documents

For large documents, content is chunked:

```python
def chunk_document(self, content: str, chunk_size: int = 600, overlap: int = 100):
    """
    Parameters:
    - chunk_size: Target words per chunk (600 words ≈ 800 tokens)
    - overlap: Words of overlap between chunks (context preservation)

    Algorithm:
    1. Split content by paragraphs (double newlines)
    2. Accumulate paragraphs until chunk_size reached
    3. Keep last paragraph for overlap with next chunk
    4. Return list of chunks with index and word count
    """
```

---

## 5. Retrieval Strategies

The system uses **5 parallel retrieval strategies**:

### 5.1 Semantic Search (Primary)

**File:** `context_service.py:257`

**Algorithm:** Cosine similarity between query embedding and stored embeddings

**SQL Query:**
```sql
SELECT
    k.*,
    e.chunk_text,
    e.chunk_index,
    (1 - (e.embedding <=> query_embedding)) AS similarity
FROM knowledge_items k
JOIN embeddings e ON e.knowledge_item_id = k.id
WHERE k.user_id = :user_id
  AND k.source_type IN (:sources)  -- Optional filter
  AND k.source_created_at >= :date_from  -- Optional
ORDER BY similarity DESC
LIMIT :limit;
```

**Cosine Similarity Formula:**
```
similarity = 1 - cosine_distance

cosine_distance = 1 - (A · B) / (||A|| × ||B||)

Where:
- A = query embedding vector
- B = document embedding vector
- A · B = dot product = Σ(aᵢ × bᵢ)
- ||A|| = magnitude = √(Σaᵢ²)
```

**pgvector Operator:** `<=>` (cosine distance)

### 5.2 Full-Text Search (PostgreSQL tsvector)

**File:** `context_service.py:395`

**Algorithm:** PostgreSQL's built-in text search with ranking

**SQL Query:**
```sql
SELECT
    k.*,
    ts_rank(
        to_tsvector('english', COALESCE(k.title, '') || ' ' || COALESCE(k.content, '')),
        plainto_tsquery('english', :query)
    ) AS rank
FROM knowledge_items k
WHERE k.user_id = :user_id
  AND to_tsvector('english', COALESCE(k.title, '') || ' ' || COALESCE(k.content, ''))
      @@ plainto_tsquery('english', :query)
ORDER BY rank DESC
LIMIT :limit;
```

**ts_rank Formula:**
```
rank = (number of matching lexemes) / (number of unique lexemes in document + 1)

Considers:
- Frequency of search terms
- Proximity of terms
- Document length normalization
```

### 5.3 Entity Search

**File:** `context_service.py:324`

**Algorithm:** Find items mentioning specific entities (people, projects)

**Process:**
1. Find entity by name in `entities` table
2. Look up mentions in `entity_mentions` table
3. Return knowledge items with those mentions

### 5.4 Keyword Search (Fallback)

**File:** `context_service.py:457`

**Algorithm:** Simple ILIKE pattern matching

**Used when:** Embedding API fails or returns no results

```python
# For each keyword in query:
conditions.append(
    or_(
        KnowledgeItem.title.ilike(f"%{keyword}%"),
        KnowledgeItem.content.ilike(f"%{keyword}%"),
        KnowledgeItem.summary.ilike(f"%{keyword}%"),
    )
)
```

**Score Calculation:**
```python
score = matches / len(keywords)
# Where matches = number of query keywords found in content
```

### 5.5 Temporal Search (Most Recent)

**File:** `context_service.py:93`

**Triggered by:** Keywords like "last", "latest", "recent", "newest"

**Algorithm:** Simple date-based sorting

```sql
SELECT * FROM knowledge_items
WHERE user_id = :user_id
  AND source_type IN (:sources)
ORDER BY source_created_at DESC
LIMIT :limit;
```

---

## 6. Relevance Scoring Mathematics

### 6.1 Final Score Calculation

**File:** `context_service.py:589`

**Formula:**
```
final_score = (semantic_score × 0.5) + recency_score + entity_score + source_score + fts_score + explicit_source_boost
```

### 6.2 Component Breakdown

#### Semantic Score (0.0 - 1.0)
```python
semantic_score = item.get("semantic_score", 0.5)
# From cosine similarity: 1 - cosine_distance
# Weighted at 50% of final score
contribution = semantic_score × 0.5
```

#### Recency Score (0.0 - 0.2)
```python
days_old = (now - item.source_created_at).days
recency_score = max(0, 0.2 - (days_old / 365) × 0.2)

# Examples:
# Today: 0.2
# 6 months ago: 0.1
# 1 year ago: 0.0
```

**Mathematical Form:**
```
recency_score = max(0, 0.2 × (1 - days_old/365))
```

#### Entity Match Score (0.0 - 0.3)
```python
matches = len(item_entities & query_entity_names)  # Set intersection
entity_score = min(0.3, matches × 0.1)

# Special case: explicit entity match
if item.get("entity_match"):
    entity_score = max(entity_score, 0.2)
```

#### Source Priority Score (0.05 - 0.10)
```python
SOURCE_PRIORITY = {
    "gmail": 0.10,
    "outlook": 0.10,
    "gdrive": 0.08,
    "onedrive": 0.08,
    "jira": 0.07,
    "calendar": 0.05,
}
source_score = SOURCE_PRIORITY.get(source, 0.05)
```

#### Full-Text Search Score (0.0 - 0.1)
```python
fts_score = min(0.1, fts_rank × 0.05)
```

#### Explicit Source Boost (0.0 or 0.4)
```python
EXPLICIT_SOURCE_BOOST = 0.4

# If user explicitly mentions a source (e.g., "jira tasks")
# Items from that source get +0.4 boost
if source in explicit_sources_set:
    explicit_source_boost = 0.4
```

### 6.3 Score Range Examples

| Scenario | Semantic | Recency | Entity | Source | FTS | Explicit | **Total** |
|----------|----------|---------|--------|--------|-----|----------|-----------|
| Perfect match, today | 0.95×0.5=0.475 | 0.2 | 0.2 | 0.1 | 0.05 | 0.4 | **1.425** |
| Good match, old | 0.8×0.5=0.4 | 0.0 | 0.1 | 0.1 | 0.02 | 0.0 | **0.62** |
| Weak match, recent | 0.4×0.5=0.2 | 0.15 | 0.0 | 0.05 | 0.0 | 0.0 | **0.40** |

---

## 7. Episodic Memory System

### 7.1 Purpose
Retrieve relevant past conversations to maintain context continuity.

### 7.2 Configuration Constants

```python
SAME_SESSION_WEIGHT = 1.0    # Full weight for current session
OTHER_SESSION_WEIGHT = 0.5   # Half weight for other sessions
EPISODIC_RELEVANCE_THRESHOLD = 0.3  # Minimum similarity to include
```

### 7.3 Retrieval Algorithm (context_service.py:733)

```python
async def get_episodic_memory(self, db, user_id, query, current_session_id, limit=5):
    # Step 1: Generate query embedding
    query_embedding = await embedding_service.generate_embedding(query)

    # Step 2: Get recent sessions (last 10)
    sessions = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.updated_at.desc())
        .limit(10)
    )

    for session in sessions:
        # Step 3: Determine session weight
        is_current = (session.id == current_session_id)
        session_weight = 1.0 if is_current else 0.5

        # Step 4: Get messages from session (last 20)
        messages = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(20)
        )

        for message in messages:
            # Step 5: Calculate semantic similarity
            message_embedding = await embedding_service.generate_embedding(
                message.content[:1000]
            )
            similarity = cosine_similarity(query_embedding, message_embedding)

            # Step 6: Skip if below threshold
            if similarity < 0.3:
                continue

            # Step 7: Calculate final relevance
            days_old = (now - message.created_at).days
            recency_score = max(0, 1 - days_old/30)

            relevance = min(0.5,
                similarity × session_weight × 0.6 +
                recency_score × 0.2
            )

            # Cap at 0.5 so episodic doesn't overpower semantic memory
```

### 7.4 Cosine Similarity Implementation

```python
def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
    """
    Formula: cos(θ) = (A · B) / (||A|| × ||B||)

    Where:
    - A · B = Σ(aᵢ × bᵢ) for i in [0, 1535]
    - ||A|| = √(Σaᵢ²)
    - ||B|| = √(Σbᵢ²)
    """
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return dot_product / (norm1 * norm2)
```

### 7.5 Episodic Score Formula

```
relevance = min(0.5, (semantic_similarity × session_weight × 0.6) + (recency_score × 0.2))

Where:
- semantic_similarity ∈ [0.3, 1.0]  (threshold filtered)
- session_weight ∈ {0.5, 1.0}
- recency_score = max(0, 1 - days_old/30)

Maximum possible: min(0.5, 1.0 × 1.0 × 0.6 + 1.0 × 0.2) = min(0.5, 0.8) = 0.5
```

---

## 8. Context Formatting for LLM

### 8.1 Message Building (base.py:213)

```python
def build_messages(self, state: AgentState) -> list[dict]:
    messages = [
        {"role": "system", "content": self.system_prompt},
    ]

    # Add conversation history (last 10 messages)
    for msg in state.conversation_history[-10:]:
        messages.append(msg)

    # Build user message with context
    user_content = state.message

    # Add context items if available
    if state.context_items:
        context_text = self._format_context(state.context_items)
        user_content = f"""## Available Context:
{context_text}

## User Request:
{user_content}"""

    # Add entities if available
    if state.entities:
        entities_text = self._format_entities(state.entities)
        user_content = f"{user_content}\n\n## Known Entities:\n{entities_text}"

    messages.append({"role": "user", "content": user_content})
    return messages
```

### 8.2 Context Item Formatting

```python
def _format_context(self, context_items: list[dict]) -> str:
    formatted = []
    for item in context_items[:5]:  # Limit to top 5
        source = item.get("source", "unknown")
        title = item.get("title", "")
        summary = item.get("summary") or item.get("content", "")[:500]

        formatted.append(f"[{source.upper()}] {title}\n{summary}\n")

    return "\n---\n".join(formatted)
```

### 8.3 Final Prompt Structure

```
┌────────────────────────────────────────────────────────────────────┐
│ SYSTEM MESSAGE                                                      │
├────────────────────────────────────────────────────────────────────┤
│ You are an intelligent AI assistant that helps users manage...     │
│ [Full system prompt from orchestrator.py]                          │
└────────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────┐
│ CONVERSATION HISTORY (last 10)                                      │
├────────────────────────────────────────────────────────────────────┤
│ {"role": "user", "content": "..."}                                 │
│ {"role": "assistant", "content": "..."}                            │
│ ...                                                                 │
└────────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────────┐
│ USER MESSAGE (with injected context)                                │
├────────────────────────────────────────────────────────────────────┤
│ ## Available Context:                                              │
│                                                                     │
│ [GMAIL] Re: Project Alpha Update                                   │
│ Sarah mentioned that the deadline has been moved to next Friday... │
│                                                                     │
│ ---                                                                 │
│                                                                     │
│ [GMAIL] Meeting Notes - Client Review                              │
│ Attendees: Sarah, John, Mike. Discussion points: budget...         │
│                                                                     │
│ ## Known Entities:                                                  │
│ - Sarah Johnson (person): sarah@company.com                        │
│ - Project Alpha (project)                                          │
│                                                                     │
│ ## User Request:                                                   │
│ What did Sarah send me last week?                                  │
└────────────────────────────────────────────────────────────────────┘
```

---

## 9. Complete Code Flow

### 9.1 Entry Point: chat.py:132

```python
@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    # 1. Get or create user
    user = await get_or_create_user(db, request.user_id)

    # 2. Get or create session
    session = await get_or_create_session(db, user, request.session_id)

    # 3. Initialize services
    redis = await get_redis()
    working_memory = WorkingMemory(redis)

    # 4. Store user message
    user_message = ChatMessage(
        session_id=session.id,
        user_id=user.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)

    # 5. Get conversation history
    history = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )

    # 6. Build agent state
    state = AgentState(
        user_id=str(user.id),
        session_id=str(session.id),
        message=request.message,
        conversation_history=[...],
        context_items=[],
    )

    # 7. Initialize orchestrator
    orchestrator = OrchestratorAgent(
        db=db,
        context_service=ContextService(),
        entity_service=EntityService(),
        preference_service=PreferenceService(working_memory),
        working_memory=working_memory,
    )

    # 8. Run orchestrator
    response = await orchestrator.run(state)

    # 9. Store assistant response
    assistant_message = ChatMessage(
        session_id=session.id,
        user_id=user.id,
        role="assistant",
        content=response.message,
        context_items=[...],
    )
    db.add(assistant_message)

    await db.commit()
    return ChatResponse(...)
```

### 9.2 Orchestrator Run: orchestrator.py:514

```python
async def run(self, state: AgentState) -> AgentResponse:
    # Load user preferences
    state.preferences = await self.preference_service.get_preferences(
        self.db, state.user_id
    )

    # Run tool execution loop
    response = await self.run_with_tools(state)

    # Handle clarification
    if state.metadata.get("needs_clarification"):
        response.needs_clarification = True
        response.clarification_question = state.metadata.get("clarification_question")

    return response
```

### 9.3 Tool Execution Loop: base.py:286

```python
async def run_with_tools(self, state: AgentState, max_iterations: int = 10):
    messages = self.build_messages(state)
    total_tokens = 0

    for iteration in range(max_iterations):
        # Call LLM
        result = await self.chat(messages)
        total_tokens += result["tokens"]

        if result["tool_calls"]:
            # Add assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": result["content"],
                "tool_calls": [...],
            })

            # Execute each tool
            for tool_call in result["tool_calls"]:
                tool_result = await self.execute_tool(tool_call, state)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result.to_dict()),
                })

            continue  # Loop for follow-up

        # No tool calls - return final response
        return AgentResponse(
            message=result["content"],
            state=state,
            tokens_used=total_tokens,
        )
```

### 9.4 Context Retrieval: orchestrator.py:270

```python
async def _handle_retrieve_context(
    self, state, query, sources=None, time_filter=None, entity_filter=None
):
    # Call enhanced retrieval with all memory types
    result = await self.context_service.retrieve_with_memory(
        db=self.db,
        user_id=state.user_id,
        query=query,
        session_id=state.session_id,
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
        "items": [...],
        "entities": result["entities"],
    }
```

### 9.5 Full Retrieval: context_service.py:831

```python
async def retrieve_with_memory(self, db, user_id, query, session_id, ...):
    # 1. Auto-detect content type from query
    detected_sources = self._detect_content_type_sources(query)
    is_temporal = self._is_temporal_query(query)

    # 2. Handle temporal queries (get most recent)
    if is_temporal and detected_sources:
        temporal_results = await self._get_most_recent(
            db, user_id, detected_sources, limit
        )

    # 3. Run base retrieval (semantic + FTS + entity + keyword)
    base_results = await self.retrieve(
        db=db,
        user_id=user_id,
        query=query,
        sources=effective_sources,
        time_filter=time_filter,
        entity_filter=entity_filter,
        explicit_sources=detected_sources,  # For boost
    )

    # 4. Add episodic memory
    if include_episodic:
        episodic = await self.get_episodic_memory(
            db, user_id, query, session_id, limit=3
        )
        base_results["items"].extend(episodic)

    # 5. Sort by relevance and limit
    base_results["items"].sort(
        key=lambda x: x.get("relevance_score", 0),
        reverse=True
    )

    return base_results
```

---

## Summary of Key Formulas

### Cosine Similarity (Semantic Search)
```
similarity = (A · B) / (||A|| × ||B||) = Σ(aᵢbᵢ) / (√Σaᵢ² × √Σbᵢ²)
```

### Final Relevance Score
```
score = semantic×0.5 + recency + entity + source + fts + explicit_boost
```

### Recency Score
```
recency = max(0, 0.2 × (1 - days_old/365))
```

### Episodic Relevance
```
relevance = min(0.5, semantic × session_weight × 0.6 + recency × 0.2)
```

### Keyword Match Score
```
score = matching_keywords / total_keywords
```

---

## Database Indexes Used

| Index | Table | Purpose |
|-------|-------|---------|
| `idx_embedding_vector` (HNSW) | embeddings | Fast cosine similarity search |
| `idx_knowledge_user_source` | knowledge_items | Filter by user + source |
| `idx_knowledge_created` | knowledge_items | Time-based sorting |
| `idx_embedding_user` | embeddings | User filtering |
| `idx_embedding_item_chunk` | embeddings | Unique chunk lookup |

---

This document covers every aspect of the context retrieval system. Each formula, algorithm, and code path is documented for complete understanding.


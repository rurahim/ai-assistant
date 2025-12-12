"""
Chat API endpoints.
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, ChatSession, ChatMessage
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    MessageResponse,
    SessionResponse,
    SessionListResponse,
    ContextItemRef,
    PendingAction,
    Clarification,
)
from app.agents import OrchestratorAgent, AgentState, ActionExecutor
from app.services import ContextService, EntityService, PreferenceService
from app.core.redis_client import get_redis
from app.core.memory import WorkingMemory
from app.core.external_api import get_external_api

router = APIRouter(prefix="/chat")


async def _learn_from_conversation(
    db: AsyncSession,
    user: User,
    message: str,
    response_content: str,
    preference_service: PreferenceService,
) -> None:
    """
    Learn user preferences from conversation patterns.

    Analyzes:
    - Message length preference
    - Topics of interest
    - Interaction patterns
    """
    import re

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

    # Track topics of interest (simple keyword extraction)
    topic_keywords = {
        "email": ["email", "mail", "send", "reply", "inbox"],
        "calendar": ["meeting", "schedule", "calendar", "event", "appointment"],
        "tasks": ["task", "jira", "ticket", "issue", "todo", "assign"],
        "documents": ["document", "doc", "file", "drive", "folder"],
    }

    message_lower = message.lower()
    for topic, keywords in topic_keywords.items():
        if any(kw in message_lower for kw in keywords):
            await preference_service.update_preference(
                db, str(user.id), "topics", topic, True
            )

    # Track time-of-day usage pattern
    from datetime import datetime
    hour = datetime.now().hour
    time_of_day = "morning" if 5 <= hour < 12 else "afternoon" if 12 <= hour < 17 else "evening" if 17 <= hour < 21 else "night"
    await preference_service.update_preference(
        db, str(user.id), "usage", "active_time", time_of_day
    )


async def get_or_create_user(
    db: AsyncSession,
    external_user_id: str,
) -> User:
    """Get or create a user by external ID."""
    stmt = select(User).where(User.external_user_id == external_user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            external_user_id=external_user_id,
            email=f"{external_user_id}@placeholder.com",  # Will be updated
        )
        db.add(user)
        await db.flush()

    return user


async def get_or_create_session(
    db: AsyncSession,
    user: User,
    session_id: Optional[str] = None,
) -> ChatSession:
    """Get existing session or create new one."""
    if session_id:
        stmt = select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == user.id,
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if session:
            return session

    # Create new session
    session = ChatSession(
        user_id=user.id,
    )
    db.add(session)
    await db.flush()

    return session


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Main chat endpoint.

    Processes user messages, retrieves context, and generates responses.
    """
    # Get or create user
    user = await get_or_create_user(db, request.user_id)

    # Get or create session
    session = await get_or_create_session(db, user, request.session_id)

    # Initialize services
    redis = await get_redis()
    working_memory = WorkingMemory(redis)

    # Store user message
    user_message = ChatMessage(
        session_id=session.id,
        user_id=user.id,
        role="user",
        content=request.message,
    )
    db.add(user_message)

    # Check for action confirmation
    completed_actions = []
    if request.confirm_actions:
        # Execute confirmed actions
        pending = await working_memory.get_pending_actions(str(user.id), str(session.id))
        actions_to_execute = [
            a for a in pending
            if a.get("id") in request.confirm_actions
        ]

        if actions_to_execute:
            external_api = await get_external_api()
            executor = ActionExecutor(external_api)
            results = await executor.execute_batch(str(user.id), actions_to_execute)

            for result in results:
                completed_actions.append(result.to_dict())

            # Remove executed actions from pending
            for action_id in request.confirm_actions:
                await working_memory.remove_pending_action(
                    str(user.id), str(session.id), action_id
                )

    # Get conversation history
    history_stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    history_result = await db.execute(history_stmt)
    history_messages = list(reversed(history_result.scalars().all()))

    # Get context items from the most recent assistant message in session
    # This ensures context is carried forward in follow-up messages
    previous_context_items = []
    for m in reversed(history_messages):
        if m.role == "assistant" and m.context_items:
            # Load full context items from database using IDs
            context_ids = [c.get("id") for c in m.context_items if c.get("id")]
            if context_ids:
                from app.models import KnowledgeItem
                context_stmt = select(KnowledgeItem).where(KnowledgeItem.id.in_(context_ids))
                context_result = await db.execute(context_stmt)
                items = context_result.scalars().all()
                # Build lookup for relevance scores
                relevance_lookup = {c.get("id"): c.get("relevance", 0.5) for c in m.context_items}
                for item in items:
                    previous_context_items.append({
                        "id": str(item.id),
                        "source": item.source_type,
                        "source_id": item.source_id,
                        "content_type": item.content_type,
                        "title": item.title,
                        "summary": item.summary,
                        "content": item.content,
                        "metadata": item.item_metadata,
                        "source_created_at": item.source_created_at.isoformat() if item.source_created_at else None,
                        "relevance_score": relevance_lookup.get(str(item.id), 0.5),
                    })
            break  # Only need most recent assistant message's context

    # Build agent state
    state = AgentState(
        user_id=str(user.id),
        session_id=str(session.id),
        message=request.message,
        conversation_history=[
            {"role": m.role, "content": m.content}
            for m in history_messages
        ],
        context_items=previous_context_items,  # Carry forward previous context
    )

    # Add clarification response context if provided
    if request.clarification_response:
        state.message = f"User clarification: {request.clarification_response}\n\nOriginal request: {state.message}"

    # Initialize services
    context_service = ContextService()
    entity_service = EntityService()
    preference_service = PreferenceService(working_memory)

    # ============================================================
    # PROACTIVE CONTEXT RETRIEVAL
    # Always fetch relevant context BEFORE LLM processes the message.
    # This ensures context_used is populated regardless of LLM's decision.
    # ============================================================
    if not previous_context_items:  # Only if no context carried from previous message
        proactive_context = await context_service.retrieve_with_memory(
            db=db,
            user_id=str(user.id),
            query=request.message,
            session_id=str(session.id),
            include_episodic=True,
            limit=10,
        )
        # Add retrieved items to state
        state.context_items.extend(proactive_context.get("items", []))
        state.entities.extend(proactive_context.get("entities", []))

    orchestrator = OrchestratorAgent(
        db=db,
        context_service=context_service,
        entity_service=entity_service,
        preference_service=preference_service,
        working_memory=working_memory,
    )

    # Run orchestrator
    response = await orchestrator.run(state)

    # Store assistant response
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

    # Store pending actions in working memory
    for action in response.pending_actions:
        await working_memory.add_pending_action(
            str(user.id), str(session.id), action
        )

    # Learn from conversation (update preferences based on interaction)
    await _learn_from_conversation(
        db=db,
        user=user,
        message=request.message,
        response_content=response.message,
        preference_service=preference_service,
    )

    # Update session context in working memory
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

    await db.commit()

    # Build response
    return ChatResponse(
        session_id=str(session.id),
        response=response.message,
        needs_clarification=response.needs_clarification,
        clarification=Clarification(
            question=response.clarification_question,
            options=response.clarification_options,
        ) if response.needs_clarification else None,
        context_used=[
            ContextItemRef(
                id=item.get("id"),
                source=item.get("source"),
                title=item.get("title"),
                summary=item.get("summary", item.get("content", "")[:150] + "..." if item.get("content") else None),
                content_type=item.get("content_type"),
                source_created_at=item.get("source_created_at"),
                relevance_score=item.get("relevance_score"),
            )
            for item in state.context_items[:5]
        ],
        pending_actions=[
            PendingAction(
                id=a["id"],
                type=a["type"],
                description=a["description"],
                params=a.get("params", {}),
            )
            for a in response.pending_actions
        ],
        completed_actions=completed_actions,
        tokens_used=response.tokens_used,
        model_used=response.model_used,
    )


@router.get("/sessions/{user_id}", response_model=SessionListResponse)
async def list_sessions(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List chat sessions for a user."""
    # Get user
    user = await get_or_create_user(db, user_id)

    # Count total
    count_stmt = select(func.count(ChatSession.id)).where(
        ChatSession.user_id == user.id
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar()

    # Get sessions with message count
    stmt = (
        select(
            ChatSession,
            func.count(ChatMessage.id).label("message_count"),
        )
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.user_id == user.id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=str(row.ChatSession.id),
                user_id=user_id,
                title=row.ChatSession.title,
                session_type=row.ChatSession.session_type,
                message_count=row.message_count,
                created_at=row.ChatSession.created_at,
                updated_at=row.ChatSession.updated_at,
            )
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/sessions/{user_id}/{session_id}/messages")
async def get_session_messages(
    user_id: str,
    session_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Get messages for a chat session."""
    # Get user
    user = await get_or_create_user(db, user_id)

    # Verify session belongs to user
    session_stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id,
    )
    session_result = await db.execute(session_stmt)
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get messages
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)
    messages = result.scalars().all()

    return {
        "session_id": session_id,
        "messages": [
            MessageResponse(
                id=str(m.id),
                session_id=str(m.session_id),
                role=m.role,
                content=m.content,
                context_items=m.context_items,
                pending_actions=m.pending_actions,
                created_at=m.created_at,
            )
            for m in messages
        ],
        "limit": limit,
        "offset": offset,
    }

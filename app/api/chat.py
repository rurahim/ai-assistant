"""
Chat API endpoints - Multi-Agent System.

Provides:
- Main chat endpoint with standardized response format
- Session management
- Backward compatibility with old endpoints
"""

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, ChatSession, ChatMessage
from app.schemas.agent_schemas import (
    ChatRequest,
    ChatResponse,
    ErrorResponse,
    ErrorDetail,
)
from app.agents.orchestrator import create_orchestrator

router = APIRouter(prefix="/chat")


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

async def get_or_create_user(
    db: AsyncSession,
    user_id: str,
) -> User:
    """Get or create a user by ID."""
    import uuid as uuid_module

    # Try external_user_id first
    stmt = select(User).where(User.external_user_id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user:
        return user

    # Try by internal ID (if user_id looks like a UUID)
    try:
        user_uuid = uuid_module.UUID(user_id)
        stmt = select(User).where(User.id == user_uuid)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user:
            return user
    except (ValueError, Exception):
        pass

    # Create new user
    user = User(
        external_user_id=user_id,
        email=f"{user_id[:8]}@placeholder.com",
    )
    db.add(user)
    await db.flush()

    return user


# =============================================================================
# MAIN CHAT ENDPOINT (NEW MULTI-AGENT SYSTEM)
# =============================================================================

@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Main chat endpoint using the multi-agent system.

    Request:
    ```json
    {
        "user_id": "string (required)",
        "session_id": "string (optional)",
        "message": "string (required)",
        "attachments": [{"type": "email", "content": {...}}],
        "confirm_action": "act_xxxxxxxx (optional)"
    }
    ```

    Response Types:
    - "answer": Direct response to a question
    - "action": Action pending confirmation or ready to execute
    - "clarification": Missing information needed

    Response:
    ```json
    {
        "response_type": "answer | action | clarification",
        "message": "Human-readable response",
        "session_id": "uuid",
        "action": {...},
        "clarifications": [...],
        "sources": [...],
        "metadata": {...}
    }
    ```
    """
    try:
        # Get or create user
        user = await get_or_create_user(db, request.user_id)

        # Update request with resolved user ID (ensures consistency)
        request.user_id = str(user.id)

        # Create orchestrator and process request
        orchestrator = create_orchestrator(db)
        response = await orchestrator.process(request)

        # Store messages in database
        await _store_messages(db, user, request, response)

        await db.commit()
        return response

    except HTTPException:
        raise
    except Exception as e:
        # Log the error
        print(f"Chat error: {e}")
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


async def _store_messages(
    db: AsyncSession,
    user: User,
    request: ChatRequest,
    response: ChatResponse,
) -> None:
    """Store chat messages in database."""
    try:
        # Get or create session
        session_id = response.session_id
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError:
            session_uuid = uuid.uuid4()

        stmt = select(ChatSession).where(ChatSession.id == session_uuid)
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            session = ChatSession(
                id=session_uuid,
                user_id=user.id,
                title=request.message[:50] + "..." if len(request.message) > 50 else request.message,
            )
            db.add(session)
            await db.flush()

        # Store user message
        user_message = ChatMessage(
            session_id=session.id,
            user_id=user.id,  # Keep as UUID, not string
            role="user",
            content=request.message,
        )
        db.add(user_message)

        # Store assistant response
        assistant_message = ChatMessage(
            session_id=session.id,
            user_id=user.id,  # Keep as UUID, not string
            role="assistant",
            content=response.message,
            context_items=[
                {"id": s.id, "type": s.type, "title": s.title}
                for s in response.sources
            ] if response.sources else None,
            pending_actions=[
                {"id": response.action.id, "type": response.action.type}
            ] if response.action else None,
        )
        db.add(assistant_message)

    except Exception as e:
        import traceback
        print(f"Failed to store messages: {e}")
        print(f"Traceback: {traceback.format_exc()}")


# =============================================================================
# SESSION MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/sessions/{user_id}")
async def list_sessions(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List chat sessions for a user."""
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

    return {
        "sessions": [
            {
                "id": str(row.ChatSession.id),
                "user_id": user_id,
                "title": row.ChatSession.title,
                "message_count": row.message_count,
                "created_at": row.ChatSession.created_at.isoformat() if row.ChatSession.created_at else None,
                "updated_at": row.ChatSession.updated_at.isoformat() if row.ChatSession.updated_at else None,
            }
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/sessions/{user_id}/{session_id}")
async def get_session(
    user_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific session with its messages."""
    user = await get_or_create_user(db, user_id)

    # Get session
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get messages
    messages_stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    )
    messages_result = await db.execute(messages_stmt)
    messages = messages_result.scalars().all()

    return {
        "session": {
            "id": str(session.id),
            "user_id": user_id,
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        },
        "messages": [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "context_items": m.context_items,
                "pending_actions": m.pending_actions,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }


@router.delete("/sessions/{user_id}/{session_id}")
async def delete_session(
    user_id: str,
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a chat session."""
    user = await get_or_create_user(db, user_id)

    # Get session
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == user.id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete messages first
    from sqlalchemy import delete
    await db.execute(
        delete(ChatMessage).where(ChatMessage.session_id == session.id)
    )

    # Delete session
    await db.delete(session)
    await db.commit()

    return {"status": "deleted", "session_id": session_id}

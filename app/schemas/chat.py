"""
Chat-related Pydantic schemas.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ContextItemRef(BaseModel):
    """Reference to a context item used in response."""

    id: str
    source: str
    title: Optional[str] = None
    summary: Optional[str] = None
    content_type: Optional[str] = None
    source_created_at: Optional[str] = None
    relevance_score: Optional[float] = None


class PendingAction(BaseModel):
    """A pending action awaiting user confirmation."""

    id: str
    type: str
    description: str
    params: dict = Field(default_factory=dict)
    status: str = "pending_confirmation"


class ChatRequest(BaseModel):
    """Request to the chat endpoint."""

    user_id: str
    message: str
    session_id: Optional[str] = None
    confirm_actions: Optional[list[str]] = Field(
        default=None,
        description="Action IDs to confirm and execute",
    )
    clarification_response: Optional[str] = Field(
        default=None,
        description="User's response to a clarification question",
    )


class Clarification(BaseModel):
    """Clarification request from the assistant."""

    question: str
    options: Optional[list[str]] = None
    required_for: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from the chat endpoint."""

    session_id: str
    response: str
    needs_clarification: bool = False
    clarification: Optional[Clarification] = None
    context_used: list[ContextItemRef] = Field(default_factory=list)
    pending_actions: list[PendingAction] = Field(default_factory=list)
    completed_actions: list[dict] = Field(default_factory=list)
    tokens_used: int = 0
    model_used: Optional[str] = None


class MessageResponse(BaseModel):
    """Response representing a single message."""

    id: str
    session_id: str
    role: str
    content: str
    context_items: list[dict] = Field(default_factory=list)
    pending_actions: list[dict] = Field(default_factory=list)
    created_at: datetime

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    """Response representing a chat session."""

    id: str
    user_id: str
    title: Optional[str] = None
    session_type: Optional[str] = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    """Response for listing chat sessions."""

    sessions: list[SessionResponse]
    total: int
    limit: int
    offset: int

"""
Context retrieval Pydantic schemas.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ContextRequest(BaseModel):
    """Request for context retrieval."""

    user_id: str
    query: str
    sources: Optional[list[str]] = Field(
        default=None,
        description="Optional: specific sources to search",
    )
    time_filter: Optional[str] = Field(
        default=None,
        description="Time filter: today, yesterday, last_week, last_month",
    )
    entity_filter: Optional[str] = Field(
        default=None,
        description="Filter by entity name",
    )
    limit: int = Field(default=10, ge=1, le=50)


class ContextItem(BaseModel):
    """A single context item from retrieval."""

    id: str
    source: str
    source_id: str
    content_type: str
    title: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None
    metadata: dict = Field(default_factory=dict)
    source_created_at: Optional[datetime] = None
    relevance_score: float = 0.0


class EntityRef(BaseModel):
    """Reference to an entity found in results."""

    name: str
    type: str
    email: Optional[str] = None


class ContextResponse(BaseModel):
    """Response from context retrieval."""

    items: list[ContextItem]
    entities: list[EntityRef] = Field(default_factory=list)
    total: int
    query: str

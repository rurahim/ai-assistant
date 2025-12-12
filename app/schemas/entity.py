"""
Entity-related Pydantic schemas.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class EntityResponse(BaseModel):
    """Response representing an entity."""

    id: str
    name: str
    type: str
    normalized_name: str
    metadata: dict = Field(default_factory=dict)
    mention_count: int = 0
    last_seen_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class EntityListResponse(BaseModel):
    """Response for listing entities."""

    entities: list[EntityResponse]
    total: int
    limit: int
    offset: int


class RelatedItemSummary(BaseModel):
    """Summary of an item related to an entity."""

    id: str
    title: Optional[str] = None
    summary: Optional[str] = None
    date: Optional[datetime] = None
    context: Optional[str] = None


class RelatedItemsBySource(BaseModel):
    """Related items grouped by source."""

    count: int
    items: list[RelatedItemSummary]


class EntityContextResponse(BaseModel):
    """Response with full entity context."""

    entity: EntityResponse
    related_items: dict[str, RelatedItemsBySource] = Field(
        description="Related items grouped by source type"
    )


class EntityCreateRequest(BaseModel):
    """Request to create an entity."""

    name: str
    type: str = Field(description="Entity type: person, project, topic, company")
    metadata: dict = Field(default_factory=dict)


class EntityUpdateRequest(BaseModel):
    """Request to update an entity."""

    name: Optional[str] = None
    metadata: Optional[dict] = None

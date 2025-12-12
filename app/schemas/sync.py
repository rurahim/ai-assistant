"""
Sync-related Pydantic schemas.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class SyncConfig(BaseModel):
    """Configuration for sync operation."""

    gmail_days: int = Field(default=30, ge=1, le=365)
    document_months: int = Field(default=6, ge=1, le=24)
    calendar_days: int = Field(default=30, ge=1, le=365)
    jira_months: int = Field(default=3, ge=1, le=12)


class SyncRequest(BaseModel):
    """Request to initiate sync."""

    user_id: str
    sources: list[str] = Field(
        description="Sources to sync: gmail, gdrive, jira, calendar, outlook, onedrive"
    )
    config: Optional[SyncConfig] = None
    force: bool = Field(
        default=False,
        description="Force full re-sync even if recently synced",
    )


class SyncSourceStatus(BaseModel):
    """Status of a single source sync."""

    source: str
    status: str  # pending, syncing, completed, failed
    items_synced: int = 0
    last_sync_at: Optional[datetime] = None
    error_message: Optional[str] = None


class SyncStatus(BaseModel):
    """Overall sync status for a user."""

    user_id: str
    sources: list[SyncSourceStatus]
    overall_status: str  # pending, syncing, completed, partial_failure, failed


class SyncResponse(BaseModel):
    """Response from sync initiation."""

    sync_id: str
    user_id: str
    status: str
    sources: list[str]
    message: str


class WebhookPayload(BaseModel):
    """Payload for webhook events."""

    event_type: str = Field(
        description="Event type: item_created, item_updated, item_deleted"
    )
    user_id: str
    source: str = Field(
        description="Source: gmail, gdrive, jira, calendar"
    )
    source_id: str
    content_type: str = Field(
        description="Content type: email, document, task, event"
    )
    data: dict = Field(
        default_factory=dict,
        description="Full item data (for create/update)",
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WebhookResponse(BaseModel):
    """Response from webhook processing."""

    received: bool = True
    processed: bool
    item_id: Optional[str] = None
    error: Optional[str] = None

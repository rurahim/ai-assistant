"""
Online Meeting model for external data database.
Mirrors the 'online_meetings' table from gmail_outlook_db.
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from external_db.database import Base

if TYPE_CHECKING:
    from external_db.models.account import Account


class OnlineMeeting(Base):
    """Online meeting model - mirrors external gmail_outlook_db online_meetings table."""

    __tablename__ = "online_meetings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    meeting_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    time_zone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_online_meeting: Mapped[bool] = mapped_column(Boolean, default=True)
    join_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conference_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    dial_in_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attendees: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    organizer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="online_meetings")

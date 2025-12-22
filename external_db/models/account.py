"""
Account model for external data database.
Mirrors the 'accounts' table from gmail_outlook_db.
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, BigInteger, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from external_db.database import Base

if TYPE_CHECKING:
    from external_db.models.user import User
    from external_db.models.calendar_event import CalendarEvent
    from external_db.models.email import Email
    from external_db.models.contact import Contact
    from external_db.models.task import Task
    from external_db.models.jira import JiraBoard, JiraIssue
    from external_db.models.online_meeting import OnlineMeeting


class Account(Base):
    """OAuth account model - mirrors external gmail_outlook_db accounts table."""

    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # google, microsoft, atlassian
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Atlassian-specific fields
    cloud_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cloud_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cloud_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    user: Mapped["User"] = relationship("User", back_populates="accounts")
    calendar_events: Mapped[list["CalendarEvent"]] = relationship(
        "CalendarEvent",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    emails: Mapped[list["Email"]] = relationship(
        "Email",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    contacts: Mapped[list["Contact"]] = relationship(
        "Contact",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    jira_boards: Mapped[list["JiraBoard"]] = relationship(
        "JiraBoard",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    jira_issues: Mapped[list["JiraIssue"]] = relationship(
        "JiraIssue",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    online_meetings: Mapped[list["OnlineMeeting"]] = relationship(
        "OnlineMeeting",
        back_populates="account",
        cascade="all, delete-orphan",
    )

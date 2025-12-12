"""
Knowledge item model - unified content storage.
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, ForeignKey, DateTime, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User, UserFeedback
    from app.models.embedding import Embedding
    from app.models.entity import EntityMention


class KnowledgeItem(Base):
    """
    Unified content storage for all data sources.

    Stores emails, documents, tasks, events, etc. from various integrations.
    """

    __tablename__ = "knowledge_items"

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
    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # gmail, gdrive, calendar, outlook, onedrive, jira
    source_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )  # Original ID from source system
    content_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # email, document, task, event, etc.

    # Content
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # AI-generated
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Full content

    # Item metadata (varies by source)
    # Email: {from, to, cc, thread_id, labels, is_reply}
    # Document: {mime_type, folder_id, chunk_index, total_chunks}
    # Task: {project_key, status, assignee, priority}
    # Event: {attendees, location, recurrence}
    item_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)

    # Timestamps
    source_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    source_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="knowledge_items")
    embeddings: Mapped[list["Embedding"]] = relationship(
        "Embedding",
        back_populates="knowledge_item",
        cascade="all, delete-orphan",
    )
    entity_mentions: Mapped[list["EntityMention"]] = relationship(
        "EntityMention",
        back_populates="knowledge_item",
        cascade="all, delete-orphan",
    )
    feedback: Mapped[list["UserFeedback"]] = relationship(
        "UserFeedback",
        back_populates="knowledge_item",
    )

    __table_args__ = (
        # Unique constraint on user + source + source_id
        Index(
            "idx_knowledge_unique_source",
            "user_id",
            "source_type",
            "source_id",
            unique=True,
        ),
        # Index for user + source queries
        Index("idx_knowledge_user_source", "user_id", "source_type"),
        # Index for time-based queries
        Index("idx_knowledge_created", "user_id", "source_created_at"),
    )

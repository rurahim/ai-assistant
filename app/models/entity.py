"""
Entity models for people, projects, topics, etc.
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.knowledge import KnowledgeItem


class Entity(Base):
    """
    Extracted entities: people, projects, topics, companies.

    Metadata varies by type:
    - Person: {emails: [], job_title, company, relationship}
    - Project: {key, source, status}
    - Topic: {keywords: [], frequency}
    - Company: {domain, industry}
    """

    __tablename__ = "entities"

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
    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # person, project, topic, company
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )  # Lowercase, trimmed for matching

    entity_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    mention_count: Mapped[int] = mapped_column(Integer, default=1)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="entities")
    mentions: Mapped[list["EntityMention"]] = relationship(
        "EntityMention",
        back_populates="entity",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Unique constraint on user + type + normalized name
        Index(
            "idx_entity_unique",
            "user_id",
            "entity_type",
            "normalized_name",
            unique=True,
        ),
        # Index for name lookups
        Index("idx_entity_name", "user_id", "normalized_name"),
        # Index for type queries
        Index("idx_entity_type", "user_id", "entity_type"),
    )


class EntityMention(Base):
    """Links entities to knowledge items where they are mentioned."""

    __tablename__ = "entity_mentions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mention_context: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )  # Surrounding text
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    entity: Mapped["Entity"] = relationship("Entity", back_populates="mentions")
    knowledge_item: Mapped["KnowledgeItem"] = relationship(
        "KnowledgeItem",
        back_populates="entity_mentions",
    )

    __table_args__ = (
        # Unique constraint on entity + knowledge item
        Index(
            "idx_entity_mention_unique",
            "entity_id",
            "knowledge_item_id",
            unique=True,
        ),
    )

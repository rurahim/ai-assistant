"""
User-related models.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Float, Integer, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """User model - links to frontend/backend auth system."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    external_user_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSONB, default=dict)
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
    knowledge_items: Mapped[list["KnowledgeItem"]] = relationship(
        "KnowledgeItem",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    embeddings: Mapped[list["Embedding"]] = relationship(
        "Embedding",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    entities: Mapped[list["Entity"]] = relationship(
        "Entity",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(
        "ChatSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    user_preferences: Mapped[list["UserPreference"]] = relationship(
        "UserPreference",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    user_feedback: Mapped[list["UserFeedback"]] = relationship(
        "UserFeedback",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    integration_syncs: Mapped[list["IntegrationSync"]] = relationship(
        "IntegrationSync",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserPreference(Base):
    """Learned user preferences (procedural memory)."""

    __tablename__ = "user_preferences"

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
    preference_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # email_tone, response_length, working_hours, etc.
    preference_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    preference_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    sample_count: Mapped[int] = mapped_column(Integer, default=1)
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
    user: Mapped["User"] = relationship("User", back_populates="user_preferences")

    __table_args__ = (
        # Unique constraint on user + preference type + key
        {"sqlite_autoincrement": True},
    )


class UserFeedback(Base):
    """User feedback on AI responses."""

    __tablename__ = "user_feedback"

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
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    knowledge_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    feedback_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # rating, edit, accept, reject
    feedback_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="user_feedback")
    message: Mapped[Optional["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="feedback",
    )
    knowledge_item: Mapped[Optional["KnowledgeItem"]] = relationship(
        "KnowledgeItem",
        back_populates="feedback",
    )


# Import for type hints (avoid circular imports)
from app.models.knowledge import KnowledgeItem
from app.models.embedding import Embedding
from app.models.entity import Entity
from app.models.chat import ChatSession, ChatMessage
from app.models.sync import IntegrationSync

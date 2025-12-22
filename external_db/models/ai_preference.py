"""
AI Preference model for external data database.
Mirrors the 'ai_preferences' table from gmail_outlook_db.
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, ForeignKey, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from external_db.database import Base

if TYPE_CHECKING:
    from external_db.models.user import User


class AIPreference(Base):
    """AI preferences model - mirrors external gmail_outlook_db ai_preferences table."""

    __tablename__ = "ai_preferences"

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
    tone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    length: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    include_greeting: Mapped[bool] = mapped_column(Boolean, default=True)
    include_signature: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    user: Mapped["User"] = relationship("User", back_populates="ai_preferences")

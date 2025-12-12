"""
Embedding model for vector storage with pgvector.
"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import String, Text, Integer, ForeignKey, DateTime, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.database import Base
from app.config import get_settings

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.knowledge import KnowledgeItem

settings = get_settings()


class Embedding(Base):
    """
    Vector embeddings for semantic search.

    Uses pgvector for efficient similarity search.
    """

    __tablename__ = "embeddings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    knowledge_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Vector embedding (1536 dimensions for text-embedding-3-small)
    embedding = mapped_column(
        Vector(settings.embedding_dimensions),
        nullable=False,
    )
    embedding_model: Mapped[str] = mapped_column(
        String(50),
        default="text-embedding-3-small",
    )

    # For chunked documents
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    # Relationships
    knowledge_item: Mapped["KnowledgeItem"] = relationship(
        "KnowledgeItem",
        back_populates="embeddings",
    )
    user: Mapped["User"] = relationship("User", back_populates="embeddings")

    __table_args__ = (
        # Index for user queries
        Index("idx_embedding_user", "user_id"),
        # Index for knowledge item + chunk
        Index(
            "idx_embedding_item_chunk",
            "knowledge_item_id",
            "chunk_index",
            unique=True,
        ),
    )


# Note: HNSW index for vector similarity search is created in Alembic migration:
# CREATE INDEX idx_embedding_vector ON embeddings
#     USING hnsw (embedding vector_cosine_ops)
#     WITH (m = 16, ef_construction = 64);

"""
Embedding service for generating and managing vector embeddings.
"""

import asyncio
import hashlib
from typing import Optional
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import KnowledgeItem, Embedding

settings = get_settings()


class EmbeddingService:
    """
    Service for generating and managing embeddings.

    Uses OpenAI's text-embedding-3-small model (1536 dimensions).
    """

    def __init__(self, openai_client: Optional[AsyncOpenAI] = None):
        self.openai = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions

    async def create_embedding(self, text: str) -> Optional[list[float]]:
        """
        Create an embedding vector for the given text.

        Args:
            text: Text to embed (max ~8000 tokens)

        Returns:
            List of floats (1536 dimensions) or None if API fails
        """
        # Clean and truncate text
        text = self._clean_text(text)

        try:
            response = await self.openai.embeddings.create(
                model=self.model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            # Log the error but don't crash - fall back to text search
            import logging
            logging.warning(f"Embedding API failed: {e}. Falling back to text search.")
            return None

    async def create_embeddings_batch(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]:
        """
        Create embeddings for multiple texts in batches.

        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call

        Returns:
            List of embedding vectors
        """
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            cleaned_batch = [self._clean_text(t) for t in batch]

            response = await self.openai.embeddings.create(
                model=self.model,
                input=cleaned_batch,
            )

            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            # Small delay to avoid rate limits
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)

        return all_embeddings

    async def embed_knowledge_item(
        self,
        db: AsyncSession,
        knowledge_item: KnowledgeItem,
        text: Optional[str] = None,
    ) -> Embedding:
        """
        Create and store embedding for a knowledge item.

        Args:
            db: Database session
            knowledge_item: The knowledge item to embed
            text: Optional custom text to embed (defaults to summary or content)

        Returns:
            The created Embedding object
        """
        # Determine text to embed
        if text is None:
            text = knowledge_item.summary or knowledge_item.content or knowledge_item.title or ""

        if not text:
            raise ValueError("No text available to embed")

        # Create embedding
        embedding_vector = await self.create_embedding(text)

        # Check for existing embedding
        existing = await db.execute(
            select(Embedding).where(
                Embedding.knowledge_item_id == knowledge_item.id,
                Embedding.chunk_index == 0,
            )
        )
        existing_embedding = existing.scalar_one_or_none()

        if existing_embedding:
            # Update existing
            existing_embedding.embedding = embedding_vector
            existing_embedding.chunk_text = text[:5000]
            existing_embedding.embedding_model = self.model
            return existing_embedding
        else:
            # Create new
            embedding = Embedding(
                knowledge_item_id=knowledge_item.id,
                user_id=knowledge_item.user_id,
                embedding=embedding_vector,
                embedding_model=self.model,
                chunk_index=0,
                chunk_text=text[:5000],
            )
            db.add(embedding)
            return embedding

    async def embed_document_chunks(
        self,
        db: AsyncSession,
        knowledge_item: KnowledgeItem,
        chunks: list[dict],
    ) -> list[Embedding]:
        """
        Create and store embeddings for document chunks.

        Args:
            db: Database session
            knowledge_item: The parent knowledge item
            chunks: List of chunks with 'text' and 'index' keys

        Returns:
            List of created Embedding objects
        """
        # Delete existing embeddings for this item
        await db.execute(
            delete(Embedding).where(
                Embedding.knowledge_item_id == knowledge_item.id
            )
        )

        # Create embeddings for all chunks
        texts = [chunk["text"] for chunk in chunks]
        embedding_vectors = await self.create_embeddings_batch(texts)

        # Store embeddings
        embeddings = []
        for i, (chunk, vector) in enumerate(zip(chunks, embedding_vectors)):
            embedding = Embedding(
                knowledge_item_id=knowledge_item.id,
                user_id=knowledge_item.user_id,
                embedding=vector,
                embedding_model=self.model,
                chunk_index=i,
                chunk_text=chunk["text"][:5000],
            )
            db.add(embedding)
            embeddings.append(embedding)

        return embeddings

    def chunk_document(
        self,
        content: str,
        chunk_size: int = 600,
        overlap: int = 100,
    ) -> list[dict]:
        """
        Chunk document with overlap for context preservation.

        Args:
            content: Document content
            chunk_size: Target words per chunk
            overlap: Words of overlap between chunks

        Returns:
            List of chunks with 'text', 'index', and 'word_count' keys
        """
        if not content:
            return []

        # Split by paragraphs first
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_words = len(para.split())

            if current_size + para_words > chunk_size and current_chunk:
                # Save chunk
                chunk_text = "\n\n".join(current_chunk)
                chunks.append({
                    "text": chunk_text,
                    "index": len(chunks),
                    "word_count": current_size,
                })

                # Keep last paragraph for overlap
                if current_chunk:
                    current_chunk = [current_chunk[-1]]
                    current_size = len(current_chunk[0].split())
                else:
                    current_chunk = []
                    current_size = 0

            current_chunk.append(para)
            current_size += para_words

        # Don't forget last chunk
        if current_chunk:
            chunks.append({
                "text": "\n\n".join(current_chunk),
                "index": len(chunks),
                "word_count": current_size,
            })

        return chunks

    async def generate_summary(
        self,
        content: str,
        content_type: str = "email",
    ) -> str:
        """
        Generate a concise summary for embedding.

        Args:
            content: Content to summarize
            content_type: Type of content (email, document, task)

        Returns:
            Generated summary
        """
        prompts = {
            "email": """Summarize this email in 2-3 sentences. Capture:
- Main topic or request
- Key people mentioned
- Any action items or deadlines

Email:
{content}""",
            "document": """Summarize this document in 3-4 sentences. Capture:
- Main topic and purpose
- Key points or sections
- Important details or conclusions

Document:
{content}""",
            "task": """Summarize this task in 1-2 sentences. Capture:
- What needs to be done
- Any important context or requirements

Task:
{content}""",
        }

        prompt = prompts.get(content_type, prompts["document"]).format(
            content=content[:4000]
        )

        response = await self.openai.chat.completions.create(
            model=settings.chat_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.3,
        )

        return response.choices[0].message.content

    def content_hash(self, content: str) -> str:
        """Generate a hash of content for change detection."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _clean_text(self, text: str) -> str:
        """Clean text for embedding."""
        # Remove excessive whitespace
        text = " ".join(text.split())

        # Truncate to approximate token limit (8000 tokens ≈ 32000 chars)
        max_chars = 30000
        if len(text) > max_chars:
            text = text[:max_chars] + "..."

        return text

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Alias for create_embedding for backwards compatibility.
        Returns zero vector if API fails instead of None.
        """
        result = await self.create_embedding(text)
        if result is None:
            # Return zero vector on failure - ensures similarity calc still works
            return [0.0] * self.dimensions
        return result

    def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        """
        Calculate cosine similarity between two vectors.

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Similarity score between 0 and 1
        """
        import math

        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

"""
Context retrieval service with semantic search and relevance scoring.

Memory Types Retrieved:
- Semantic Memory: Knowledge items with embeddings (emails, docs, tasks, events)
- Episodic Memory: Recent chat history and past conversations
- Working Memory: Current session context (via Redis)
- Procedural Memory: User preferences (via PreferenceService)

Enhanced with:
- LLM-based query analysis for entity/time/intent extraction
- Metadata field search (from, to, assignee, etc.)
- Natural language date parsing
"""

from datetime import datetime, timedelta, timezone
from typing import Union, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_, func, text, cast, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import KnowledgeItem, Embedding, Entity, EntityMention, ChatSession, ChatMessage
from app.services.embedding_service import EmbeddingService
from app.services.query_analyzer import QueryAnalyzer, QueryAnalysis, get_query_analyzer

settings = get_settings()


class ContextService:
    """
    Service for retrieving relevant context using multiple strategies:
    - Semantic search (embeddings)
    - Entity lookup
    - Time-based filtering
    - Full-text search
    """

    # Source priorities for scoring
    SOURCE_PRIORITY = {
        "gmail": 0.10,
        "outlook": 0.10,
        "gdrive": 0.08,
        "onedrive": 0.08,
        "jira": 0.07,
        "calendar": 0.05,
    }

    # Keywords that indicate specific content types
    CONTENT_TYPE_KEYWORDS = {
        "email": ["gmail", "outlook"],
        "emails": ["gmail", "outlook"],
        "mail": ["gmail", "outlook"],
        "inbox": ["gmail", "outlook"],
        "document": ["gdrive", "onedrive"],
        "documents": ["gdrive", "onedrive"],
        "doc": ["gdrive", "onedrive"],
        "docs": ["gdrive", "onedrive"],
        "file": ["gdrive", "onedrive"],
        "files": ["gdrive", "onedrive"],
        "task": ["jira"],
        "tasks": ["jira"],
        "ticket": ["jira"],
        "tickets": ["jira"],
        "issue": ["jira"],
        "issues": ["jira"],
        "jira": ["jira"],
        "meeting": ["calendar"],
        "meetings": ["calendar"],
        "calendar": ["calendar"],
        "event": ["calendar"],
        "events": ["calendar"],
        "appointment": ["calendar"],
    }

    # Temporal keywords that indicate "most recent" rather than text search
    TEMPORAL_KEYWORDS = ["last", "latest", "recent", "newest", "most recent"]

    # Explicit source boost - when user explicitly mentions a source, boost its relevance
    EXPLICIT_SOURCE_BOOST = 0.4  # Add 0.4 to items from explicitly mentioned sources

    def _detect_content_type_sources(self, query: str) -> Optional[list[str]]:
        """Detect if query mentions specific content types and return corresponding sources."""
        query_lower = query.lower()
        detected_sources = set()

        for keyword, sources in self.CONTENT_TYPE_KEYWORDS.items():
            if keyword in query_lower:
                detected_sources.update(sources)

        return list(detected_sources) if detected_sources else None

    def _is_temporal_query(self, query: str) -> bool:
        """Check if query is asking for most recent items rather than text search."""
        query_lower = query.lower()
        return any(kw in query_lower for kw in self.TEMPORAL_KEYWORDS)

    async def _get_most_recent(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        sources: Optional[list[str]],
        limit: int = 5,
    ) -> list[dict]:
        """Get most recent items by date (for 'last', 'latest', 'recent' queries)."""
        all_items = []

        if sources and len(sources) > 1:
            # When multiple source types are requested, get items from EACH source
            # to ensure balanced retrieval (e.g., emails AND documents)
            per_source_limit = max(2, limit // len(sources))
            for source in sources:
                stmt = (
                    select(KnowledgeItem)
                    .where(KnowledgeItem.user_id == str(user_id))
                    .where(KnowledgeItem.source_type == source)
                    .order_by(KnowledgeItem.source_created_at.desc())
                    .limit(per_source_limit)
                )
                result = await db.execute(stmt)
                all_items.extend(result.scalars().all())
        else:
            # Single source or no source filter
            stmt = (
                select(KnowledgeItem)
                .where(KnowledgeItem.user_id == str(user_id))
                .order_by(KnowledgeItem.source_created_at.desc())
                .limit(limit)
            )
            if sources:
                stmt = stmt.where(KnowledgeItem.source_type.in_(sources))
            result = await db.execute(stmt)
            all_items = list(result.scalars().all())

        # Sort all items by date and limit
        all_items.sort(key=lambda x: x.source_created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        all_items = all_items[:limit]

        return [
            {
                "id": str(item.id),
                "source": item.source_type,
                "source_id": item.source_id,
                "content_type": item.content_type,
                "title": item.title,
                "summary": item.summary,
                "content": item.content,
                "metadata": item.item_metadata,
                "source_created_at": item.source_created_at.isoformat() if item.source_created_at else None,
                "relevance_score": 0.9,  # High score for temporal matches
                "retrieval_method": "temporal",
            }
            for item in all_items
        ]

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self.embedding_service = embedding_service or EmbeddingService()
        self.query_analyzer = get_query_analyzer()

    async def retrieve(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        query: str,
        sources: Optional[list[str]] = None,
        time_filter: Optional[str] = None,
        entity_filter: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 10,
        explicit_sources: Optional[list[str]] = None,
    ) -> dict:
        """
        Retrieve relevant context for a query.

        Args:
            db: Database session
            user_id: User ID
            query: Search query
            sources: Optional list of sources to search (gmail, gdrive, jira, etc.)
            time_filter: Optional time filter (today, yesterday, last_week, last_month)
            entity_filter: Optional entity name to filter by
            date_from: Optional start date
            date_to: Optional end date
            limit: Maximum number of items to return
            explicit_sources: Sources explicitly mentioned by user (for relevance boost)

        Returns:
            {
                "items": [...],
                "entities": [...],
                "total": int
            }
        """
        # Resolve time filter to dates
        if time_filter:
            date_from, date_to = self._resolve_time_filter(time_filter)

        # Run parallel retrieval strategies
        results = []

        # 1. Semantic search (may return empty if embeddings API fails)
        semantic_results = await self._semantic_search(
            db, user_id, query, sources, date_from, date_to, limit * 2
        )
        results.extend(semantic_results)

        # 2. Entity-based retrieval (if entity filter provided)
        if entity_filter:
            entity_results = await self._entity_search(
                db, user_id, entity_filter, sources, date_from, date_to, limit
            )
            results.extend(entity_results)

        # 3. Full-text search
        fts_results = await self._fulltext_search(
            db, user_id, query, sources, date_from, date_to, limit
        )
        results.extend(fts_results)

        # 4. Direct keyword search (fallback when semantic search fails)
        if not semantic_results:
            keyword_results = await self._keyword_search(
                db, user_id, query, sources, date_from, date_to, limit * 2
            )
            results.extend(keyword_results)

        # 5. Fallback: If source filter was applied but no results, retry without filter
        if sources and not results:
            # Try fulltext without source filter
            fts_fallback = await self._fulltext_search(
                db, user_id, query, None, date_from, date_to, limit
            )
            results.extend(fts_fallback)

            # Try keyword search without source filter
            if not fts_fallback:
                keyword_fallback = await self._keyword_search(
                    db, user_id, query, None, date_from, date_to, limit * 2
                )
                results.extend(keyword_fallback)

        # Merge and deduplicate results
        merged = self._merge_results(results)

        # Calculate final relevance scores
        query_entities = await self._extract_query_entities(db, user_id, query)
        scored = self._calculate_relevance(merged, query_entities, date_from, explicit_sources)

        # Sort by score and limit
        scored.sort(key=lambda x: x["relevance_score"], reverse=True)
        final_items = scored[:limit]

        # Extract unique entities from results
        entities = self._extract_entities(final_items)

        return {
            "items": final_items,
            "entities": entities,
            "total": len(final_items),
        }

    async def _semantic_search(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        query: str,
        sources: Optional[list[str]],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: int,
    ) -> list[dict]:
        """Perform semantic search using embeddings."""
        # Create query embedding
        query_embedding = await self.embedding_service.create_embedding(query)

        # If embedding failed (API error), skip semantic search
        if query_embedding is None:
            return []

        # Build query with cosine similarity
        # Using pgvector's <=> operator for cosine distance
        similarity_expr = 1 - Embedding.embedding.cosine_distance(query_embedding)

        stmt = (
            select(
                KnowledgeItem,
                Embedding.chunk_text,
                Embedding.chunk_index,
                similarity_expr.label("similarity"),
            )
            .join(Embedding, Embedding.knowledge_item_id == KnowledgeItem.id)
            .where(KnowledgeItem.user_id == str(user_id))
        )

        # Apply source filter
        if sources:
            stmt = stmt.where(KnowledgeItem.source_type.in_(sources))

        # Apply date filters
        if date_from:
            stmt = stmt.where(KnowledgeItem.source_created_at >= date_from)
        if date_to:
            stmt = stmt.where(KnowledgeItem.source_created_at <= date_to)

        # Order by similarity and limit
        stmt = stmt.order_by(text("similarity DESC")).limit(limit)

        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": str(row.KnowledgeItem.id),
                "source": row.KnowledgeItem.source_type,
                "source_id": row.KnowledgeItem.source_id,
                "content_type": row.KnowledgeItem.content_type,
                "title": row.KnowledgeItem.title,
                "summary": row.KnowledgeItem.summary,
                "content": row.chunk_text or row.KnowledgeItem.content,
                "metadata": row.KnowledgeItem.item_metadata,
                "source_created_at": row.KnowledgeItem.source_created_at.isoformat() if row.KnowledgeItem.source_created_at else None,
                "semantic_score": float(row.similarity),
                "chunk_index": row.chunk_index,
                "retrieval_method": "semantic",
            }
            for row in rows
        ]

    async def _entity_search(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        entity_name: str,
        sources: Optional[list[str]],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: int,
    ) -> list[dict]:
        """Search for items mentioning a specific entity."""
        # Find entity
        normalized = entity_name.lower().strip()

        entity_stmt = select(Entity).where(
            Entity.user_id == str(user_id),
            or_(
                Entity.normalized_name == normalized,
                Entity.normalized_name.contains(normalized),
                Entity.name.ilike(f"%{entity_name}%"),
            )
        )

        result = await db.execute(entity_stmt)
        entities = result.scalars().all()

        if not entities:
            return []

        entity_ids = [e.id for e in entities]

        # Find knowledge items mentioning these entities
        stmt = (
            select(KnowledgeItem, EntityMention.mention_context)
            .join(EntityMention, EntityMention.knowledge_item_id == KnowledgeItem.id)
            .where(
                KnowledgeItem.user_id == str(user_id),
                EntityMention.entity_id.in_(entity_ids),
            )
        )

        if sources:
            stmt = stmt.where(KnowledgeItem.source_type.in_(sources))
        if date_from:
            stmt = stmt.where(KnowledgeItem.source_created_at >= date_from)
        if date_to:
            stmt = stmt.where(KnowledgeItem.source_created_at <= date_to)

        stmt = stmt.order_by(KnowledgeItem.source_created_at.desc()).limit(limit)

        result = await db.execute(stmt)
        rows = result.all()

        return [
            {
                "id": str(row.KnowledgeItem.id),
                "source": row.KnowledgeItem.source_type,
                "source_id": row.KnowledgeItem.source_id,
                "content_type": row.KnowledgeItem.content_type,
                "title": row.KnowledgeItem.title,
                "summary": row.KnowledgeItem.summary,
                "content": row.KnowledgeItem.content,
                "metadata": row.KnowledgeItem.item_metadata,
                "source_created_at": row.KnowledgeItem.source_created_at.isoformat() if row.KnowledgeItem.source_created_at else None,
                "entity_match": entity_name,
                "mention_context": row.mention_context,
                "retrieval_method": "entity",
            }
            for row in rows
        ]

    async def _metadata_search(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        entities: list[str],
        sources: Optional[list[str]],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: int,
    ) -> list[dict]:
        """
        Search for items by metadata fields (from, to, assignee, etc.).

        This is a GENERIC search that checks all relevant metadata fields
        based on the entity being searched (name or email).

        Metadata fields searched:
        - Email: from, to, cc, bcc
        - Jira: assignee, reporter, creator
        - Calendar: organizer, attendees
        - Drive: owner, shared_with
        """
        if not entities:
            return []

        all_results = []

        for entity in entities:
            entity_lower = entity.lower()

            # Build conditions for metadata search
            # Using PostgreSQL JSONB operators and text casting for search
            # Cast entire metadata to text and search within it for the entity
            conditions = []

            # Convert JSONB to text and search - works for all field types (strings, arrays)
            # This is a generic approach that handles any metadata structure
            metadata_text = func.lower(cast(KnowledgeItem.item_metadata, Text))

            # Search in the entire metadata (handles from, to, assignee, etc.)
            conditions.append(metadata_text.contains(entity_lower))

            stmt = (
                select(KnowledgeItem)
                .where(
                    KnowledgeItem.user_id == str(user_id),
                    or_(*conditions)
                )
            )

            if sources:
                stmt = stmt.where(KnowledgeItem.source_type.in_(sources))
            if date_from:
                stmt = stmt.where(KnowledgeItem.source_created_at >= date_from)
            if date_to:
                stmt = stmt.where(KnowledgeItem.source_created_at <= date_to)

            stmt = stmt.order_by(KnowledgeItem.source_created_at.desc()).limit(limit)

            try:
                result = await db.execute(stmt)
                items = result.scalars().all()

                for item in items:
                    all_results.append({
                        "id": str(item.id),
                        "source": item.source_type,
                        "source_id": item.source_id,
                        "content_type": item.content_type,
                        "title": item.title,
                        "summary": item.summary,
                        "content": item.content,
                        "metadata": item.item_metadata,
                        "source_created_at": item.source_created_at.isoformat() if item.source_created_at else None,
                        "entity_match": entity,
                        "retrieval_method": "metadata",
                        "semantic_score": 0.8,  # High score for metadata matches
                    })
            except Exception as e:
                # Log and continue if metadata search fails for an entity
                print(f"Metadata search failed for entity '{entity}': {e}")
                continue

        return all_results

    async def _fulltext_search(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        query: str,
        sources: Optional[list[str]],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: int,
    ) -> list[dict]:
        """Perform full-text search using PostgreSQL's tsvector."""
        # Use plainto_tsquery for natural language search (handles phrases properly)
        tsvector_expr = func.to_tsvector(
            "english",
            func.coalesce(KnowledgeItem.title, "") + " " + func.coalesce(KnowledgeItem.content, "")
        )
        tsquery_expr = func.plainto_tsquery("english", query)

        stmt = (
            select(
                KnowledgeItem,
                func.ts_rank(tsvector_expr, tsquery_expr).label("rank"),
            )
            .where(
                KnowledgeItem.user_id == str(user_id),
                tsvector_expr.op("@@")(tsquery_expr),
            )
        )

        if sources:
            stmt = stmt.where(KnowledgeItem.source_type.in_(sources))
        if date_from:
            stmt = stmt.where(KnowledgeItem.source_created_at >= date_from)
        if date_to:
            stmt = stmt.where(KnowledgeItem.source_created_at <= date_to)

        stmt = stmt.order_by(text("rank DESC")).limit(limit)

        try:
            result = await db.execute(stmt)
            rows = result.all()
        except Exception:
            # Fallback if FTS query fails
            return []

        return [
            {
                "id": str(row.KnowledgeItem.id),
                "source": row.KnowledgeItem.source_type,
                "source_id": row.KnowledgeItem.source_id,
                "content_type": row.KnowledgeItem.content_type,
                "title": row.KnowledgeItem.title,
                "summary": row.KnowledgeItem.summary,
                "content": row.KnowledgeItem.content,
                "metadata": row.KnowledgeItem.item_metadata,
                "source_created_at": row.KnowledgeItem.source_created_at.isoformat() if row.KnowledgeItem.source_created_at else None,
                "fts_rank": float(row.rank) if row.rank else 0,
                "retrieval_method": "fulltext",
            }
            for row in rows
        ]

    async def _keyword_search(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        query: str,
        sources: Optional[list[str]],
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        limit: int,
    ) -> list[dict]:
        """
        Direct keyword search using ILIKE.
        Fallback when embeddings API is unavailable.
        """
        # Extract keywords from query
        keywords = [w.lower() for w in query.split() if len(w) >= 3]

        if not keywords:
            return []

        # Build OR conditions for each keyword
        conditions = []
        for keyword in keywords[:5]:  # Limit to 5 keywords
            conditions.append(
                or_(
                    KnowledgeItem.title.ilike(f"%{keyword}%"),
                    KnowledgeItem.content.ilike(f"%{keyword}%"),
                    KnowledgeItem.summary.ilike(f"%{keyword}%"),
                )
            )

        stmt = (
            select(KnowledgeItem)
            .where(
                KnowledgeItem.user_id == str(user_id),
                or_(*conditions) if conditions else True,
            )
        )

        if sources:
            stmt = stmt.where(KnowledgeItem.source_type.in_(sources))
        if date_from:
            stmt = stmt.where(KnowledgeItem.source_created_at >= date_from)
        if date_to:
            stmt = stmt.where(KnowledgeItem.source_created_at <= date_to)

        stmt = stmt.order_by(KnowledgeItem.source_created_at.desc()).limit(limit)

        try:
            result = await db.execute(stmt)
            items = result.scalars().all()
        except Exception:
            return []

        # Calculate keyword match score
        results = []
        for item in items:
            content_lower = ((item.title or "") + " " + (item.content or "") + " " + (item.summary or "")).lower()
            matches = sum(1 for kw in keywords if kw in content_lower)
            score = matches / len(keywords) if keywords else 0.5

            results.append({
                "id": str(item.id),
                "source": item.source_type,
                "source_id": item.source_id,
                "content_type": item.content_type,
                "title": item.title,
                "summary": item.summary,
                "content": item.content,
                "metadata": item.item_metadata,
                "source_created_at": item.source_created_at.isoformat() if item.source_created_at else None,
                "semantic_score": score,  # Use as base score
                "retrieval_method": "keyword",
            })

        return results

    async def _extract_query_entities(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        query: str,
    ) -> list[dict]:
        """Extract entity mentions from query."""
        words = query.lower().split()
        entities = []

        for word in words:
            if len(word) < 3:
                continue

            stmt = select(Entity).where(
                Entity.user_id == str(user_id),
                or_(
                    Entity.normalized_name == word,
                    Entity.normalized_name.contains(word),
                )
            ).limit(5)

            result = await db.execute(stmt)
            found = result.scalars().all()

            for entity in found:
                entities.append({
                    "id": str(entity.id),
                    "name": entity.name,
                    "type": entity.entity_type,
                })

        return entities

    def _merge_results(self, results: list[dict]) -> list[dict]:
        """Merge and deduplicate results from multiple retrieval methods."""
        seen = {}

        for item in results:
            item_id = item["id"]

            if item_id in seen:
                # Merge scores from different methods
                existing = seen[item_id]
                if "semantic_score" in item and "semantic_score" not in existing:
                    existing["semantic_score"] = item["semantic_score"]
                if "fts_rank" in item and "fts_rank" not in existing:
                    existing["fts_rank"] = item["fts_rank"]
                if "entity_match" in item and "entity_match" not in existing:
                    existing["entity_match"] = item["entity_match"]
            else:
                seen[item_id] = item

        return list(seen.values())

    def _calculate_relevance(
        self,
        items: list[dict],
        query_entities: list[dict],
        query_date: Optional[datetime],
        explicit_sources: Optional[list[str]] = None,
    ) -> list[dict]:
        """
        Calculate final relevance score for each item.

        When user explicitly mentions a source in their query (e.g., "jira tasks"),
        items from that source get a significant boost to ensure they rank higher
        than items from other sources that might just mention related words.
        """
        query_entity_names = {e["name"].lower() for e in query_entities}
        now = datetime.now(timezone.utc)
        explicit_sources_set = set(explicit_sources) if explicit_sources else set()

        for item in items:
            # Base semantic score (0-1)
            semantic_score = item.get("semantic_score", 0.5)

            # Recency boost (0-0.2)
            recency_score = 0.0
            if item.get("source_created_at"):
                try:
                    created = datetime.fromisoformat(item["source_created_at"].replace("Z", "+00:00"))
                    days_old = (now - created.replace(tzinfo=None)).days
                    recency_score = max(0, 0.2 - (days_old / 365) * 0.2)
                except (ValueError, TypeError):
                    pass

            # Entity match bonus (0-0.3)
            entity_score = 0.0
            item_entities = self._extract_item_entities(item)
            matches = len(item_entities & query_entity_names)
            entity_score = min(0.3, matches * 0.1)

            if item.get("entity_match"):
                entity_score = max(entity_score, 0.2)

            # Source priority (0-0.1)
            source = item.get("source", "").lower()
            source_score = self.SOURCE_PRIORITY.get(source, 0.05)

            # FTS boost (0-0.1)
            fts_score = min(0.1, item.get("fts_rank", 0) * 0.05)

            # EXPLICIT SOURCE BOOST (0 or EXPLICIT_SOURCE_BOOST)
            # When user explicitly mentions a source type in query,
            # items from that source get a significant boost
            explicit_source_boost = 0.0
            if explicit_sources_set and source in explicit_sources_set:
                explicit_source_boost = self.EXPLICIT_SOURCE_BOOST

            # Final score
            final_score = (
                semantic_score * 0.5 +
                recency_score +
                entity_score +
                source_score +
                fts_score +
                explicit_source_boost
            )

            item["relevance_score"] = round(final_score, 3)

        return items

    def _extract_item_entities(self, item: dict) -> set[str]:
        """Extract entity names from item metadata."""
        entities = set()
        metadata = item.get("metadata", {})

        # Extract from email metadata
        if "from" in metadata:
            entities.add(metadata["from"].split("@")[0].lower())
        if "to" in metadata:
            for email in metadata.get("to", []):
                entities.add(email.split("@")[0].lower())

        # Extract from Jira metadata
        if "assignee" in metadata:
            entities.add(metadata["assignee"].split("@")[0].lower())
        if "reporter" in metadata:
            entities.add(metadata["reporter"].split("@")[0].lower())

        return entities

    def _extract_entities(self, items: list[dict]) -> list[dict]:
        """Extract unique entities from results."""
        entities = {}

        for item in items:
            metadata = item.get("metadata", {})

            # People from emails
            if item.get("source") in ("gmail", "outlook"):
                if "from" in metadata:
                    email = metadata["from"]
                    if email not in entities:
                        entities[email] = {
                            "type": "person",
                            "name": email.split("@")[0].title(),
                            "email": email,
                        }

            # Entity matches
            if item.get("entity_match"):
                name = item["entity_match"]
                if name not in entities:
                    entities[name] = {
                        "type": "person",
                        "name": name,
                    }

        return list(entities.values())

    def _resolve_time_filter(
        self,
        time_filter: str,
    ) -> tuple[Optional[datetime], Optional[datetime]]:
        """Resolve time filter string to date range."""
        now = datetime.now(timezone.utc)

        filters = {
            "today": (now.replace(hour=0, minute=0, second=0), now),
            "yesterday": (
                (now - timedelta(days=1)).replace(hour=0, minute=0, second=0),
                now.replace(hour=0, minute=0, second=0),
            ),
            "last_week": (now - timedelta(days=7), now),
            "last_month": (now - timedelta(days=30), now),
            "last_3_months": (now - timedelta(days=90), now),
            "last_6_months": (now - timedelta(days=180), now),
        }

        return filters.get(time_filter, (None, None))

    # Session weighting for episodic memory
    SAME_SESSION_WEIGHT = 1.0  # Full weight for current session
    OTHER_SESSION_WEIGHT = 0.5  # Lower weight for other sessions
    EPISODIC_RELEVANCE_THRESHOLD = 0.3  # Minimum semantic similarity to include

    async def get_episodic_memory(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        query: str,
        current_session_id: Optional[str] = None,
        limit: int = 5,
    ) -> list[dict]:
        """
        Retrieve relevant episodic memory (past conversations).

        Uses SEMANTIC SIMILARITY (embeddings) for relevance instead of word overlap.
        Applies session-based weighting:
        - Same session: higher weight (more relevant context)
        - Different session: lower weight (less relevant)
        """
        # Generate query embedding for semantic comparison
        embedding_service = EmbeddingService()
        query_embedding = await embedding_service.generate_embedding(query)

        # Get recent sessions
        sessions_stmt = (
            select(ChatSession)
            .where(ChatSession.user_id == str(user_id))
            .order_by(ChatSession.updated_at.desc())
            .limit(10)
        )
        sessions_result = await db.execute(sessions_stmt)
        sessions = sessions_result.scalars().all()

        relevant_memories = []

        for session in sessions:
            # Determine session weight
            is_current_session = current_session_id and str(session.id) == current_session_id
            session_weight = self.SAME_SESSION_WEIGHT if is_current_session else self.OTHER_SESSION_WEIGHT

            # Get messages from this session
            messages_stmt = (
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.desc())
                .limit(20)
            )
            messages_result = await db.execute(messages_stmt)
            messages = messages_result.scalars().all()

            for message in messages:
                if not message.content:
                    continue

                # Generate embedding for message content and compute semantic similarity
                message_embedding = await embedding_service.generate_embedding(message.content[:1000])
                semantic_similarity = embedding_service.cosine_similarity(query_embedding, message_embedding)

                # Skip if below threshold - not semantically relevant
                if semantic_similarity < self.EPISODIC_RELEVANCE_THRESHOLD:
                    continue

                # Calculate recency score
                days_old = (datetime.now(timezone.utc) - message.created_at).days if message.created_at else 30
                recency_score = max(0, 1 - (days_old / 30))

                # Final relevance: semantic similarity * session weight + recency bonus
                # Cap at 0.5 so episodic doesn't overpower actual data
                relevance = min(0.5, (semantic_similarity * session_weight * 0.6 + recency_score * 0.2))

                # Generate title
                title = session.title
                if not title:
                    preview = message.content[:50].replace('\n', ' ').strip()
                    if len(message.content) > 50:
                        preview += "..."
                    title = f"Chat: {preview}"

                relevant_memories.append({
                    "id": str(message.id),
                    "source": "episodic",
                    "source_id": str(session.id),
                    "content_type": "chat_message",
                    "title": title,
                    "summary": message.content[:200] if message.content else None,
                    "content": message.content,
                    "metadata": {
                        "role": message.role,
                        "session_type": session.session_type,
                        "context_items": message.context_items,
                        "is_current_session": is_current_session,
                    },
                    "source_created_at": message.created_at.isoformat() if message.created_at else None,
                    "relevance_score": round(relevance, 3),
                    "retrieval_method": "episodic",
                })

        # Sort by relevance and return top results
        relevant_memories.sort(key=lambda x: x["relevance_score"], reverse=True)
        return relevant_memories[:limit]

    async def retrieve_with_memory(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        query: str,
        session_id: Optional[str] = None,
        sources: Optional[list[str]] = None,
        time_filter: Optional[str] = None,
        entity_filter: Optional[str] = None,
        include_episodic: bool = True,
        limit: int = 10,
    ) -> dict:
        """
        Enhanced retrieve that includes all memory types.

        Memory Types:
        - Semantic: Knowledge items from emails, docs, tasks (via embeddings)
        - Episodic: Past conversation history
        - Entity: People, projects, topics mentioned
        - Metadata: Items matching entities in from/to/assignee fields

        Uses LLM-based query analysis for:
        - Entity extraction (names, emails)
        - Source detection (emails, tasks, calendar, etc.)
        - Natural language date parsing (November 2025, coming up, etc.)
        """
        # ============================================================
        # STEP 1: Analyze query using LLM-based query analyzer
        # ============================================================
        analysis = await self.query_analyzer.analyze(query)

        # Use analyzed sources if no explicit sources provided
        effective_sources = sources
        if not sources and analysis.sources:
            effective_sources = analysis.sources

        # Use analyzed dates if no time_filter provided
        date_from = analysis.date_from
        date_to = analysis.date_to
        if time_filter:
            # Override with explicit time_filter if provided
            date_from, date_to = self._resolve_time_filter(time_filter)

        # ============================================================
        # STEP 2: Metadata search for extracted entities
        # ============================================================
        metadata_results = []
        if analysis.entities:
            metadata_results = await self._metadata_search(
                db=db,
                user_id=user_id,
                entities=analysis.entities,
                sources=effective_sources,
                date_from=date_from,
                date_to=date_to,
                limit=limit,
            )

        # ============================================================
        # STEP 3: Handle temporal queries (last, latest, recent, coming up)
        # ============================================================
        temporal_results = []
        if analysis.is_temporal and effective_sources:
            temporal_results = await self._get_most_recent(
                db=db,
                user_id=user_id,
                sources=effective_sources,
                limit=limit,
            )

        # ============================================================
        # STEP 4: Get base semantic/entity/fulltext results
        # ============================================================
        base_results = await self.retrieve(
            db=db,
            user_id=user_id,
            query=query,
            sources=effective_sources,
            time_filter=None,  # We handle dates separately
            date_from=date_from,
            date_to=date_to,
            entity_filter=entity_filter or (analysis.entities[0] if analysis.entities else None),
            limit=limit,
            explicit_sources=analysis.sources,  # Boost items from detected sources
        )

        # ============================================================
        # STEP 5: Merge all results (metadata + temporal + semantic)
        # ============================================================
        existing_ids = {item["id"] for item in base_results["items"]}

        # Add metadata search results (high priority for entity matches)
        for item in metadata_results:
            if item["id"] not in existing_ids:
                base_results["items"].append(item)
                existing_ids.add(item["id"])

        # Add temporal results
        for item in temporal_results:
            if item["id"] not in existing_ids:
                base_results["items"].append(item)
                existing_ids.add(item["id"])

        if temporal_results:
            base_results["temporal_count"] = len(temporal_results)

        if metadata_results:
            base_results["metadata_count"] = len(metadata_results)

        # ============================================================
        # STEP 6: Add episodic memory if requested
        # ============================================================
        if include_episodic:
            episodic = await self.get_episodic_memory(
                db=db,
                user_id=user_id,
                query=query,
                current_session_id=session_id,
                limit=3,
            )
            base_results["items"].extend(episodic)
            base_results["episodic_count"] = len(episodic)

        # ============================================================
        # STEP 7: Re-sort by relevance and limit
        # ============================================================
        base_results["items"].sort(
            key=lambda x: x.get("relevance_score", 0),
            reverse=True
        )

        base_results["items"] = base_results["items"][:limit]
        base_results["total"] = len(base_results["items"])

        # Add query analysis info for debugging
        base_results["query_analysis"] = {
            "entities": analysis.entities,
            "sources": analysis.sources,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
            "time_type": analysis.time_type,
            "is_temporal": analysis.is_temporal,
            "confidence": analysis.confidence,
        }

        return base_results

"""
Memory Agent - Centralized RAG and context retrieval.

This agent is the SOLE owner of database access for context retrieval.
All other agents get their context through this agent.

Responsibilities:
1. Semantic search (embeddings)
2. Entity resolution ("Farhan" → farhan@hcms.ai)
3. Date-based retrieval
4. Episodic memory (past conversations)
5. User preferences
"""

from typing import Optional, Union
from uuid import UUID

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeItem, Entity, UserPreference, ChatSession, ChatMessage
from app.services.context_service import ContextService
from app.services.embedding_service import EmbeddingService
from app.schemas.agent_schemas import MemoryContext, ChatRequest


class MemoryAgent:
    """
    Centralized memory agent for RAG and context retrieval.

    Key principle: This is the ONLY agent that touches the database for context.
    All specialist agents receive pre-fetched context from this agent.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.context_service = ContextService(EmbeddingService())

    async def retrieve_context(
        self,
        request: ChatRequest,
        session_id: Optional[str] = None,
        include_episodic: bool = True,
        limit: int = 10,
    ) -> MemoryContext:
        """
        Main method to retrieve all relevant context for a request.

        This method:
        1. Analyzes the query to determine retrieval strategy
        2. Fetches relevant knowledge items (emails, docs, events, tasks)
        3. Resolves entities mentioned in the query
        4. Gets user preferences
        5. Retrieves relevant episodic memory (past conversations)

        Args:
            request: The chat request
            session_id: Current session for episodic filtering
            include_episodic: Whether to include past conversation context
            limit: Max items to retrieve

        Returns:
            MemoryContext with all retrieved context
        """
        # Use the existing context service for main retrieval
        retrieval_result = await self.context_service.retrieve_with_plan(
            db=self.db,
            user_id=request.user_id,
            query=request.message,
            session_id=session_id,
            include_episodic=include_episodic,
            limit=limit,
        )

        # Extract items and query analysis with defensive checks
        if retrieval_result is None:
            retrieval_result = {}
        items = retrieval_result.get("items") or []
        query_analysis = retrieval_result.get("query_analysis") or {}

        # Resolve entities mentioned in the query or found in results
        entities = await self._resolve_entities(
            request.user_id,
            query_analysis.get("filters", {}).get("entities", []),
            items
        )

        # Get user preferences
        preferences = await self._get_user_preferences(request.user_id)

        # Process attachments if any (ad-hoc content)
        if request.attachments:
            attachment_items = self._process_attachments(request.attachments)
            items = attachment_items + items  # Attachments take priority

        return MemoryContext(
            items=items,
            entities=entities,
            user_preferences=preferences,
            episodic=retrieval_result.get("episodic", []),
            query_analysis=query_analysis,
        )

    async def resolve_entity(
        self,
        user_id: str,
        name: str,
    ) -> Optional[dict]:
        """
        Resolve an entity name to full details.

        Args:
            user_id: User ID
            name: Entity name to resolve (e.g., "Farhan")

        Returns:
            Entity details dict or None if not found
        """
        normalized = name.lower().strip()

        # Search in entities table using ILIKE for case-insensitive search
        stmt = select(Entity).where(
            and_(
                Entity.user_id == user_id,
                Entity.name.ilike(f"%{normalized}%")
            )
        ).limit(1)

        result = await self.db.execute(stmt)
        entity = result.scalar_one_or_none()

        if entity:
            return {
                "name": entity.name,
                "normalized_name": entity.normalized_name,
                "type": entity.entity_type,
                "email": entity.email,
                "metadata": entity.entity_metadata or {}
            }

        # Fallback: search in knowledge_items metadata
        # Look for emails/calendar items with this name
        from sqlalchemy import Text, cast
        metadata_as_text = cast(KnowledgeItem.item_metadata, Text)
        stmt = select(KnowledgeItem).where(
            and_(
                KnowledgeItem.user_id == user_id,
                metadata_as_text.ilike(f"%{normalized}%")
            )
        ).limit(5)

        result = await self.db.execute(stmt)
        items = result.scalars().all()

        for item in items:
            metadata = item.item_metadata or {}
            # Check email fields
            if "from" in metadata and normalized in metadata["from"].lower():
                email = metadata["from"]
                return {
                    "name": name,
                    "email": email,
                    "type": "person",
                    "metadata": {}
                }
            if "attendees" in metadata:
                for attendee in metadata.get("attendees", []):
                    if normalized in attendee.lower():
                        return {
                            "name": name,
                            "email": attendee,
                            "type": "person",
                            "metadata": {}
                        }

        return None

    async def _resolve_entities(
        self,
        user_id: str,
        query_entities: list[str],
        items: list[dict],
    ) -> dict[str, dict]:
        """Resolve all entities from query and results."""
        entities = {}

        # Defensive checks for None
        if query_entities is None:
            query_entities = []
        if items is None:
            items = []

        # Resolve entities mentioned in query
        for name in query_entities:
            resolved = await self.resolve_entity(user_id, name)
            if resolved:
                entities[name] = resolved

        # Extract entities from results
        for item in items:
            metadata = item.get("metadata", {})

            # Email: from field
            if item.get("source") in ("gmail", "outlook"):
                from_email = metadata.get("from")
                if from_email and from_email not in entities:
                    name_part = from_email.split("@")[0].replace(".", " ").title()
                    entities[from_email] = {
                        "name": name_part,
                        "email": from_email,
                        "type": "person",
                        "metadata": {}
                    }

            # Calendar: organizer and attendees
            if item.get("source") == "calendar":
                organizer = metadata.get("organizer")
                if organizer and organizer not in entities:
                    entities[organizer] = {
                        "name": organizer.split("@")[0].replace(".", " ").title(),
                        "email": organizer,
                        "type": "person",
                        "metadata": {}
                    }

            # Jira: assignee and reporter
            if item.get("source") == "jira":
                for field in ["assignee", "reporter"]:
                    person = metadata.get(field)
                    if person and person not in entities:
                        entities[person] = {
                            "name": person,
                            "type": "person",
                            "metadata": {}
                        }

        return entities

    async def _get_user_preferences(self, user_id: str) -> dict:
        """Get user preferences."""
        try:
            stmt = select(UserPreference).where(
                UserPreference.user_id == user_id
            )
            result = await self.db.execute(stmt)
            prefs = result.scalars().all()

            preferences = {}
            for pref in prefs:
                if pref.category not in preferences:
                    preferences[pref.category] = {}
                preferences[pref.category][pref.key] = {
                    "value": pref.value,
                    "source": pref.source
                }

            return preferences
        except Exception:
            return {}

    def _process_attachments(self, attachments: list) -> list[dict]:
        """Process ad-hoc attachments into context items."""
        items = []

        for attachment in attachments:
            if attachment.content:
                content = attachment.content

                if attachment.type == "email":
                    items.append({
                        "id": "attachment_email",
                        "source": "attachment",
                        "content_type": "email",
                        "title": content.get("subject", "Email"),
                        "summary": content.get("body", "")[:500],
                        "content": content.get("body", ""),
                        "metadata": {
                            "from": content.get("from"),
                            "to": content.get("to"),
                            "date": content.get("date"),
                        },
                        "relevance_score": 1.0,  # Highest priority
                    })

                elif attachment.type == "email_thread":
                    for i, email in enumerate(content.get("emails", [])):
                        items.append({
                            "id": f"attachment_thread_{i}",
                            "source": "attachment",
                            "content_type": "email",
                            "title": email.get("subject", "Email"),
                            "content": email.get("body", ""),
                            "metadata": {
                                "from": email.get("from"),
                                "to": email.get("to"),
                                "date": email.get("date"),
                            },
                            "relevance_score": 0.95,
                        })

                elif attachment.type == "document":
                    items.append({
                        "id": "attachment_document",
                        "source": "attachment",
                        "content_type": "document",
                        "title": content.get("title", "Document"),
                        "content": content.get("content", ""),
                        "metadata": content.get("metadata", {}),
                        "relevance_score": 1.0,
                    })

        return items

    async def get_recent_session_context(
        self,
        user_id: str,
        session_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Get recent messages from current session."""
        try:
            stmt = (
                select(ChatMessage)
                .join(ChatSession)
                .where(
                    and_(
                        ChatSession.id == session_id,
                        ChatSession.user_id == user_id,
                    )
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
            )

            result = await self.db.execute(stmt)
            messages = result.scalars().all()

            return [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None,
                }
                for msg in reversed(messages)  # Oldest first
            ]
        except Exception:
            return []

    async def search_by_source(
        self,
        user_id: str,
        source_type: str,
        query: Optional[str] = None,
        limit: int = 10,
    ) -> list[dict]:
        """Search items from a specific source."""
        from app.services.context_service import ContextService

        result = await self.context_service.retrieve_with_plan(
            db=self.db,
            user_id=user_id,
            query=query or f"show me {source_type}",
            include_episodic=False,
            limit=limit,
        )

        # Filter to only requested source
        items = [
            item for item in result.get("items", [])
            if item.get("source") == source_type
        ]

        return items

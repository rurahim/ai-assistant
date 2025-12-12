"""
Entity extraction and management service.
"""

import json
from datetime import datetime
from typing import Union,  Optional
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.models import Entity, EntityMention, KnowledgeItem

settings = get_settings()


class EntityService:
    """
    Service for extracting and managing entities.

    Entities include:
    - People (from emails, Jira, calendar)
    - Projects (from Jira, documents)
    - Topics (from content analysis)
    - Companies/Organizations
    """

    def __init__(self, openai_client: Optional[AsyncOpenAI] = None):
        self.openai = openai_client or AsyncOpenAI(api_key=settings.openai_api_key)

    async def extract_and_store(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        knowledge_item: KnowledgeItem,
        raw_data: dict,
    ) -> list[Entity]:
        """
        Extract entities from content and store them.

        Args:
            db: Database session
            user_id: User ID
            knowledge_item: The knowledge item source
            raw_data: Raw data from the source

        Returns:
            List of extracted/created entities
        """
        entities = []

        # Extract based on source type
        source_type = knowledge_item.source_type

        if source_type in ("gmail", "outlook"):
            entities.extend(
                await self._extract_from_email(db, user_id, knowledge_item, raw_data)
            )
        elif source_type == "jira":
            entities.extend(
                await self._extract_from_jira(db, user_id, knowledge_item, raw_data)
            )
        elif source_type == "calendar":
            entities.extend(
                await self._extract_from_calendar(db, user_id, knowledge_item, raw_data)
            )

        # Use LLM to extract additional entities from content
        content = knowledge_item.summary or knowledge_item.content
        if content:
            llm_entities = await self._extract_with_llm(content)
            for entity_data in llm_entities:
                entity = await self._create_or_update_entity(
                    db, user_id, entity_data
                )
                if entity:
                    await self._create_mention(
                        db, entity.id, knowledge_item.id, entity_data.get("context")
                    )
                    entities.append(entity)

        return entities

    async def _extract_from_email(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        knowledge_item: KnowledgeItem,
        email: dict,
    ) -> list[Entity]:
        """Extract entities from email metadata."""
        entities = []

        # Extract sender
        if email.get("from"):
            entity = await self._create_or_update_entity(
                db,
                user_id,
                {
                    "type": "person",
                    "name": self._email_to_name(email["from"]),
                    "email": email["from"],
                },
            )
            if entity:
                await self._create_mention(
                    db, entity.id, knowledge_item.id, f"Email from {email['from']}"
                )
                entities.append(entity)

        # Extract recipients
        for recipient in email.get("to", []) + email.get("cc", []):
            entity = await self._create_or_update_entity(
                db,
                user_id,
                {
                    "type": "person",
                    "name": self._email_to_name(recipient),
                    "email": recipient,
                },
            )
            if entity:
                await self._create_mention(
                    db, entity.id, knowledge_item.id, f"Email to {recipient}"
                )
                entities.append(entity)

        return entities

    async def _extract_from_jira(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        knowledge_item: KnowledgeItem,
        issue: dict,
    ) -> list[Entity]:
        """Extract entities from Jira issue."""
        entities = []

        # Project entity
        if issue.get("project_key"):
            entity = await self._create_or_update_entity(
                db,
                user_id,
                {
                    "type": "project",
                    "name": issue["project_key"],
                    "source": "jira",
                },
            )
            if entity:
                await self._create_mention(
                    db, entity.id, knowledge_item.id, f"Jira project {issue['project_key']}"
                )
                entities.append(entity)

        # Assignee
        if issue.get("assignee"):
            entity = await self._create_or_update_entity(
                db,
                user_id,
                {
                    "type": "person",
                    "name": self._email_to_name(issue["assignee"]),
                    "email": issue["assignee"],
                },
            )
            if entity:
                await self._create_mention(
                    db, entity.id, knowledge_item.id, f"Assigned to {issue['assignee']}"
                )
                entities.append(entity)

        # Reporter
        if issue.get("reporter"):
            entity = await self._create_or_update_entity(
                db,
                user_id,
                {
                    "type": "person",
                    "name": self._email_to_name(issue["reporter"]),
                    "email": issue["reporter"],
                },
            )
            if entity:
                await self._create_mention(
                    db, entity.id, knowledge_item.id, f"Reported by {issue['reporter']}"
                )
                entities.append(entity)

        return entities

    async def _extract_from_calendar(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        knowledge_item: KnowledgeItem,
        event: dict,
    ) -> list[Entity]:
        """Extract entities from calendar event."""
        entities = []

        # Attendees
        for attendee in event.get("attendees", []):
            email = attendee.get("email") if isinstance(attendee, dict) else attendee
            name = attendee.get("name") if isinstance(attendee, dict) else None

            entity = await self._create_or_update_entity(
                db,
                user_id,
                {
                    "type": "person",
                    "name": name or self._email_to_name(email),
                    "email": email,
                },
            )
            if entity:
                await self._create_mention(
                    db, entity.id, knowledge_item.id, f"Calendar attendee: {email}"
                )
                entities.append(entity)

        return entities

    async def _extract_with_llm(self, content: str) -> list[dict]:
        """Use LLM to extract additional entities from content."""
        if not content or len(content) < 50:
            return []

        prompt = f"""Extract entities from this text. Return a JSON array.

Text:
{content[:3000]}

Extract:
- People (name, email if mentioned)
- Projects/Products mentioned
- Companies/Organizations
- Key topics/subjects

Return format:
{{"entities": [
  {{"type": "person", "name": "John Smith", "email": "john@example.com"}},
  {{"type": "project", "name": "Mobile App"}},
  {{"type": "company", "name": "Acme Inc"}},
  {{"type": "topic", "name": "budget planning"}}
]}}

Only include entities that are clearly mentioned. Return empty array if none found."""

        try:
            response = await self.openai.chat.completions.create(
                model=settings.chat_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0,
                response_format={"type": "json_object"},
            )

            result = json.loads(response.choices[0].message.content)
            return result.get("entities", [])
        except Exception:
            return []

    async def _create_or_update_entity(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        entity_data: dict,
    ) -> Optional[Entity]:
        """Create or update an entity."""
        entity_type = entity_data.get("type")
        name = entity_data.get("name")

        if not name or not entity_type:
            return None

        normalized_name = name.lower().strip()

        # Build metadata
        metadata = {}
        if entity_data.get("email"):
            metadata["emails"] = [entity_data["email"]]
        if entity_data.get("source"):
            metadata["source"] = entity_data["source"]

        # Try to find existing entity
        stmt = select(Entity).where(
            Entity.user_id == str(user_id),
            Entity.entity_type == entity_type,
            Entity.normalized_name == normalized_name,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing
            existing.mention_count += 1
            existing.last_seen_at = datetime.utcnow()

            # Merge metadata
            if metadata.get("emails"):
                current_emails = existing.entity_metadata.get("emails", [])
                new_email = metadata["emails"][0]
                if new_email not in current_emails:
                    current_emails.append(new_email)
                    existing.entity_metadata = {**existing.entity_metadata, "emails": current_emails}

            return existing
        else:
            # Create new
            entity = Entity(
                user_id=str(user_id),
                entity_type=entity_type,
                name=name,
                normalized_name=normalized_name,
                entity_metadata=metadata,
                mention_count=1,
            )
            db.add(entity)
            await db.flush()
            return entity

    async def _create_mention(
        self,
        db: AsyncSession,
        entity_id: UUID,
        knowledge_item_id: UUID,
        context: Optional[str] = None,
    ) -> None:
        """Create an entity mention link."""
        stmt = insert(EntityMention).values(
            entity_id=entity_id,
            knowledge_item_id=knowledge_item_id,
            mention_context=context,
        ).on_conflict_do_nothing(
            index_elements=["entity_id", "knowledge_item_id"]
        )
        await db.execute(stmt)

    def _email_to_name(self, email: str) -> str:
        """Convert email address to a display name."""
        if not email:
            return "Unknown"

        # Extract local part and convert to title case
        local_part = email.split("@")[0]
        # Replace common separators with spaces
        name = local_part.replace(".", " ").replace("_", " ").replace("-", " ")
        return name.title()

    async def get_user_entities(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Entity], int]:
        """Get entities for a user with optional type filter."""
        # Count query
        count_stmt = select(func.count(Entity.id)).where(
            Entity.user_id == str(user_id)
        )
        if entity_type:
            count_stmt = count_stmt.where(Entity.entity_type == entity_type)

        count_result = await db.execute(count_stmt)
        total = count_result.scalar()

        # Main query
        stmt = select(Entity).where(
            Entity.user_id == str(user_id)
        )
        if entity_type:
            stmt = stmt.where(Entity.entity_type == entity_type)

        stmt = stmt.order_by(Entity.mention_count.desc()).offset(offset).limit(limit)

        result = await db.execute(stmt)
        entities = result.scalars().all()

        return list(entities), total

    async def get_entity_context(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        entity_id: Union[str, UUID],
        limit: int = 20,
    ) -> dict:
        """Get all context related to an entity."""
        # Get entity
        entity_result = await db.execute(
            select(Entity).where(
                Entity.id == str(entity_id),
                Entity.user_id == str(user_id),
            )
        )
        entity = entity_result.scalar_one_or_none()

        if not entity:
            return None

        # Get related knowledge items
        stmt = (
            select(KnowledgeItem, EntityMention.mention_context)
            .join(EntityMention, EntityMention.knowledge_item_id == KnowledgeItem.id)
            .where(EntityMention.entity_id == entity.id)
            .order_by(KnowledgeItem.source_created_at.desc())
            .limit(limit)
        )

        result = await db.execute(stmt)
        items = result.all()

        # Group by source
        by_source = {}
        for item, context in items:
            source = item.source_type
            if source not in by_source:
                by_source[source] = {"count": 0, "items": []}
            by_source[source]["count"] += 1
            by_source[source]["items"].append({
                "id": str(item.id),
                "title": item.title,
                "summary": item.summary,
                "date": item.source_created_at.isoformat() if item.source_created_at else None,
                "context": context,
            })

        return {
            "entity": {
                "id": str(entity.id),
                "name": entity.name,
                "type": entity.entity_type,
                "metadata": entity.entity_metadata,
                "mention_count": entity.mention_count,
            },
            "related_items": by_source,
        }

    async def find_entity(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        name: str,
    ) -> Optional[Entity]:
        """Find an entity by name (fuzzy match)."""
        normalized = name.lower().strip()

        # Try exact match first
        stmt = select(Entity).where(
            Entity.user_id == str(user_id),
            Entity.normalized_name == normalized,
        )
        result = await db.execute(stmt)
        entity = result.scalar_one_or_none()

        if entity:
            return entity

        # Try partial match
        stmt = select(Entity).where(
            Entity.user_id == str(user_id),
            Entity.normalized_name.contains(normalized),
        ).order_by(Entity.mention_count.desc()).limit(1)

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

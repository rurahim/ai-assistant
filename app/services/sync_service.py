"""
Sync service for synchronizing data from external sources.
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import Union,  Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.models import (
    User,
    KnowledgeItem,
    Embedding,
    Entity,
    EntityMention,
    IntegrationSync,
)
from app.core.external_api import ExternalAPIClient
from app.services.embedding_service import EmbeddingService
from app.services.entity_service import EntityService

settings = get_settings()


class SyncService:
    """
    Service for synchronizing data from external sources.

    Handles:
    - Initial full sync
    - Incremental sync
    - Real-time webhook updates
    """

    def __init__(
        self,
        external_api: Optional[ExternalAPIClient] = None,
        embedding_service: Optional[EmbeddingService] = None,
        entity_service: Optional[EntityService] = None,
    ):
        self.external_api = external_api
        self.embedding_service = embedding_service or EmbeddingService()
        self.entity_service = entity_service or EntityService()

    async def initial_sync(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        sources: list[str],
        config: Optional[dict] = None,
    ) -> str:
        """
        Trigger initial sync for a new user.

        Args:
            db: Database session
            user_id: User ID
            sources: List of sources to sync (gmail, gdrive, jira, etc.)
            config: Optional sync configuration

        Returns:
            Sync ID for tracking
        """
        sync_id = str(uuid.uuid4())
        config = config or {}

        # Create or update sync records for each source
        for source in sources:
            stmt = insert(IntegrationSync).values(
                user_id=str(user_id),
                source_type=source,
                status="pending",
            ).on_conflict_do_update(
                index_elements=["user_id", "source_type"],
                set_={"status": "pending", "error_message": None},
            )
            await db.execute(stmt)

        await db.commit()

        # Note: Actual sync is triggered via Celery task
        # Return sync_id for tracking
        return sync_id

    async def sync_gmail(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        days: int = 30,
    ) -> int:
        """
        Sync Gmail emails for a user.

        Returns:
            Number of items synced
        """
        await self._update_sync_status(db, user_id, "gmail", "syncing")

        try:
            since = datetime.utcnow() - timedelta(days=days)
            cursor = None
            total_synced = 0

            while True:
                # Fetch batch from external API
                data = await self.external_api.get_emails(
                    user_id=user_id,
                    since=since,
                    limit=100,
                    cursor=cursor,
                )

                # Process each email
                for email in data.get("items", []):
                    await self._process_email(db, user_id, email)
                    total_synced += 1

                # Commit batch
                await db.commit()

                # Check pagination
                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")

            await self._update_sync_status(
                db, user_id, "gmail", "completed", total_synced
            )
            return total_synced

        except Exception as e:
            await self._update_sync_status(
                db, user_id, "gmail", "failed", error=str(e)
            )
            raise

    async def sync_gdrive(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        months: int = 6,
    ) -> int:
        """Sync Google Drive documents for a user."""
        await self._update_sync_status(db, user_id, "gdrive", "syncing")

        try:
            since = datetime.utcnow() - timedelta(days=months * 30)
            cursor = None
            total_synced = 0

            while True:
                data = await self.external_api.get_documents(
                    user_id=user_id,
                    since=since,
                    limit=50,
                    cursor=cursor,
                )

                for doc in data.get("items", []):
                    await self._process_document(db, user_id, doc)
                    total_synced += 1

                await db.commit()

                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")

            await self._update_sync_status(
                db, user_id, "gdrive", "completed", total_synced
            )
            return total_synced

        except Exception as e:
            await self._update_sync_status(
                db, user_id, "gdrive", "failed", error=str(e)
            )
            raise

    async def sync_jira(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        months: int = 3,
    ) -> int:
        """Sync Jira issues for a user."""
        await self._update_sync_status(db, user_id, "jira", "syncing")

        try:
            since = datetime.utcnow() - timedelta(days=months * 30)
            cursor = None
            total_synced = 0

            while True:
                data = await self.external_api.get_jira_issues(
                    user_id=user_id,
                    since=since,
                    limit=100,
                    cursor=cursor,
                )

                for issue in data.get("items", []):
                    await self._process_jira_issue(db, user_id, issue)
                    total_synced += 1

                await db.commit()

                if not data.get("has_more"):
                    break
                cursor = data.get("next_cursor")

            await self._update_sync_status(
                db, user_id, "jira", "completed", total_synced
            )
            return total_synced

        except Exception as e:
            await self._update_sync_status(
                db, user_id, "jira", "failed", error=str(e)
            )
            raise

    async def sync_calendar(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        days: int = 30,
    ) -> int:
        """Sync calendar events for a user."""
        await self._update_sync_status(db, user_id, "calendar", "syncing")

        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            end_date = datetime.utcnow() + timedelta(days=days)
            total_synced = 0

            data = await self.external_api.get_events(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
                limit=200,
            )

            for event in data.get("items", []):
                await self._process_calendar_event(db, user_id, event)
                total_synced += 1

            await db.commit()

            await self._update_sync_status(
                db, user_id, "calendar", "completed", total_synced
            )
            return total_synced

        except Exception as e:
            await self._update_sync_status(
                db, user_id, "calendar", "failed", error=str(e)
            )
            raise

    async def _process_email(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        email: dict,
    ) -> None:
        """Process and store a single email."""
        # Generate summary for embedding
        summary = await self.embedding_service.generate_summary(
            f"From: {email.get('from', '')}\n"
            f"To: {', '.join(email.get('to', []))}\n"
            f"Subject: {email.get('subject', '')}\n"
            f"Body: {email.get('body_text', '')[:3000]}",
            content_type="email",
        )

        # Create or update knowledge item
        stmt = insert(KnowledgeItem).values(
            user_id=str(user_id),
            source_type="gmail",
            source_id=email["id"],
            content_type="email",
            title=email.get("subject"),
            summary=summary,
            content=email.get("body_text", "")[:10000],
            metadata={
                "from": email.get("from"),
                "to": email.get("to", []),
                "cc": email.get("cc", []),
                "thread_id": email.get("thread_id"),
                "labels": email.get("labels", []),
                "is_read": email.get("is_read"),
                "attachments": email.get("attachments", []),
            },
            source_created_at=datetime.fromisoformat(email["date"].replace("Z", "+00:00")) if email.get("date") else None,
        ).on_conflict_do_update(
            index_elements=["user_id", "source_type", "source_id"],
            set_={
                "summary": summary,
                "content": email.get("body_text", "")[:10000],
                "metadata": {
                    "from": email.get("from"),
                    "to": email.get("to", []),
                    "thread_id": email.get("thread_id"),
                    "labels": email.get("labels", []),
                },
                "synced_at": datetime.utcnow(),
            },
        ).returning(KnowledgeItem.id)

        result = await db.execute(stmt)
        item_id = result.scalar_one()

        # Get the knowledge item for embedding
        item_result = await db.execute(
            select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        )
        knowledge_item = item_result.scalar_one()

        # Create embedding
        await self.embedding_service.embed_knowledge_item(
            db, knowledge_item, summary
        )

        # Extract and store entities
        await self.entity_service.extract_and_store(
            db, user_id, knowledge_item, email
        )

    async def _process_document(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        doc: dict,
    ) -> None:
        """Process and store a document with chunking."""
        content = doc.get("content_text", "")

        # Chunk the document
        chunks = self.embedding_service.chunk_document(content)

        # Create or update knowledge item
        stmt = insert(KnowledgeItem).values(
            user_id=str(user_id),
            source_type="gdrive",
            source_id=doc["id"],
            content_type="document",
            title=doc.get("name"),
            content=content[:50000],
            metadata={
                "mime_type": doc.get("mime_type"),
                "folder_path": doc.get("folder_path"),
                "total_chunks": len(chunks),
                "size_bytes": doc.get("size_bytes"),
                "owner": doc.get("owner"),
            },
            source_created_at=datetime.fromisoformat(doc["created_at"].replace("Z", "+00:00")) if doc.get("created_at") else None,
            source_updated_at=datetime.fromisoformat(doc["modified_at"].replace("Z", "+00:00")) if doc.get("modified_at") else None,
        ).on_conflict_do_update(
            index_elements=["user_id", "source_type", "source_id"],
            set_={
                "title": doc.get("name"),
                "content": content[:50000],
                "metadata": {
                    "mime_type": doc.get("mime_type"),
                    "folder_path": doc.get("folder_path"),
                    "total_chunks": len(chunks),
                },
                "synced_at": datetime.utcnow(),
            },
        ).returning(KnowledgeItem.id)

        result = await db.execute(stmt)
        item_id = result.scalar_one()

        # Get the knowledge item
        item_result = await db.execute(
            select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        )
        knowledge_item = item_result.scalar_one()

        # Create embeddings for chunks
        if chunks:
            await self.embedding_service.embed_document_chunks(
                db, knowledge_item, chunks
            )

    async def _process_jira_issue(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        issue: dict,
    ) -> None:
        """Process and store a Jira issue."""
        # Combine title and description for embedding
        text_for_embedding = f"{issue.get('summary', '')}\n\n{issue.get('description', '')}"

        # Create or update knowledge item
        stmt = insert(KnowledgeItem).values(
            user_id=str(user_id),
            source_type="jira",
            source_id=issue["key"],
            content_type="task",
            title=issue.get("summary"),
            content=issue.get("description", ""),
            metadata={
                "project_key": issue.get("project_key"),
                "type": issue.get("type"),
                "status": issue.get("status"),
                "priority": issue.get("priority"),
                "assignee": issue.get("assignee"),
                "reporter": issue.get("reporter"),
                "labels": issue.get("labels", []),
                "components": issue.get("components", []),
            },
            source_created_at=datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00")) if issue.get("created_at") else None,
            source_updated_at=datetime.fromisoformat(issue["updated_at"].replace("Z", "+00:00")) if issue.get("updated_at") else None,
        ).on_conflict_do_update(
            index_elements=["user_id", "source_type", "source_id"],
            set_={
                "title": issue.get("summary"),
                "content": issue.get("description", ""),
                "metadata": {
                    "project_key": issue.get("project_key"),
                    "type": issue.get("type"),
                    "status": issue.get("status"),
                    "priority": issue.get("priority"),
                    "assignee": issue.get("assignee"),
                    "reporter": issue.get("reporter"),
                    "labels": issue.get("labels", []),
                },
                "synced_at": datetime.utcnow(),
            },
        ).returning(KnowledgeItem.id)

        result = await db.execute(stmt)
        item_id = result.scalar_one()

        # Get the knowledge item
        item_result = await db.execute(
            select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        )
        knowledge_item = item_result.scalar_one()

        # Create embedding
        await self.embedding_service.embed_knowledge_item(
            db, knowledge_item, text_for_embedding
        )

        # Extract entities
        await self.entity_service.extract_and_store(
            db, user_id, knowledge_item, issue
        )

    async def _process_calendar_event(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        event: dict,
    ) -> None:
        """Process and store a calendar event."""
        text_for_embedding = f"{event.get('title', '')}\n{event.get('description', '')}"

        stmt = insert(KnowledgeItem).values(
            user_id=str(user_id),
            source_type="calendar",
            source_id=event["id"],
            content_type="event",
            title=event.get("title"),
            content=event.get("description", ""),
            metadata={
                "start": event.get("start"),
                "end": event.get("end"),
                "location": event.get("location"),
                "attendees": event.get("attendees", []),
                "recurrence": event.get("recurrence"),
                "meet_link": event.get("meet_link"),
            },
            source_created_at=datetime.fromisoformat(event["start"].replace("Z", "+00:00")) if event.get("start") else None,
        ).on_conflict_do_update(
            index_elements=["user_id", "source_type", "source_id"],
            set_={
                "title": event.get("title"),
                "content": event.get("description", ""),
                "metadata": {
                    "start": event.get("start"),
                    "end": event.get("end"),
                    "attendees": event.get("attendees", []),
                },
                "synced_at": datetime.utcnow(),
            },
        ).returning(KnowledgeItem.id)

        result = await db.execute(stmt)
        item_id = result.scalar_one()

        # Get the knowledge item
        item_result = await db.execute(
            select(KnowledgeItem).where(KnowledgeItem.id == item_id)
        )
        knowledge_item = item_result.scalar_one()

        # Create embedding (light index for calendar)
        await self.embedding_service.embed_knowledge_item(
            db, knowledge_item, text_for_embedding
        )

    async def _update_sync_status(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        source: str,
        status: str,
        items_synced: int = 0,
        error: Optional[str] = None,
    ) -> None:
        """Update sync status in database."""
        stmt = (
            select(IntegrationSync)
            .where(
                IntegrationSync.user_id == str(user_id),
                IntegrationSync.source_type == source,
            )
        )
        result = await db.execute(stmt)
        sync_record = result.scalar_one_or_none()

        if sync_record:
            sync_record.status = status
            sync_record.items_synced = items_synced
            sync_record.error_message = error
            if status == "completed":
                sync_record.last_sync_at = datetime.utcnow()
            await db.commit()

    async def process_webhook_item(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        source: str,
        source_id: str,
        content_type: str,
        data: dict,
    ) -> None:
        """Process a single item from a webhook (real-time update)."""
        if source == "gmail":
            await self._process_email(db, user_id, data)
        elif source == "gdrive":
            await self._process_document(db, user_id, data)
        elif source == "jira":
            await self._process_jira_issue(db, user_id, data)
        elif source == "calendar":
            await self._process_calendar_event(db, user_id, data)

        await db.commit()

    async def delete_item(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        source: str,
        source_id: str,
    ) -> bool:
        """Delete a knowledge item and its related data."""
        # Find the item
        stmt = select(KnowledgeItem).where(
            KnowledgeItem.user_id == str(user_id),
            KnowledgeItem.source_type == source,
            KnowledgeItem.source_id == source_id,
        )
        result = await db.execute(stmt)
        item = result.scalar_one_or_none()

        if not item:
            return False

        # Delete (cascades to embeddings and entity_mentions)
        await db.delete(item)
        await db.commit()

        return True

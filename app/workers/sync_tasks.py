"""
Celery tasks for data synchronization.
"""

import asyncio
from typing import Optional

from celery import shared_task

from app.workers.celery_app import celery_app


def run_async(coro):
    """Run async function in Celery task."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3)
def initial_sync_task(
    self,
    user_id: str,
    sources: list[str],
    config: Optional[dict] = None,
):
    """
    Task for initial full sync of a user's data.

    This is triggered when a new user connects their accounts.
    """
    return run_async(_initial_sync_async(user_id, sources, config))


async def _initial_sync_async(
    user_id: str,
    sources: list[str],
    config: Optional[dict] = None,
):
    """Async implementation of initial sync."""
    from app.database import get_db_context
    from app.core.external_api import ExternalAPIClient
    from app.services import SyncService

    config = config or {}
    results = {}

    async with get_db_context() as db:
        async with ExternalAPIClient() as api:
            sync_service = SyncService(external_api=api)

            for source in sources:
                try:
                    if source == "gmail":
                        count = await sync_service.sync_gmail(
                            db, user_id, days=config.get("gmail_days", 30)
                        )
                        results["gmail"] = {"status": "completed", "items": count}

                    elif source == "gdrive":
                        count = await sync_service.sync_gdrive(
                            db, user_id, months=config.get("document_months", 6)
                        )
                        results["gdrive"] = {"status": "completed", "items": count}

                    elif source == "jira":
                        count = await sync_service.sync_jira(
                            db, user_id, months=config.get("jira_months", 3)
                        )
                        results["jira"] = {"status": "completed", "items": count}

                    elif source == "calendar":
                        count = await sync_service.sync_calendar(
                            db, user_id, days=config.get("calendar_days", 30)
                        )
                        results["calendar"] = {"status": "completed", "items": count}

                    elif source == "outlook":
                        # Same as Gmail but for Outlook
                        count = await sync_service.sync_gmail(
                            db, user_id, days=config.get("gmail_days", 30)
                        )
                        results["outlook"] = {"status": "completed", "items": count}

                    elif source == "onedrive":
                        # Same as GDrive but for OneDrive
                        count = await sync_service.sync_gdrive(
                            db, user_id, months=config.get("document_months", 6)
                        )
                        results["onedrive"] = {"status": "completed", "items": count}

                except Exception as e:
                    results[source] = {"status": "failed", "error": str(e)}

    return results


@celery_app.task(bind=True, max_retries=3)
def sync_gmail_task(
    self,
    user_id: str,
    days: int = 30,
):
    """Task for syncing Gmail emails."""
    return run_async(_sync_gmail_async(user_id, days))


async def _sync_gmail_async(user_id: str, days: int):
    """Async implementation of Gmail sync."""
    from app.database import get_db_context
    from app.core.external_api import ExternalAPIClient
    from app.services import SyncService

    async with get_db_context() as db:
        async with ExternalAPIClient() as api:
            sync_service = SyncService(external_api=api)
            count = await sync_service.sync_gmail(db, user_id, days=days)
            return {"status": "completed", "items": count}


@celery_app.task(bind=True, max_retries=3)
def sync_gdrive_task(
    self,
    user_id: str,
    months: int = 6,
):
    """Task for syncing Google Drive documents."""
    return run_async(_sync_gdrive_async(user_id, months))


async def _sync_gdrive_async(user_id: str, months: int):
    """Async implementation of GDrive sync."""
    from app.database import get_db_context
    from app.core.external_api import ExternalAPIClient
    from app.services import SyncService

    async with get_db_context() as db:
        async with ExternalAPIClient() as api:
            sync_service = SyncService(external_api=api)
            count = await sync_service.sync_gdrive(db, user_id, months=months)
            return {"status": "completed", "items": count}


@celery_app.task(bind=True, max_retries=3)
def sync_jira_task(
    self,
    user_id: str,
    months: int = 3,
):
    """Task for syncing Jira issues."""
    return run_async(_sync_jira_async(user_id, months))


async def _sync_jira_async(user_id: str, months: int):
    """Async implementation of Jira sync."""
    from app.database import get_db_context
    from app.core.external_api import ExternalAPIClient
    from app.services import SyncService

    async with get_db_context() as db:
        async with ExternalAPIClient() as api:
            sync_service = SyncService(external_api=api)
            count = await sync_service.sync_jira(db, user_id, months=months)
            return {"status": "completed", "items": count}


@celery_app.task(bind=True, max_retries=3)
def sync_calendar_task(
    self,
    user_id: str,
    days: int = 30,
):
    """Task for syncing calendar events."""
    return run_async(_sync_calendar_async(user_id, days))


async def _sync_calendar_async(user_id: str, days: int):
    """Async implementation of calendar sync."""
    from app.database import get_db_context
    from app.core.external_api import ExternalAPIClient
    from app.services import SyncService

    async with get_db_context() as db:
        async with ExternalAPIClient() as api:
            sync_service = SyncService(external_api=api)
            count = await sync_service.sync_calendar(db, user_id, days=days)
            return {"status": "completed", "items": count}


@celery_app.task
def periodic_sync():
    """
    Periodic task to sync all users incrementally.

    Run every hour via Celery Beat.
    """
    return run_async(_periodic_sync_async())


async def _periodic_sync_async():
    """Async implementation of periodic sync."""
    from sqlalchemy import select

    from app.database import get_db_context
    from app.models import IntegrationSync

    synced_users = 0

    async with get_db_context() as db:
        # Get all users with completed syncs
        stmt = select(IntegrationSync.user_id).where(
            IntegrationSync.status == "completed"
        ).distinct()

        result = await db.execute(stmt)
        user_ids = [row[0] for row in result.all()]

        # Trigger incremental sync for each user
        for user_id in user_ids:
            # Get sources for this user
            source_stmt = select(IntegrationSync.source_type).where(
                IntegrationSync.user_id == user_id,
                IntegrationSync.status == "completed",
            )
            source_result = await db.execute(source_stmt)
            sources = [row[0] for row in source_result.all()]

            if sources:
                # Queue individual sync tasks
                initial_sync_task.delay(str(user_id), sources)
                synced_users += 1

    return {"users_queued": synced_users}

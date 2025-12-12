"""
Sync API endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, IntegrationSync
from app.schemas.sync import (
    SyncRequest,
    SyncResponse,
    SyncStatus,
    SyncSourceStatus,
)
from app.services import SyncService
from app.core.external_api import get_external_api

router = APIRouter(prefix="/sync")


VALID_SOURCES = {"gmail", "gdrive", "jira", "calendar", "outlook", "onedrive"}


async def get_user(db: AsyncSession, external_user_id: str) -> User:
    """Get user by external ID."""
    stmt = select(User).where(User.external_user_id == external_user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            external_user_id=external_user_id,
            email=f"{external_user_id}@placeholder.com",
        )
        db.add(user)
        await db.flush()

    return user


@router.post("/initial", response_model=SyncResponse)
async def initial_sync(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate initial sync for a user.

    This triggers background jobs to sync data from all specified sources.
    """
    # Validate sources
    invalid_sources = set(request.sources) - VALID_SOURCES
    if invalid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sources: {invalid_sources}. Valid: {VALID_SOURCES}",
        )

    # Get user
    user = await get_user(db, request.user_id)

    # Initialize sync service
    external_api = await get_external_api()
    sync_service = SyncService(external_api=external_api)

    # Trigger initial sync
    sync_id = await sync_service.initial_sync(
        db=db,
        user_id=user.id,
        sources=request.sources,
        config=request.config.model_dump() if request.config else None,
    )

    # Add background task for actual sync
    # In production, this would be a Celery task
    background_tasks.add_task(
        run_sync_background,
        str(user.id),
        request.sources,
        request.config.model_dump() if request.config else None,
    )

    return SyncResponse(
        sync_id=sync_id,
        user_id=request.user_id,
        status="started",
        sources=request.sources,
        message=f"Initial sync started for {len(request.sources)} sources",
    )


async def run_sync_background(
    user_id: str,
    sources: list[str],
    config: dict = None,
):
    """Background task to run sync (simplified, use Celery in production)."""
    from app.database import get_db_context
    from app.core.external_api import ExternalAPIClient

    config = config or {}

    async with get_db_context() as db:
        async with ExternalAPIClient() as api:
            sync_service = SyncService(external_api=api)

            for source in sources:
                try:
                    if source == "gmail":
                        await sync_service.sync_gmail(
                            db, user_id, days=config.get("gmail_days", 30)
                        )
                    elif source == "gdrive":
                        await sync_service.sync_gdrive(
                            db, user_id, months=config.get("document_months", 6)
                        )
                    elif source == "jira":
                        await sync_service.sync_jira(
                            db, user_id, months=config.get("jira_months", 3)
                        )
                    elif source == "calendar":
                        await sync_service.sync_calendar(
                            db, user_id, days=config.get("calendar_days", 30)
                        )
                except Exception as e:
                    # Log error, continue with other sources
                    print(f"Error syncing {source}: {e}")


@router.get("/status/{user_id}", response_model=SyncStatus)
async def get_sync_status(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get sync status for all sources for a user."""
    # Get user
    user = await get_user(db, user_id)

    # Get sync records
    stmt = select(IntegrationSync).where(IntegrationSync.user_id == user.id)
    result = await db.execute(stmt)
    syncs = result.scalars().all()

    source_statuses = [
        SyncSourceStatus(
            source=s.source_type,
            status=s.status,
            items_synced=s.items_synced,
            last_sync_at=s.last_sync_at,
            error_message=s.error_message,
        )
        for s in syncs
    ]

    # Determine overall status
    statuses = [s.status for s in source_statuses]
    if all(s == "completed" for s in statuses):
        overall = "completed"
    elif any(s == "syncing" for s in statuses):
        overall = "syncing"
    elif any(s == "failed" for s in statuses):
        if any(s == "completed" for s in statuses):
            overall = "partial_failure"
        else:
            overall = "failed"
    else:
        overall = "pending"

    return SyncStatus(
        user_id=user_id,
        sources=source_statuses,
        overall_status=overall,
    )


@router.post("/incremental/{user_id}")
async def incremental_sync(
    user_id: str,
    sources: list[str] = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger incremental sync for a user.

    Only syncs items updated since last sync.
    """
    # Get user
    user = await get_user(db, user_id)

    # Get all sources if not specified
    if not sources:
        stmt = select(IntegrationSync.source_type).where(
            IntegrationSync.user_id == user.id,
            IntegrationSync.status == "completed",
        )
        result = await db.execute(stmt)
        sources = [r[0] for r in result.all()]

    if not sources:
        return {"message": "No sources configured for sync"}

    # Update status to syncing
    for source in sources:
        stmt = select(IntegrationSync).where(
            IntegrationSync.user_id == user.id,
            IntegrationSync.source_type == source,
        )
        result = await db.execute(stmt)
        sync_record = result.scalar_one_or_none()
        if sync_record:
            sync_record.status = "syncing"

    await db.commit()

    # Add background task
    if background_tasks:
        background_tasks.add_task(
            run_sync_background,
            str(user.id),
            sources,
        )

    return {
        "user_id": user_id,
        "sources": sources,
        "status": "started",
        "message": f"Incremental sync started for {len(sources)} sources",
    }


@router.delete("/{user_id}/{source}")
async def clear_sync_data(
    user_id: str,
    source: str,
    db: AsyncSession = Depends(get_db),
):
    """Clear synced data for a specific source."""
    if source not in VALID_SOURCES:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    # Get user
    user = await get_user(db, user_id)

    # Delete knowledge items for this source
    from app.models import KnowledgeItem
    from sqlalchemy import delete

    stmt = delete(KnowledgeItem).where(
        KnowledgeItem.user_id == user.id,
        KnowledgeItem.source_type == source,
    )
    result = await db.execute(stmt)
    deleted_count = result.rowcount

    # Reset sync status
    sync_stmt = select(IntegrationSync).where(
        IntegrationSync.user_id == user.id,
        IntegrationSync.source_type == source,
    )
    sync_result = await db.execute(sync_stmt)
    sync_record = sync_result.scalar_one_or_none()

    if sync_record:
        sync_record.status = "pending"
        sync_record.items_synced = 0
        sync_record.last_sync_at = None

    await db.commit()

    return {
        "user_id": user_id,
        "source": source,
        "deleted_items": deleted_count,
        "message": f"Cleared {deleted_count} items from {source}",
    }

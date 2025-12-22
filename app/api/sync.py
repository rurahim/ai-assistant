"""
Sync API endpoints.
"""

from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
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

DEFAULT_SOURCES = ["gmail", "gdrive", "jira", "calendar"]


class BulkSyncRequest(BaseModel):
    """Request for bulk sync of all users."""
    sources: list[str] = DEFAULT_SOURCES
    config: Optional[dict] = None


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


@router.get("/users")
async def list_sync_users(
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """
    List all users available for sync.

    This fetches users from the external database that have connected accounts.
    Use this to discover user IDs before initiating sync.
    """
    from external_db.database import get_local_db_context
    from sqlalchemy import text

    try:
        async with get_local_db_context() as ext_db:
            # Get users with their connected accounts
            result = await ext_db.execute(
                text("""
                    SELECT DISTINCT u.id, u.email, u.name,
                           array_agg(DISTINCT a.provider) as providers
                    FROM users u
                    LEFT JOIN accounts a ON a.user_id = u.id AND a.is_active = true
                    GROUP BY u.id, u.email, u.name
                    ORDER BY u.email
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": limit, "offset": offset}
            )
            rows = result.fetchall()

            # Get total count
            count_result = await ext_db.execute(
                text("SELECT COUNT(DISTINCT id) FROM users")
            )
            total = count_result.scalar()

            users = []
            for row in rows:
                providers = row.providers if row.providers and row.providers[0] else []
                users.append({
                    "user_id": str(row.id),
                    "email": row.email,
                    "name": row.name,
                    "connected_providers": [p for p in providers if p],
                })

            return {
                "users": users,
                "total": total,
                "limit": limit,
                "offset": offset,
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch users from external database: {str(e)}"
        )


@router.post("/all")
async def bulk_sync_all_users(
    request: BulkSyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate sync for ALL users in the external database.

    This is useful for initial setup or periodic full re-sync.
    Syncs are run in background for each user.
    """
    from external_db.database import get_local_db_context
    from sqlalchemy import text

    # Validate sources
    invalid_sources = set(request.sources) - VALID_SOURCES
    if invalid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sources: {invalid_sources}. Valid: {VALID_SOURCES}",
        )

    try:
        # Get all users from external database
        async with get_local_db_context() as ext_db:
            result = await ext_db.execute(
                text("SELECT DISTINCT id, email FROM users ORDER BY email")
            )
            external_users = result.fetchall()

        if not external_users:
            return {
                "status": "no_users",
                "message": "No users found in external database. Run external sync first.",
                "users_queued": 0,
            }

        # Queue sync for each user
        queued_users = []
        for ext_user in external_users:
            external_user_id = str(ext_user.id)

            # Get or create user in our database
            user = await get_user(db, external_user_id)
            await db.commit()

            # Queue background sync
            background_tasks.add_task(
                run_sync_background,
                str(user.id),
                request.sources,
                request.config,
            )

            queued_users.append({
                "user_id": external_user_id,
                "email": ext_user.email,
            })

        return {
            "status": "started",
            "message": f"Bulk sync started for {len(queued_users)} users",
            "sources": request.sources,
            "users_queued": len(queued_users),
            "users": queued_users,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate bulk sync: {str(e)}"
        )


@router.get("/status")
async def get_all_sync_status(
    db: AsyncSession = Depends(get_db),
):
    """
    Get sync status for ALL users.

    Returns aggregated sync status across all users.
    """
    # Get all users with their sync status
    stmt = select(User).order_by(User.email)
    result = await db.execute(stmt)
    users = result.scalars().all()

    user_statuses = []
    for user in users:
        # Get sync records for this user
        sync_stmt = select(IntegrationSync).where(IntegrationSync.user_id == user.id)
        sync_result = await db.execute(sync_stmt)
        syncs = sync_result.scalars().all()

        sources = {}
        for s in syncs:
            sources[s.source_type] = {
                "status": s.status,
                "items_synced": s.items_synced,
                "last_sync_at": s.last_sync_at.isoformat() if s.last_sync_at else None,
                "error": s.error_message,
            }

        # Determine overall status for this user
        statuses = [s.status for s in syncs]
        if not statuses:
            overall = "not_started"
        elif all(s == "completed" for s in statuses):
            overall = "completed"
        elif any(s == "syncing" for s in statuses):
            overall = "syncing"
        elif any(s == "failed" for s in statuses):
            overall = "partial_failure" if any(s == "completed" for s in statuses) else "failed"
        else:
            overall = "pending"

        user_statuses.append({
            "user_id": user.external_user_id,
            "email": user.email,
            "overall_status": overall,
            "sources": sources,
        })

    # Calculate summary
    total_users = len(user_statuses)
    completed = sum(1 for u in user_statuses if u["overall_status"] == "completed")
    syncing = sum(1 for u in user_statuses if u["overall_status"] == "syncing")
    failed = sum(1 for u in user_statuses if u["overall_status"] in ["failed", "partial_failure"])
    not_started = sum(1 for u in user_statuses if u["overall_status"] == "not_started")

    return {
        "summary": {
            "total_users": total_users,
            "completed": completed,
            "syncing": syncing,
            "failed": failed,
            "not_started": not_started,
        },
        "users": user_statuses,
    }

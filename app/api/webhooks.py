"""
Webhook API endpoints for real-time updates.
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User
from app.schemas.sync import WebhookPayload, WebhookResponse
from app.services import SyncService
from app.core.external_api import get_external_api
from app.core.redis_client import get_redis
from app.core.memory import WorkingMemory

router = APIRouter(prefix="/webhooks")


async def verify_webhook_signature(
    x_webhook_signature: str = Header(None),
) -> bool:
    """Verify webhook signature (implement proper HMAC verification in production)."""
    # In production, verify HMAC signature
    return True


@router.post("/item-created", response_model=WebhookResponse)
async def item_created(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
    valid: bool = Depends(verify_webhook_signature),
):
    """
    Handle item creation webhook.

    Called when a new email, document, task, or event is created.
    """
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Get user
    stmt = select(User).where(User.external_user_id == payload.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return WebhookResponse(
            processed=False,
            error="User not found",
        )

    try:
        # Process the new item
        external_api = await get_external_api()
        sync_service = SyncService(external_api=external_api)

        await sync_service.process_webhook_item(
            db=db,
            user_id=user.id,
            source=payload.source,
            source_id=payload.source_id,
            content_type=payload.content_type,
            data=payload.data,
        )

        # Invalidate relevant caches
        redis = await get_redis()
        working_memory = WorkingMemory(redis)
        await working_memory.invalidate_user_cache(str(user.id), payload.source)

        return WebhookResponse(
            processed=True,
            item_id=payload.source_id,
        )

    except Exception as e:
        return WebhookResponse(
            processed=False,
            error=str(e),
        )


@router.post("/item-updated", response_model=WebhookResponse)
async def item_updated(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
    valid: bool = Depends(verify_webhook_signature),
):
    """
    Handle item update webhook.

    Called when an existing item is modified.
    """
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Get user
    stmt = select(User).where(User.external_user_id == payload.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return WebhookResponse(
            processed=False,
            error="User not found",
        )

    try:
        # Process the updated item (same as create, will upsert)
        external_api = await get_external_api()
        sync_service = SyncService(external_api=external_api)

        await sync_service.process_webhook_item(
            db=db,
            user_id=user.id,
            source=payload.source,
            source_id=payload.source_id,
            content_type=payload.content_type,
            data=payload.data,
        )

        # Invalidate caches
        redis = await get_redis()
        working_memory = WorkingMemory(redis)
        await working_memory.invalidate_user_cache(str(user.id), payload.source)

        return WebhookResponse(
            processed=True,
            item_id=payload.source_id,
        )

    except Exception as e:
        return WebhookResponse(
            processed=False,
            error=str(e),
        )


@router.post("/item-deleted", response_model=WebhookResponse)
async def item_deleted(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db),
    valid: bool = Depends(verify_webhook_signature),
):
    """
    Handle item deletion webhook.

    Called when an item is deleted from the source system.
    """
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    # Get user
    stmt = select(User).where(User.external_user_id == payload.user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        return WebhookResponse(
            processed=False,
            error="User not found",
        )

    try:
        # Delete the item
        external_api = await get_external_api()
        sync_service = SyncService(external_api=external_api)

        deleted = await sync_service.delete_item(
            db=db,
            user_id=user.id,
            source=payload.source,
            source_id=payload.source_id,
        )

        if not deleted:
            return WebhookResponse(
                processed=False,
                error="Item not found",
            )

        # Invalidate caches
        redis = await get_redis()
        working_memory = WorkingMemory(redis)
        await working_memory.invalidate_user_cache(str(user.id), payload.source)

        return WebhookResponse(
            processed=True,
            item_id=payload.source_id,
        )

    except Exception as e:
        return WebhookResponse(
            processed=False,
            error=str(e),
        )


@router.post("/batch", response_model=dict)
async def batch_webhook(
    payloads: list[WebhookPayload],
    db: AsyncSession = Depends(get_db),
    valid: bool = Depends(verify_webhook_signature),
):
    """
    Handle batch webhook for multiple items.

    Useful for bulk updates.
    """
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    results = {
        "processed": 0,
        "failed": 0,
        "errors": [],
    }

    for payload in payloads:
        try:
            if payload.event_type == "item_created":
                response = await item_created(payload, db, valid)
            elif payload.event_type == "item_updated":
                response = await item_updated(payload, db, valid)
            elif payload.event_type == "item_deleted":
                response = await item_deleted(payload, db, valid)
            else:
                results["failed"] += 1
                results["errors"].append(f"Unknown event type: {payload.event_type}")
                continue

            if response.processed:
                results["processed"] += 1
            else:
                results["failed"] += 1
                if response.error:
                    results["errors"].append(response.error)

        except Exception as e:
            results["failed"] += 1
            results["errors"].append(str(e))

    return results

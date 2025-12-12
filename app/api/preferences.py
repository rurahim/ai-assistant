"""
User preferences API endpoints.
"""

from typing import Union

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, UserPreference
from app.services import PreferenceService
from app.core.redis_client import get_redis
from app.core.memory import WorkingMemory

router = APIRouter(prefix="/preferences")


class PreferenceUpdate(BaseModel):
    """Request to update a preference."""

    preference_type: str
    preference_key: str
    value: Union[dict, str, int, bool, list]


class WorkingHoursUpdate(BaseModel):
    """Request to update working hours."""

    start: str = Field(description="Start time in HH:MM format")
    end: str = Field(description="End time in HH:MM format")
    timezone: str = "UTC"


class EmailPreferencesUpdate(BaseModel):
    """Request to update email preferences."""

    tone: str = Field(default=None, description="professional, casual, formal")
    length: str = Field(default=None, description="brief, medium, detailed")
    signature: str = Field(default=None, description="Email signature text")
    include_greeting: bool = Field(default=None)


async def get_user(db: AsyncSession, external_user_id: str) -> User:
    """Get user by external ID."""
    stmt = select(User).where(User.external_user_id == external_user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.get("/{user_id}")
async def get_all_preferences(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all preferences for a user."""
    user = await get_user(db, user_id)

    redis = await get_redis()
    working_memory = WorkingMemory(redis)
    preference_service = PreferenceService(working_memory)

    preferences = await preference_service.get_preferences(db, user.id)

    return {
        "user_id": user_id,
        "preferences": preferences,
    }


@router.get("/{user_id}/{preference_type}")
async def get_preference_type(
    user_id: str,
    preference_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Get preferences of a specific type."""
    user = await get_user(db, user_id)

    stmt = select(UserPreference).where(
        UserPreference.user_id == user.id,
        UserPreference.preference_type == preference_type,
    )
    result = await db.execute(stmt)
    prefs = result.scalars().all()

    return {
        "user_id": user_id,
        "preference_type": preference_type,
        "preferences": {
            p.preference_key: {
                "value": p.preference_value,
                "confidence": p.confidence,
                "sample_count": p.sample_count,
            }
            for p in prefs
        },
    }


@router.put("/{user_id}")
async def update_preference(
    user_id: str,
    request: PreferenceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a specific preference."""
    user = await get_user(db, user_id)

    redis = await get_redis()
    working_memory = WorkingMemory(redis)
    preference_service = PreferenceService(working_memory)

    pref = await preference_service.update_preference(
        db=db,
        user_id=user.id,
        preference_type=request.preference_type,
        preference_key=request.preference_key,
        value=request.value,
        explicit=True,  # User-set preferences are explicit
    )

    return {
        "updated": True,
        "preference_type": request.preference_type,
        "preference_key": request.preference_key,
        "value": pref.preference_value,
        "confidence": pref.confidence,
    }


@router.put("/{user_id}/working-hours")
async def update_working_hours(
    user_id: str,
    request: WorkingHoursUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update user's working hours preference."""
    user = await get_user(db, user_id)

    redis = await get_redis()
    working_memory = WorkingMemory(redis)
    preference_service = PreferenceService(working_memory)

    await preference_service.set_working_hours(
        db=db,
        user_id=user.id,
        start=request.start,
        end=request.end,
        timezone=request.timezone,
    )

    return {
        "updated": True,
        "working_hours": {
            "start": request.start,
            "end": request.end,
            "timezone": request.timezone,
        },
    }


@router.get("/{user_id}/working-hours")
async def get_working_hours(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get user's working hours preference."""
    user = await get_user(db, user_id)

    redis = await get_redis()
    working_memory = WorkingMemory(redis)
    preference_service = PreferenceService(working_memory)

    hours = await preference_service.get_working_hours(db, user.id)

    return {
        "user_id": user_id,
        "working_hours": hours,
    }


@router.put("/{user_id}/email")
async def update_email_preferences(
    user_id: str,
    request: EmailPreferencesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update email preferences."""
    user = await get_user(db, user_id)

    redis = await get_redis()
    working_memory = WorkingMemory(redis)
    preference_service = PreferenceService(working_memory)

    updated = {}

    if request.tone:
        await preference_service.update_preference(
            db, user.id, "email", "tone", request.tone, explicit=True
        )
        updated["tone"] = request.tone

    if request.length:
        await preference_service.update_preference(
            db, user.id, "email", "length", request.length, explicit=True
        )
        updated["length"] = request.length

    if request.signature:
        await preference_service.update_preference(
            db, user.id, "email", "signature", request.signature, explicit=True
        )
        updated["signature"] = request.signature

    if request.include_greeting is not None:
        await preference_service.update_preference(
            db, user.id, "email", "greeting", request.include_greeting, explicit=True
        )
        updated["include_greeting"] = request.include_greeting

    return {
        "updated": True,
        "email_preferences": updated,
    }


@router.get("/{user_id}/email")
async def get_email_preferences(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get email preferences."""
    user = await get_user(db, user_id)

    redis = await get_redis()
    working_memory = WorkingMemory(redis)
    preference_service = PreferenceService(working_memory)

    prefs = await preference_service.get_email_preferences(db, user.id)

    return {
        "user_id": user_id,
        "email_preferences": prefs,
    }


@router.get("/{user_id}/frequent-contacts")
async def get_frequent_contacts(
    user_id: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    """Get frequently contacted people."""
    user = await get_user(db, user_id)

    redis = await get_redis()
    working_memory = WorkingMemory(redis)
    preference_service = PreferenceService(working_memory)

    contacts = await preference_service.get_frequent_recipients(
        db, user.id, limit=limit
    )

    return {
        "user_id": user_id,
        "frequent_contacts": contacts,
    }


@router.delete("/{user_id}/{preference_type}/{preference_key}")
async def delete_preference(
    user_id: str,
    preference_type: str,
    preference_key: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a specific preference."""
    user = await get_user(db, user_id)

    stmt = select(UserPreference).where(
        UserPreference.user_id == user.id,
        UserPreference.preference_type == preference_type,
        UserPreference.preference_key == preference_key,
    )
    result = await db.execute(stmt)
    pref = result.scalar_one_or_none()

    if not pref:
        raise HTTPException(status_code=404, detail="Preference not found")

    await db.delete(pref)
    await db.commit()

    # Invalidate cache
    redis = await get_redis()
    working_memory = WorkingMemory(redis)
    await working_memory.invalidate_preferences_cache(str(user.id))

    return {
        "deleted": True,
        "preference_type": preference_type,
        "preference_key": preference_key,
    }

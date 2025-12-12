"""
User preference learning and management service.
"""

from datetime import datetime
from typing import Union,  Any, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.models import UserPreference, UserFeedback, ChatMessage
from app.core.memory import WorkingMemory


class PreferenceService:
    """
    Service for learning and managing user preferences.

    Tracks:
    - Email tone preferences
    - Response length preferences
    - Working hours patterns
    - Frequent recipients
    - Common actions
    """

    # Confidence thresholds
    MIN_CONFIDENCE = 0.3
    HIGH_CONFIDENCE = 0.8

    def __init__(self, working_memory: Optional[WorkingMemory] = None):
        self.working_memory = working_memory

    async def get_preferences(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
    ) -> dict:
        """Get all preferences for a user."""
        # Try cache first
        if self.working_memory:
            cached = await self.working_memory.get_cached_preferences(str(user_id))
            if cached:
                return cached

        # Query from database
        stmt = select(UserPreference).where(
            UserPreference.user_id == str(user_id)
        )
        result = await db.execute(stmt)
        prefs = result.scalars().all()

        # Format preferences
        preferences = {}
        for pref in prefs:
            key = f"{pref.preference_type}.{pref.preference_key}"
            preferences[key] = {
                "value": pref.preference_value,
                "confidence": pref.confidence,
                "sample_count": pref.sample_count,
            }

        # Cache preferences
        if self.working_memory:
            await self.working_memory.set_cached_preferences(str(user_id), preferences)

        return preferences

    async def get_preference(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        preference_type: str,
        preference_key: str,
    ) -> Optional[dict]:
        """Get a specific preference."""
        stmt = select(UserPreference).where(
            UserPreference.user_id == str(user_id),
            UserPreference.preference_type == preference_type,
            UserPreference.preference_key == preference_key,
        )
        result = await db.execute(stmt)
        pref = result.scalar_one_or_none()

        if pref:
            return {
                "value": pref.preference_value,
                "confidence": pref.confidence,
                "sample_count": pref.sample_count,
            }
        return None

    async def update_preference(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        preference_type: str,
        preference_key: str,
        value: Any,
        explicit: bool = False,
    ) -> UserPreference:
        """
        Update a user preference.

        Args:
            db: Database session
            user_id: User ID
            preference_type: Type of preference (email_tone, response_length, etc.)
            preference_key: Specific key within the type
            value: The preference value
            explicit: Whether this is an explicit user setting (high confidence)
        """
        # Get existing preference
        stmt = select(UserPreference).where(
            UserPreference.user_id == str(user_id),
            UserPreference.preference_type == preference_type,
            UserPreference.preference_key == preference_key,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            if explicit:
                # Explicit setting: high confidence
                existing.preference_value = value
                existing.confidence = self.HIGH_CONFIDENCE
                existing.sample_count += 1
            else:
                # Learned preference: gradual increase
                existing.sample_count += 1
                # Increase confidence with more samples (max 0.9)
                existing.confidence = min(
                    0.9,
                    existing.confidence + (1 - existing.confidence) * 0.1
                )
                # Update value if same, decrease confidence if different
                if existing.preference_value == value:
                    pass  # Value unchanged
                else:
                    # Conflicting value - decrease confidence
                    existing.confidence *= 0.8
                    if existing.confidence < self.MIN_CONFIDENCE:
                        existing.preference_value = value
                        existing.confidence = self.MIN_CONFIDENCE
            pref = existing
        else:
            # Create new preference
            confidence = self.HIGH_CONFIDENCE if explicit else 0.5
            pref = UserPreference(
                user_id=str(user_id),
                preference_type=preference_type,
                preference_key=preference_key,
                preference_value=value,
                confidence=confidence,
                sample_count=1,
            )
            db.add(pref)

        await db.commit()

        # Invalidate cache
        if self.working_memory:
            await self.working_memory.invalidate_preferences_cache(str(user_id))

        return pref

    async def learn_from_feedback(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        message_id: Union[str, UUID],
        feedback_type: str,
        feedback_value: dict,
    ) -> None:
        """
        Learn preferences from user feedback.

        Args:
            db: Database session
            user_id: User ID
            message_id: The message receiving feedback
            feedback_type: Type of feedback (rating, edit, accept, reject)
            feedback_value: Feedback details
        """
        # Store feedback
        feedback = UserFeedback(
            user_id=str(user_id),
            message_id=str(message_id),
            feedback_type=feedback_type,
            feedback_value=feedback_value,
        )
        db.add(feedback)

        # Get the message context
        message_result = await db.execute(
            select(ChatMessage).where(ChatMessage.id == str(message_id))
        )
        message = message_result.scalar_one_or_none()

        if not message:
            await db.commit()
            return

        # Learn based on feedback type
        if feedback_type == "rating":
            rating = feedback_value.get("rating", 3)
            if rating >= 4:
                # Positive feedback - reinforce current approach
                # Could analyze message style and store preferences
                pass
            elif rating <= 2:
                # Negative feedback - adjust preferences
                pass

        elif feedback_type == "edit":
            # User edited the response - learn from changes
            original = feedback_value.get("original", "")
            edited = feedback_value.get("edited", "")

            # Analyze length preference
            if len(edited) < len(original) * 0.7:
                await self.update_preference(
                    db, user_id, "response", "length", "shorter"
                )
            elif len(edited) > len(original) * 1.3:
                await self.update_preference(
                    db, user_id, "response", "length", "longer"
                )

        elif feedback_type == "accept":
            # User accepted suggestion - reinforce
            action_type = feedback_value.get("action_type")
            if action_type:
                await self.update_preference(
                    db, user_id, "actions", f"accept_{action_type}", True
                )

        elif feedback_type == "reject":
            # User rejected suggestion
            action_type = feedback_value.get("action_type")
            if action_type:
                await self.update_preference(
                    db, user_id, "actions", f"reject_{action_type}", True
                )

        await db.commit()

    async def get_email_preferences(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
    ) -> dict:
        """Get email-related preferences."""
        prefs = await self.get_preferences(db, user_id)

        return {
            "tone": prefs.get("email.tone", {}).get("value", "professional"),
            "length": prefs.get("email.length", {}).get("value", "medium"),
            "signature": prefs.get("email.signature", {}).get("value", "Best regards"),
            "include_greeting": prefs.get("email.greeting", {}).get("value", True),
        }

    async def get_frequent_recipients(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        limit: int = 10,
    ) -> list[dict]:
        """Get frequently contacted recipients."""
        pref = await self.get_preference(db, user_id, "contacts", "frequent")
        if pref:
            return pref.get("value", [])[:limit]
        return []

    async def update_frequent_recipient(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        email: str,
    ) -> None:
        """Update frequent recipient list."""
        pref = await self.get_preference(db, user_id, "contacts", "frequent")
        recipients = pref.get("value", []) if pref else []

        # Find or add recipient
        found = False
        for r in recipients:
            if r.get("email") == email:
                r["count"] = r.get("count", 0) + 1
                found = True
                break

        if not found:
            recipients.append({"email": email, "count": 1})

        # Sort by count and limit
        recipients.sort(key=lambda x: x.get("count", 0), reverse=True)
        recipients = recipients[:50]  # Keep top 50

        await self.update_preference(
            db, user_id, "contacts", "frequent", recipients
        )

    async def get_working_hours(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
    ) -> Optional[dict]:
        """Get user's working hours preference."""
        pref = await self.get_preference(db, user_id, "schedule", "working_hours")
        if pref and pref.get("confidence", 0) > self.MIN_CONFIDENCE:
            return pref.get("value")
        return None

    async def set_working_hours(
        self,
        db: AsyncSession,
        user_id: Union[str, UUID],
        start: str,
        end: str,
        timezone: str = "UTC",
    ) -> None:
        """Set user's working hours."""
        await self.update_preference(
            db,
            user_id,
            "schedule",
            "working_hours",
            {"start": start, "end": end, "timezone": timezone},
            explicit=True,
        )

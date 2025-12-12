"""
Working Memory management using Redis.

Handles current session context, active entities, and cached preferences.
"""

import json
from datetime import datetime
from typing import Union,  Any, Optional
from uuid import UUID

from app.core.redis_client import RedisClient
from app.config import get_settings

settings = get_settings()


class WorkingMemory:
    """
    Working memory for current session context.

    Key structure:
    - working:{user_id}:{session_id}:context     - Current conversation context
    - working:{user_id}:{session_id}:entities    - Active entities in session
    - working:{user_id}:preferences              - Cached user preferences
    - working:{user_id}:recent_items             - Recently accessed items
    """

    # TTL values
    SESSION_TTL = 1800  # 30 minutes
    PREFERENCES_TTL = 3600  # 1 hour
    RECENT_ITEMS_TTL = 900  # 15 minutes

    def __init__(self, redis: RedisClient):
        self.redis = redis

    # ============== Session Context ==============

    async def get_session_context(
        self,
        user_id: Union[str, UUID],
        session_id: Union[str, UUID],
    ) -> Optional[dict]:
        """Get current session context."""
        key = f"working:{user_id}:{session_id}:context"
        return await self.redis.get_json(key)

    async def set_session_context(
        self,
        user_id: Union[str, UUID],
        session_id: Union[str, UUID],
        context: dict,
    ) -> None:
        """Set current session context."""
        key = f"working:{user_id}:{session_id}:context"
        await self.redis.set_json(key, context, self.SESSION_TTL)

    async def update_session_context(
        self,
        user_id: Union[str, UUID],
        session_id: Union[str, UUID],
        updates: dict,
    ) -> dict:
        """Update session context with new data."""
        context = await self.get_session_context(user_id, session_id) or {}
        context.update(updates)
        context["updated_at"] = datetime.utcnow().isoformat()
        await self.set_session_context(user_id, session_id, context)
        return context

    async def clear_session_context(
        self,
        user_id: Union[str, UUID],
        session_id: Union[str, UUID],
    ) -> None:
        """Clear session context."""
        await self.redis.delete(f"working:{user_id}:{session_id}:context")
        await self.redis.delete(f"working:{user_id}:{session_id}:entities")

    # ============== Active Entities ==============

    async def get_active_entities(
        self,
        user_id: Union[str, UUID],
        session_id: Union[str, UUID],
    ) -> list[dict]:
        """Get active entities in current session."""
        key = f"working:{user_id}:{session_id}:entities"
        data = await self.redis.get_json(key)
        return data.get("entities", []) if data else []

    async def add_active_entity(
        self,
        user_id: Union[str, UUID],
        session_id: Union[str, UUID],
        entity: dict,
    ) -> None:
        """Add an entity to the active session."""
        key = f"working:{user_id}:{session_id}:entities"
        data = await self.redis.get_json(key) or {"entities": []}

        # Check if entity already exists (by id or normalized_name)
        existing = next(
            (e for e in data["entities"]
             if e.get("id") == entity.get("id")
             or e.get("normalized_name") == entity.get("normalized_name")),
            None,
        )

        if existing:
            # Update existing entity
            existing.update(entity)
        else:
            # Add new entity
            data["entities"].append(entity)

        await self.redis.set_json(key, data, self.SESSION_TTL)

    async def remove_active_entity(
        self,
        user_id: Union[str, UUID],
        session_id: Union[str, UUID],
        entity_id: str,
    ) -> None:
        """Remove an entity from the active session."""
        key = f"working:{user_id}:{session_id}:entities"
        data = await self.redis.get_json(key)
        if data:
            data["entities"] = [
                e for e in data["entities"]
                if str(e.get("id")) != str(entity_id)
            ]
            await self.redis.set_json(key, data, self.SESSION_TTL)

    # ============== User Preferences Cache ==============

    async def get_cached_preferences(
        self,
        user_id: Union[str, UUID],
    ) -> Optional[dict]:
        """Get cached user preferences."""
        key = f"working:{user_id}:preferences"
        return await self.redis.get_json(key)

    async def set_cached_preferences(
        self,
        user_id: Union[str, UUID],
        preferences: dict,
    ) -> None:
        """Cache user preferences."""
        key = f"working:{user_id}:preferences"
        await self.redis.set_json(key, preferences, self.PREFERENCES_TTL)

    async def invalidate_preferences_cache(
        self,
        user_id: Union[str, UUID],
    ) -> None:
        """Invalidate cached preferences."""
        key = f"working:{user_id}:preferences"
        await self.redis.delete(key)

    # ============== Recently Accessed Items ==============

    async def get_recent_items(
        self,
        user_id: Union[str, UUID],
        limit: int = 10,
    ) -> list[dict]:
        """Get recently accessed items."""
        key = f"working:{user_id}:recent_items"
        items_json = await self.redis.lrange(key, 0, limit - 1)
        return [json.loads(item) for item in items_json]

    async def add_recent_item(
        self,
        user_id: Union[str, UUID],
        item: dict,
        max_items: int = 20,
    ) -> None:
        """Add an item to recently accessed list."""
        key = f"working:{user_id}:recent_items"

        # Add to front of list
        await self.redis.lpush(key, json.dumps(item))

        # Trim to max items
        await self.redis.ltrim(key, 0, max_items - 1)

        # Set TTL
        await self.redis.expire(key, self.RECENT_ITEMS_TTL)

    async def clear_recent_items(
        self,
        user_id: Union[str, UUID],
    ) -> None:
        """Clear recently accessed items."""
        key = f"working:{user_id}:recent_items"
        await self.redis.delete(key)

    # ============== Cache Invalidation ==============

    async def invalidate_user_cache(
        self,
        user_id: Union[str, UUID],
        source: Optional[str] = None,
    ) -> int:
        """
        Invalidate cached data for a user.

        Args:
            user_id: User ID
            source: Optional source type to invalidate specific caches

        Returns:
            Number of keys deleted
        """
        patterns = [
            f"working:{user_id}:*",
        ]

        if source:
            patterns.append(f"context:{user_id}:{source}:*")

        total_deleted = 0
        for pattern in patterns:
            deleted = await self.redis.delete_pattern(pattern)
            total_deleted += deleted

        return total_deleted

    # ============== Pending Actions ==============

    async def get_pending_actions(
        self,
        user_id: Union[str, UUID],
        session_id: Union[str, UUID],
    ) -> list[dict]:
        """Get pending actions for a session."""
        context = await self.get_session_context(user_id, session_id)
        return context.get("pending_actions", []) if context else []

    async def add_pending_action(
        self,
        user_id: Union[str, UUID],
        session_id: Union[str, UUID],
        action: dict,
    ) -> None:
        """Add a pending action to the session."""
        context = await self.get_session_context(user_id, session_id) or {}
        pending = context.get("pending_actions", [])
        pending.append(action)
        context["pending_actions"] = pending
        await self.set_session_context(user_id, session_id, context)

    async def remove_pending_action(
        self,
        user_id: Union[str, UUID],
        session_id: Union[str, UUID],
        action_id: str,
    ) -> Optional[dict]:
        """Remove and return a pending action."""
        context = await self.get_session_context(user_id, session_id)
        if not context:
            return None

        pending = context.get("pending_actions", [])
        action = next(
            (a for a in pending if a.get("id") == action_id),
            None,
        )

        if action:
            pending.remove(action)
            context["pending_actions"] = pending
            await self.set_session_context(user_id, session_id, context)

        return action

    async def clear_pending_actions(
        self,
        user_id: Union[str, UUID],
        session_id: Union[str, UUID],
    ) -> None:
        """Clear all pending actions for a session."""
        context = await self.get_session_context(user_id, session_id)
        if context:
            context["pending_actions"] = []
            await self.set_session_context(user_id, session_id, context)

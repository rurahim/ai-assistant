"""
Redis client for caching and working memory.
"""

import json
from typing import Any, Optional
from functools import lru_cache

import redis.asyncio as redis

from app.config import get_settings

settings = get_settings()


class RedisClient:
    """Async Redis client wrapper."""

    def __init__(self, url: str):
        self.url = url
        self._client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Connect to Redis."""
        if self._client is None:
            self._client = redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
            )

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None

    @property
    def client(self) -> redis.Redis:
        """Get Redis client instance."""
        if self._client is None:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return self._client

    async def get(self, key: str) -> Optional[str]:
        """Get a value from Redis."""
        return await self.client.get(key)

    async def set(
        self,
        key: str,
        value: str,
        ttl: Optional[int] = None,
    ) -> None:
        """Set a value in Redis with optional TTL."""
        if ttl:
            await self.client.setex(key, ttl, value)
        else:
            await self.client.set(key, value)

    async def get_json(self, key: str) -> Optional[dict]:
        """Get a JSON value from Redis."""
        value = await self.get(key)
        if value:
            return json.loads(value)
        return None

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
    ) -> None:
        """Set a JSON value in Redis."""
        await self.set(key, json.dumps(value), ttl)

    async def delete(self, key: str) -> None:
        """Delete a key from Redis."""
        await self.client.delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern."""
        keys = []
        async for key in self.client.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            return await self.client.delete(*keys)
        return 0

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        return await self.client.exists(key) > 0

    async def expire(self, key: str, ttl: int) -> None:
        """Set TTL on an existing key."""
        await self.client.expire(key, ttl)

    async def lpush(self, key: str, *values: str) -> int:
        """Push values to the left of a list."""
        return await self.client.lpush(key, *values)

    async def rpush(self, key: str, *values: str) -> int:
        """Push values to the right of a list."""
        return await self.client.rpush(key, *values)

    async def lrange(self, key: str, start: int, end: int) -> list[str]:
        """Get a range of values from a list."""
        return await self.client.lrange(key, start, end)

    async def ltrim(self, key: str, start: int, end: int) -> None:
        """Trim a list to the specified range."""
        await self.client.ltrim(key, start, end)

    async def hset(self, key: str, field: str, value: str) -> None:
        """Set a hash field."""
        await self.client.hset(key, field, value)

    async def hget(self, key: str, field: str) -> Optional[str]:
        """Get a hash field."""
        return await self.client.hget(key, field)

    async def hgetall(self, key: str) -> dict[str, str]:
        """Get all hash fields."""
        return await self.client.hgetall(key)

    async def hdel(self, key: str, *fields: str) -> int:
        """Delete hash fields."""
        return await self.client.hdel(key, *fields)


# Global Redis client instance
_redis_client: Optional[RedisClient] = None


async def get_redis() -> RedisClient:
    """Get the global Redis client instance."""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient(settings.redis_url)
        await _redis_client.connect()
    return _redis_client


async def close_redis() -> None:
    """Close the global Redis client."""
    global _redis_client
    if _redis_client:
        await _redis_client.disconnect()
        _redis_client = None

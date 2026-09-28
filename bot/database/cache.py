import asyncio
import json
import logging
import time
from typing import Optional, Any
import redis.asyncio as aioredis
from bot.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._in_memory: dict[str, tuple[str, float]] = {}
        self._connected: bool = True

    def _get_client(self) -> Optional[aioredis.Redis]:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            return None

        if self._redis is None or self._loop != current_loop:
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2.0
            )
            self._loop = current_loop
        return self._redis

    async def init(self):
        client = self._get_client()
        if client:
            try:
                await client.ping()
                self._connected = True
                logger.info("Успішно підключено до Redis кешу.")
                return
            except Exception as e:
                logger.warning(f"Redis недоступний ({e}). Використовується резервний in-memory кеш.")
        self._connected = False

    async def get(self, key: str) -> Optional[Any]:
        if self._connected:
            client = self._get_client()
            if client:
                try:
                    val = await client.get(key)
                    if val:
                        return json.loads(val)
                    return None
                except Exception as e:
                    logger.warning(f"Помилка читання з Redis: {e}")

        # In-memory fallback
        item = self._in_memory.get(key)
        if item:
            val_str, expire_at = item
            if expire_at == 0 or expire_at > time.time():
                return json.loads(val_str)
            else:
                del self._in_memory[key]
        return None

    async def set(self, key: str, value: Any, ttl: int = 10):
        val_str = json.dumps(value, default=str)
        if self._connected:
            client = self._get_client()
            if client:
                try:
                    await client.set(key, val_str, ex=ttl)
                    return
                except Exception as e:
                    logger.warning(f"Помилка запису в Redis: {e}")

        # In-memory fallback
        expire_at = (time.time() + ttl) if ttl > 0 else 0
        self._in_memory[key] = (val_str, expire_at)

    async def delete(self, key: str):
        if self._connected:
            client = self._get_client()
            if client:
                try:
                    await client.delete(key)
                except Exception as e:
                    logger.warning(f"Помилка видалення з Redis: {e}")
        self._in_memory.pop(key, None)

    async def clear_pattern(self, pattern: str):
        if self._connected:
            client = self._get_client()
            if client:
                try:
                    keys = await client.keys(pattern)
                    if keys:
                        await client.delete(*keys)
                except Exception:
                    pass
        self._in_memory.clear()

    async def close(self):
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None


cache = CacheService()

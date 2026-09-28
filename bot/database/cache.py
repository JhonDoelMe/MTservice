import json
import logging
from typing import Optional, Any
import redis.asyncio as aioredis
from bot.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self):
        self._redis: Optional[aioredis.Redis] = None
        self._in_memory: dict[str, tuple[str, float]] = {}
        self._connected: bool = False

    async def init(self):
        try:
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2.0
            )
            # Ping test
            await self._redis.ping()
            self._connected = True
            logger.info("Успішно підключено до Redis кешу.")
        except Exception as e:
            logger.warning(f"Redis недоступний ({e}). Використовується резервний in-memory кеш.")
            self._connected = False

    async def get(self, key: str) -> Optional[Any]:
        if self._connected and self._redis:
            try:
                val = await self._redis.get(key)
                if val:
                    return json.loads(val)
                return None
            except Exception as e:
                logger.warning(f"Помилка читання з Redis: {e}")

        # In-memory fallback
        import time
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
        if self._connected and self._redis:
            try:
                await self._redis.set(key, val_str, ex=ttl)
                return
            except Exception as e:
                logger.warning(f"Помилка запису в Redis: {e}")

        # In-memory fallback
        import time
        expire_at = (time.time() + ttl) if ttl > 0 else 0
        self._in_memory[key] = (val_str, expire_at)

    async def delete(self, key: str):
        if self._connected and self._redis:
            try:
                await self._redis.delete(key)
            except Exception:
                pass
        self._in_memory.pop(key, None)

    async def clear_pattern(self, pattern: str):
        if self._connected and self._redis:
            try:
                keys = await self._redis.keys(pattern)
                if keys:
                    await self._redis.delete(*keys)
            except Exception:
                pass
        self._in_memory.clear()

    async def close(self):
        if self._redis:
            await self._redis.close()


cache = CacheService()

import redis.asyncio as redis
import redis as sync_redis
from src.core.config import settings

class RedisClient:
    _instance = None
    _sync_instance = None

    @classmethod
    def get_instance(cls) -> redis.Redis:
        if cls._instance is None:
            # Create a connection pool
            pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True, # Automatically decode bytes to strings
                max_connections=20
            )
            cls._instance = redis.Redis(connection_pool=pool)
        return cls._instance

    @classmethod
    def get_sync_instance(cls) -> sync_redis.Redis:
        if cls._sync_instance is None:
             pool = sync_redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                max_connections=20
             )
             cls._sync_instance = sync_redis.Redis(connection_pool=pool)
        return cls._sync_instance

    @classmethod
    async def close(cls):
        if cls._instance:
            await cls._instance.close()
            cls._instance = None
        if cls._sync_instance:
            cls._sync_instance.close()
            cls._sync_instance = None

def get_redis_client() -> redis.Redis:
    return RedisClient.get_instance()

def get_sync_redis_client() -> sync_redis.Redis:
    return RedisClient.get_sync_instance()

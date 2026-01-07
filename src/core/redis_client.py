import redis.asyncio as redis
from src.core.config import settings

class RedisClient:
    _instance = None

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
    async def close(cls):
        if cls._instance:
            await cls._instance.close()
            cls._instance = None

def get_redis_client() -> redis.Redis:
    return RedisClient.get_instance()

from redis.asyncio.client import Redis
from redis.typing import (
    AbsExpiryT,
    ExpiryT,
    KeyT
)
import json
from typing import Union, Optional, Any

from config import config

class CustomRedisClient(Redis):
    def __init__(self, key_prefix: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.key_prefix = key_prefix
    
    def _add_prefix(self, key: KeyT):
        return f"{self.key_prefix}:{key}" if self.key_prefix else key
    
    async def get(self, key: str, *args, **kwargs) -> Optional[Any]:
        prefixed_key = self._add_prefix(key)
        return await super().get(prefixed_key, *args, **kwargs)

    async def set(self, key: str, *args, **kwargs) -> Optional[Any]:
        prefixed_key = self._add_prefix(key)
        return await super().set(prefixed_key, *args, **kwargs)

    async def hset(self, key: str, *args, **kwargs) -> Optional[Any]:
        prefixed_key = self._add_prefix(key)
        return await super().hset(prefixed_key, *args, **kwargs)

    async def hgetall(self, key: str, *args, **kwargs) -> dict:
        prefixed_key = self._add_prefix(key)
        return await super().hgetall(prefixed_key, *args, **kwargs)

    async def delete(self, *keys: str) -> int:
        prefixed_keys = [self._add_prefix(key) for key in keys]
        return await super().delete(*prefixed_keys)
    

    async def get_abs(self, key: str, *args, **kwargs) -> Optional[Any]:
        return await super().get(key, *args, **kwargs)

    async def set_abs(self, key: str, *args, **kwargs) -> Optional[Any]:
        return await super().set(key, *args, **kwargs)

    async def hset_abs(self, key: str, *args, **kwargs) -> Optional[Any]:
        return await super().hset(key, *args, **kwargs)

    async def hgetall_abs(self, key: str, *args, **kwargs) -> dict:
        return await super().hgetall(key, *args, **kwargs)

    async def delete_abs(self, *keys: str) -> int:
        return await super().delete(keys)


    async def set_dict(self, key: KeyT, data: dict, ex: Union[ExpiryT, None] = None, px: Union[ExpiryT, None] = None, nx: bool = False, xx: bool = False, keepttl: bool = False, get: bool = False, exat: Union[AbsExpiryT, None] = None, pxat: Union[AbsExpiryT, None] = None):
        await self.set(
            key=key,
            value=json.dumps(data),
            ex=ex, px=px, nx=nx, xx=xx, keepttl=keepttl, get=get, exat=exat, pxat=pxat
        )

    async def get_dict(self, key: KeyT):
        json_data = await self.get(key)
        return dict(json.loads(json_data)) if json_data else None


def create_connection() -> CustomRedisClient:
    return CustomRedisClient(
        host=config["Redis"]["host"],
        port=int(config["Redis"]["port"]),
        password=config["Redis"]["password"],
        username=config["Redis"]["login"],
        key_prefix="probook", # custom prefix
        decode_responses=True,
        retry_on_timeout=True,
        socket_keepalive=True
    )


redis_db = create_connection()
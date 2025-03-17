import logging
from ..routers.uploader import STATIC_IMAGES_DIR
from ..database import redis_db

import os
from redis.exceptions import ConnectionError
import asyncio

pubsub = redis_db.pubsub()

async def tmp_image_remover_task(message: dict):
    key = str(message['data'])
    allows_startswith = ["probook:user_image:"]
    fl = True

    for allow_startswith in allows_startswith:
        fl = fl and key.startswith(allow_startswith)

    if fl:
        return await tmp_image_remover(key)


async def tmp_image_remover(key: str):
    key = key + '_value'
    
    path = await redis_db.get(key)
    await redis_db.delete(key)

    if path is None:
        return

    file_path = os.path.join(STATIC_IMAGES_DIR, path)

    if os.path.exists(file_path):
        os.remove(file_path)


async def subscribe_expired_keys():
    await remove_trash("probook:user_image:", "_value")
    
    while True:
        await pubsub.subscribe(**{'__keyevent@0__:expired': tmp_image_remover_task})
        logging.info("Subscribe to key expiration notifications...")
        
        try:
            async for message in pubsub.listen():
                pass
        except ConnectionError as e:
            logging.info(f"Connection error: {e}. Reconnecting in 5 seconds...")
            await asyncio.sleep(5)
        
        finally:
            await pubsub.close()
            await redis_db.close()

async def remove_trash(prefix: str, sufix: str):
    cursor = 0
    matching_keys = []
    while True:
        cursor, keys = await redis_db.scan(cursor=cursor, match=f"{prefix}*{sufix}", count=100)
        
        matching_keys.extend(keys)

        if cursor == 0:
            break
        
    for key in matching_keys:
        key = key[:-len(sufix):]
        
        if await redis_db.get(key) is None:
            await tmp_image_remover(key)
from fastapi import FastAPI, Depends, Request, HTTPException, APIRouter
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import json
import logging
import asyncio
import os
import uvicorn

from routers.auth import router as auth_router
from routers.group import router as group_router
from routers.event import router as event_router
from routers.coworking import router as coworking_router
from routers.permissions import router as permissions_router
from routers.item import router as items_router
from routers.uploader import router as uploader_router, STATIC_IMAGES_DIR
from routers.schedule import router as schedule_router
from routers.room import router as room_router
from routers.action_history import router as action_history_router
from routers.workers import router as workers_router
from auth import *
from schemas import *
from sqlalchemy import (
    select,
    insert
)
from database import async_session_maker
from mock_data import schedule_template
from models_ import schedule, room as room_db
from services import subscribe_expired_keys, repeat_event_updater
from services.tmp_image_remover import pubsub
from shared.utils.schedule_utils import schedule_template_fix


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code
    app.state.expired_keys_task = asyncio.create_task(subscribe_expired_keys())

    asyncio.create_task(repeat_event_updater())

    async with async_session_maker() as session:
        await schedule_template_fix(session)
        await session.commit()
    
    yield
    
    # Shutdown code
    task = app.state.expired_keys_task
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        logging.info("Background task cancelled")

    if pubsub:
        await pubsub.unsubscribe('__keyevent@0__:expired')
        await pubsub.close()
    
    await redis_db.close()


app = FastAPI(
    title="ProBook API",
    lifespan=lifespan,
    docs_url=None,
    openapi_url=None,
    redoc_url=None,
)

os.makedirs(STATIC_IMAGES_DIR, exist_ok=True)
app.mount("/api/static", StaticFiles(directory=STATIC_IMAGES_DIR), name="static")
api_router = APIRouter(
    prefix="/api"
)

routers = [
    auth_router,
    group_router,
    event_router,
    coworking_router,
    permissions_router,
    items_router,
    uploader_router,
    schedule_router,
    room_router,
    action_history_router,
    workers_router
]

for router in routers:
    api_router.include_router(router)


async def add_new_token_to_response(request: Request, call_next):
    response = await call_next(request)

    user = getattr(request.state, "__auth_user_data", None)

    if user:
        response_body = [chunk async for chunk in response.body_iterator]
        content_dict = json.loads(b"".join(response_body).decode("utf-8"))

        if "new_token" in content_dict and "result" in content_dict:
            response = JSONResponse(
                content=content_dict, status_code=response.status_code)
        else:
            new_token = getattr(user, "new_token", None)
            content = BaseTokenResponse(
                new_token=new_token,
                result=content_dict
            ).model_dump()

            response = JSONResponse(
                content=content, status_code=response.status_code)

    return response


@app.middleware("http")
async def add_new_token_middleware(request: Request, call_next):
    return await add_new_token_to_response(request, call_next)


@api_router.get('/')
async def root():
    return {'data': 'Hello world'}
    
app.include_router(api_router)

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://git-ts2.ru:8000",
    "http://localhost:8000"
]

app.add_middleware(
     CORSMiddleware,
     allow_origins=origins,
     allow_credentials=True, 
     allow_methods=["*"],
     allow_headers=["Authorization", "Content-Type"],  
)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    

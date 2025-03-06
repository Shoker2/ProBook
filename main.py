from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
import json
import os
from fastapi.staticfiles import StaticFiles
from .routers.auth import router as auth_router
from .routers.group import router as group_router
from .routers.event import router as event_router
from .routers.coworking import router as coworking_router
from .routers.permissions import router as permissions_router
from .routers.item import router as items_router
from .routers.uploader import router as uploader_router, STATIC_IMAGES_DIR
from .routers.schedule import router as schedule_router
from .routers.room import router as room_router
from .routers.action_history import router as action_history_router
from .auth import *
from .schemas import *
from sqlalchemy import (
    select,
    insert
)
from .database import async_session_maker
from .mock_data import schedule_template
from .models_ import schedule


app = FastAPI(
    title="TP2 API",
)

if not os.path.exists(STATIC_IMAGES_DIR):
    os.makedirs(STATIC_IMAGES_DIR)
app.mount("/images/", StaticFiles(directory=STATIC_IMAGES_DIR), name="img")

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
    action_history_router
]

for router in routers:
    app.include_router(router)

# @app.exception_handler(HTTPException)
# async def http_exception_handler(request: Request, exc: HTTPException):
#     response_data = {"detail": exc.detail}

#     return JSONResponse(
#         status_code=exc.status_code,
#         content=response_data,
#     )

# Валидация наличия new_token


async def add_new_token_to_response(request: Request, call_next):
    response = await call_next(request)

    user = getattr(request.state, "__auth_user_data", None)

    if user:
        response_body = [chunk async for chunk in response.body_iterator]
        content_dict = json.loads(b"".join(response_body).decode("utf-8"))

        if "new_token" in content_dict and "result" in content_dict and len(content_dict.keys()) == 2:
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


@app.get('/', response_model=BaseTokenResponse[UserRead])
async def root(user: UserToken = Depends(get_current_user)):
    return BaseTokenResponse(
        new_token=user.new_token,
        result=user
    )
# TODO: Прописать все возвраты для свагера


@app.on_event("startup")
async def startup_event():
    async with async_session_maker() as session:
        for date, schedule_times in schedule_template.items():

            date_obj = datetime.strptime(
                date, '%d.%m.%Y').date()

            query = select(schedule).where(date_obj == schedule.c.date)
            result = await session.execute(query)
            schedule_row = result.first()
            if not schedule_row:
                stmt = insert(schedule).values(
                    date=date_obj,
                    schedule_time=schedule_times
                )
                await session.execute(stmt)
                await session.commit()

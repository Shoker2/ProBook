from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
import json

from .routers.auth import router as auth_router
from .routers.group import router as group_router
from .routers.event import router as event_router
from .routers.coworking import router as coworking_router
from .routers.permissions import router as permissions_router
from .auth import *
from .schemas import *


app = FastAPI(
    title="TP2 API",
)

app.include_router(
    auth_router,
    prefix="/auth",
    tags=["auth"]
)

app.include_router(
    group_router
)

app.include_router(
    event_router
)

app.include_router(
    coworking_router
)

app.include_router(
    permissions_router
)

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

    user = getattr(request.state, "user", None)

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

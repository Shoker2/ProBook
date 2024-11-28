from fastapi import FastAPI, Depends

from .routers import auth_router
from .auth import *
from .schemas import *

app = FastAPI(
    title = "TP2 API",    
)

app.include_router(
    auth_router.router,
    prefix="/auth",
    tags=["auth"]
)

@app.get('/', response_model=BaseTokenResponse[UserRead])
async def root(user: UserToken = Depends(get_current_user)):
    return BaseTokenResponse(
        new_token=user.new_token,
        result=user
    )

# TODO: Прописать все возвраты для свагера
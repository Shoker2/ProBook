from details import *
from config import config
from schemas import *
from database import redis_db, get_async_session
from auth import *
from .uploader import upload as upload_file
from auth.auth import get_user_by_uuid as get_user_by_uuid_db, get_user_image_path, get_microsoft_user_info
from models_ import user as user_db

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError
import math
import io

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

router_microsoft = APIRouter(
    prefix="/microsoft",
)

router_users = APIRouter(
    prefix="/users",
)

@router_microsoft.get("/get_authorization_url", summary="Get Microsoft Authorization URL", response_model=GetAuthorizationUrl)
async def get_authorization_url(redirect_uri: str | None = None):
    """
    Generate a Microsoft authorization URL for user login.
    """

    if redirect_uri is None:
        redirect_uri = REDIRECT_URI

    authorization_url = await microsoft_oauth_client.get_authorization_url(
        redirect_uri=redirect_uri,
        scope=["User.Read", "profile", "openid", "email", "offline_access"] # "User.Read.All"
    )

    return GetAuthorizationUrl(authorization_url=authorization_url)

@router_microsoft.get("/token", response_model=GetToken, summary="Exchange Authorization Code for Tokens")
async def get_token_callback(request: Request, session: AsyncSession = Depends(get_async_session)):
    """
    Exchange the authorization code for access and refresh tokens.
    """

    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=AUTHORIZATION_CODE_NOT_FOUND)

    # Обмен кода на токен
    try:
        token = await microsoft_oauth_client.get_access_token(
            code,
            redirect_uri=REDIRECT_URI
        )
    except GetAccessTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_TOKEN
        )

    return await get_token_by_microsoft_access_token(token, session)


async def get_microsoft_me(user: UserToken, session: AsyncSession):
    """
    Fetch the current user's information from Microsoft Graph API.
    """

    prefix = 'info:'
    user_redis_temp = await redis_db.get(f"{prefix}{user.uuid}_temp")

    if user_redis_temp is not None:
        user_redis = await redis_db.get_dict(f"{prefix}{user.uuid}")

        if user_redis is not None:
            return user_redis

    async with microsoft_oauth_client.get_httpx_client() as client:
        user_info_response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {user.microsoft_access_token}"}
        )

    if user_info_response.status_code != 200:
        raise HTTPException(status_code=user_info_response.status_code, detail=FAILED_FETCH_USER_INFO)

    microsoft_data = user_info_response.json()

    await redis_db.set_dict(f'{prefix}{user.uuid}', microsoft_data)
    await redis_db.set_dict(f'{prefix}{user.uuid}_temp', 1, ex=3600 * 24)

    if microsoft_data is not None and "displayName" in microsoft_data:
        stmt = update(user_db).where(user_db.c.uuid == user.uuid).values(name=microsoft_data['displayName'])
        await session.execute(stmt)
        await session.commit()

    return microsoft_data


async def get_microsoft_me_photo(user: UserToken, session: AsyncSession):
    prefix = 'user_image:'
    image_path = await redis_db.get(f"{prefix}{user.uuid}")
    
    if image_path is None:
        async with microsoft_oauth_client.get_httpx_client() as client:
            user_photo_response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/photo/$value",
                headers={"Authorization": f"Bearer {user.microsoft_access_token}"}
            )

        if user_photo_response.status_code != 200:
            image_path = ""

        else:
            file_content = user_photo_response.content

            file = UploadFile(
                filename=f"{user.uuid}.jpg",
                file=io.BytesIO(file_content),
                headers={"content-type": "image/jpeg"}
            )

            img_save = (await upload_file(user, file, session)).result
            image_path = img_save.file_name

        await redis_db.set(f"{prefix}{user.uuid}", image_path, ex=7200)
        await redis_db.set(f"{prefix}{user.uuid}_value", image_path)

    return image_path if image_path != "" else None



@router_users.get('/me', response_model=BaseTokenResponse[UserReadMicrosoft])
async def get_me_user(user: UserToken = Depends(get_current_user), session: AsyncSession = Depends(get_async_session)):
    microsoft_me_info = await get_microsoft_me(user, session)
    microsoft_me_photo = await get_microsoft_me_photo(user, session)
    
    return BaseTokenResponse(
        new_token=user.new_token,
        result=UserReadMicrosoft(
            **user.model_dump(),
            microsoft=microsoft_me_info,
            image_path=microsoft_me_photo
        ),
    )

@router_users.get('/{uuid}', response_model=BaseTokenResponse[UserReadMicrosoft])
async def get_user_by_uuid(uuid: str, user: UserToken = Depends(get_current_user), session: AsyncSession = Depends(get_async_session)):

    find_user = await get_user_by_uuid_db(uuid, session)

    microsoft_user_info = await get_microsoft_user_info(uuid)
    microsoft_user_photo = await get_user_image_path(uuid)
    
    return BaseTokenResponse(
        new_token=user.new_token,
        result=UserReadMicrosoft(
            **find_user.model_dump(),
            microsoft=microsoft_user_info,
            image_path=microsoft_user_photo
        ),
    )


@router_users.get('/', response_model=BaseTokenPageResponse[list[UserReadMicrosoft]])
async def get_users(
        user: UserToken = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session),

        display_name: str | None = None,
        is_superuser: bool | None = None,
        group_id: int | None = None,
        limit: int = 10,
        page: int = 1,
    ):

    limit = min(max(1, limit), 60)
    page = max(1, page) - 1

    total_pages_stmt = select(func.count(user_db.c.uuid))

    stmt = select(user_db).limit(limit).offset(page * limit)

    if is_superuser is not None:
        stmt = stmt.where(user_db.c.is_superuser == is_superuser)
        total_pages_stmt = total_pages_stmt.where(user_db.c.is_superuser == is_superuser)
    
    if group_id is not None:
        stmt = stmt.where(user_db.c.group_id == group_id)
        total_pages_stmt = total_pages_stmt.where(user_db.c.group_id == group_id)

    if display_name is not None:
        stmt = stmt.filter(user_db.c.name.like(f'%{display_name}%'))
        total_pages_stmt = total_pages_stmt.filter(user_db.c.name.like(f'%{display_name}%'))

    result = await session.execute(stmt)
    data = result.fetchall()

    users = []

    for user_ in data:
        group = await get_group_by_id(id=user_.group_id, session=session)
        if group is None:
            group = await get_default_group(session=session)

        users.append(
            UserReadMicrosoft(
                uuid=user_.uuid,
                is_superuser=user_.is_superuser,
                name=user_.name,
                group=group,

                microsoft= await get_microsoft_user_info(user_.uuid),
                image_path= await get_user_image_path(user_.uuid)
            )
        )

    current_page = page + 1
    total_pages = await session.scalar(total_pages_stmt)
    total_pages = math.ceil(total_pages/limit)
    
    return BaseTokenPageResponse(
        current_page=current_page,
        total_page=total_pages,
        new_token=user.new_token,
        result=users,
    )

router.include_router(router_microsoft)
router.include_router(router_users)
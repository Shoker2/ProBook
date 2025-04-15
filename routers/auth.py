from details import *
from config import config
from schemas import *
from database import redis_db, get_async_session
from auth import *
from .uploader import upload as upload_file

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError
from auth.auth import get_user_by_uuid as get_user_by_uuid_db
from models_ import user as user_db
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


async def get_microsoft_me(user: UserToken = Depends(get_current_user)):
    """
    Fetch the current user's information from Microsoft Graph API.
    """

    prefix = 'info:'
    user_redis_temp = await redis_db.get(f"{prefix}{user.uuid}_temp")

    if user_redis_temp is not None:
        user_redis = await redis_db.get_dict(f"{prefix}{user.uuid}")

        if user_redis is not None:
            return BaseTokenResponse(
                new_token=user.new_token,
                result=user_redis
            )

    async with microsoft_oauth_client.get_httpx_client() as client:
        user_info_response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {user.microsoft_access_token}"}
        )

    if user_info_response.status_code != 200:
        raise HTTPException(status_code=user_info_response.status_code, detail=FAILED_FETCH_USER_INFO)

    await redis_db.set_dict(f'{prefix}{user.uuid}', user_info_response.json())
    await redis_db.set_dict(f'{prefix}{user.uuid}_temp', 1, ex=3600 * 24)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=user_info_response.json()
    )


async def get_microsoft_user_by_uuid(uuid: str, user: UserToken = Depends(get_current_user)):
    """
    Fetch the uuid user's information from Microsoft Graph API.
    """
    prefix = 'info:'
    user_redis_temp = await redis_db.get(f"{prefix}{uuid}_temp")

    if user_redis_temp is not None:
        user_redis = await redis_db.get_dict(f"{prefix}{user.uuid}")

        if user_redis is not None:
            return BaseTokenResponse(
                new_token=user.new_token,
                result=user_redis
            )

    if user_redis_temp is not None and user_redis is not None:
        return BaseTokenResponse(
            new_token=user.new_token,
            result=user_redis
        )

    async with microsoft_oauth_client.get_httpx_client() as client:
        user_info_response = await client.get(
            f"https://graph.microsoft.com/v1.0/users/{uuid}",
            headers={"Authorization": f"Bearer {user.microsoft_access_token}"}
        )

    if user_info_response.status_code != 200:
        raise HTTPException(status_code=user_info_response.status_code, detail=FAILED_FETCH_USER_INFO)

    await redis_db.set_dict(f'{prefix}{uuid}', user_info_response.json())
    await redis_db.set(f'{prefix}{uuid}_temp', 1, ex=3600 * 24)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=user_info_response.json()
    )


async def get_microsoft_me_photo(user: UserToken = Depends(get_current_user)):
    return await get_microsoft_user_photo(str(user.uuid), user)



async def get_microsoft_user_photo(uuid: str, user: UserToken = Depends(get_current_user)):
    """
    Fetch the user's photo from Microsoft Graph API.
    """
    prefix = 'user_image:'
    image_path = await redis_db.get(f"{prefix}{uuid}")
    
    if image_path is None:
        async with microsoft_oauth_client.get_httpx_client() as client:
            user_photo_response = await client.get(
                f"https://graph.microsoft.com/v1.0/users/{uuid}/photo/$value",
                headers={"Authorization": f"Bearer {user.microsoft_access_token}"}
            )

        if user_photo_response.status_code != 200:
            raise HTTPException(status_code=user_photo_response.status_code, detail=FAILED_FETCH_USER_INFO)
        
        file_content = user_photo_response.content

        file = UploadFile(
            filename=f"{uuid}.jpg",
            file=io.BytesIO(file_content),
            headers={"content-type": "image/jpeg"}
        )

        img_save = (await upload_file(user, file)).result
        image_path = img_save.file_name

        await redis_db.set(f"{prefix}{uuid}", image_path, ex=7200)
        await redis_db.set(f"{prefix}{uuid}_value", image_path)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=image_path
    )


@router_users.get('/me', response_model=BaseTokenResponse[UserReadMicrosoft])
async def get_me_user(user: UserToken = Depends(get_current_user)):
    microsoft_me_info = await get_microsoft_me(user)
    microsoft_me_photo = await get_microsoft_me_photo(user)
    
    return BaseTokenResponse(
        new_token=user.new_token,
        result=UserReadMicrosoft(
            **user.model_dump(),
            microsoft=microsoft_me_info.result,
            image_path=microsoft_me_photo.result
        ),
    )

@router_users.get('/{uuid}', response_model=BaseTokenResponse[UserReadMicrosoft])
async def get_user_by_uuid(uuid: str, user: UserToken = Depends(get_current_user), session: AsyncSession = Depends(get_async_session)):

    find_user = await get_user_by_uuid_db(uuid, session)

    microsoft_user_info = await get_microsoft_user_by_uuid(uuid, user)
    microsoft_user_photo = await get_microsoft_user_photo(uuid, user)
    
    return BaseTokenResponse(
        new_token=user.new_token,
        result=UserReadMicrosoft(
            **find_user.model_dump(),
            microsoft=microsoft_user_info.result,
            image_path=microsoft_user_photo.result
        ),
    )


@router_users.get('/', response_model=BaseTokenResponse[list[UserReadMicrosoft]])
async def get_users(
        user: UserToken = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session),

        is_superuser: bool | None = None,
        group_id: int | None = None,
        limit: int = 10,
        page: int = 1,
    ):

    limit = min(max(1, limit), 60)
    page = max(1, page) - 1

    stmt = select(user_db.c.uuid, user_db.c.is_superuser, user_db.c.group_id).limit(limit).offset(page * limit)

    if is_superuser is not None:
        stmt = stmt.where(user_db.c.is_superuser == is_superuser)
    
    if group_id is not None:
        stmt = stmt.where(user_db.c.group_id == group_id)

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
                group=group,

                microsoft= await get_microsoft_user_info(user_.uuid),
                image_path= await get_user_image_path(user_.uuid)
            )
        )
    
    return BaseTokenResponse(
        new_token=user.new_token,
        result=users,
    )

router.include_router(router_microsoft)
router.include_router(router_users)
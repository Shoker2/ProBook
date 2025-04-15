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

@router_microsoft.get("/users/me",
    summary="Get Microsoft User Info",
    response_model=BaseTokenResponse[dict]
)
async def get_microsoft_me(user: UserToken = Depends(get_current_user)):
    """
    Fetch the current user's information from Microsoft Graph API.
    """

    async with microsoft_oauth_client.get_httpx_client() as client:
        user_info_response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {user.microsoft_access_token}"}
        )

    if user_info_response.status_code != 200:
        raise HTTPException(status_code=user_info_response.status_code, detail=FAILED_FETCH_USER_INFO)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=user_info_response.json()
    )

@router_microsoft.get("/users/{uuid}",
    summary="Get Microsoft User Info by UUID",
    response_model=BaseTokenResponse[dict]
)
async def get_microsoft_user_by_uuid(uuid: str, user: UserToken = Depends(get_current_user)):
    """
    Fetch the uuid user's information from Microsoft Graph API.
    """
    async with microsoft_oauth_client.get_httpx_client() as client:
        user_info_response = await client.get(
            f"https://graph.microsoft.com/v1.0/users/{uuid}",
            headers={"Authorization": f"Bearer {user.microsoft_access_token}"}
        )

    if user_info_response.status_code != 200:
        raise HTTPException(status_code=user_info_response.status_code, detail=FAILED_FETCH_USER_INFO)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=user_info_response.json()
    )


@router_microsoft.get("/users/me/photo",
    summary="Get Microsoft My Photo",
    response_model=BaseTokenResponse[str]
)
async def get_microsoft_me_photo(user: UserToken = Depends(get_current_user)):
    return await get_microsoft_user_photo(str(user.uuid), user)

@router_microsoft.get("/users/{uuid}/photo",
    summary="Get Microsoft User Photo",
    response_model=BaseTokenResponse[str]
)
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


@router_users.get('/me', response_model=BaseTokenResponse[UserRead])
async def get_me_user(user: UserToken = Depends(get_current_user)):
    return BaseTokenResponse(
        new_token=user.new_token,
        result=user
    )

@router_users.get('/{uuid}', response_model=BaseTokenResponse[UserRead])
async def get_user_by_uuid(uuid: str, user: UserToken = Depends(get_current_user), session: AsyncSession = Depends(get_async_session)):

    find_user = await get_user_by_uuid_db(uuid, session)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=find_user
    )

router.include_router(router_microsoft)
router.include_router(router_users)
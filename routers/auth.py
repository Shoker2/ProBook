from ..details import *
from ..config import config
from ..schemas import *
from ..database import redis_db, get_async_session
from ..auth import *

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError

router = APIRouter(
    prefix="/microsoft",
)

@router.get("/get_authorization_url", summary="Get Microsoft Authorization URL", response_model=GetAuthorizationUrl)
async def get_authorization_url():
    """
    Generate a Microsoft authorization URL for user login.
    """

    authorization_url = await microsoft_oauth_client.get_authorization_url(
        redirect_uri=REDIRECT_URI,
        scope=["User.Read", "profile", "openid", "email", "offline_access"]
    )

    return GetAuthorizationUrl(authorization_url=authorization_url)

@router.get("/token", response_model=GetToken, summary="Exchange Authorization Code for Tokens")
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

@router.get("/me",
    summary="Get Microsoft User Info",
    response_model=BaseTokenResponse[dict]
)
async def get_me(user: UserToken = Depends(get_current_user)):
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

@router.get('/info', response_model=BaseTokenResponse[UserRead])
async def root(user: UserToken = Depends(get_current_user)):
    return BaseTokenResponse(
        new_token=user.new_token,
        result=user
    )
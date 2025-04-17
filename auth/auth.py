from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy.future import select
from fastapi import HTTPException, status, Depends, Body, Security, Request
from fastapi.security import APIKeyHeader
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from datetime import datetime, timedelta, timezone
from schemas import *
from models_ import user, group as group_db
from database import *
from details import *
from config import config
from httpx_oauth.clients.microsoft import MicrosoftGraphOAuth2
from httpx_oauth.oauth2 import RefreshTokenError

api_key_header = APIKeyHeader(name='Authorization', auto_error=False)

CLIENT_ID = config['Microsoft']['client_id']
CLIENT_SECRET = config['Microsoft']['client_secret']
REDIRECT_URI = config['Microsoft']['redirect_url']

microsoft_oauth_client = MicrosoftGraphOAuth2(CLIENT_ID, CLIENT_SECRET)

ALGORITHM = "HS256"
SECRET = config['Miscellaneous']['secret']

def create_token(data: dict, expires_delta: timedelta | None = None, expire: int | None = None):
    to_encode = data.copy()

    if expire is None:
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET, algorithm=ALGORITHM)

    return encoded_jwt

def create_access_token(user_uuid: str, microsoft_access_token: str, microsoft_refresh_token, expires_at: int):
    token_data = {
        'sub': user_uuid,
        'ma_token': microsoft_access_token,
        'mr_token': microsoft_refresh_token
    }

    return create_token(token_data, expire=expires_at)

async def get_token_by_microsoft_access_token(token: dict, session: AsyncSession):
    """
    Process Microsoft token and fetch user data.

    Args:
        token (dict): Token information containing access and refresh tokens.
        session (AsyncSession): Database session.

    Returns:
        GetToken: Custom token with user data.
    """

    expires_at = token['expires_at']
    access_token = token['access_token']
    refresh_token = token['refresh_token']

    # Получение данных пользователя
    async with microsoft_oauth_client.get_httpx_client() as client:
        user_info_response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {token['access_token']}"}
        )

    if user_info_response.status_code != 200:
        raise HTTPException(
            status_code=user_info_response.status_code,
            detail=FAILED_FETCH_USER_INFO
        )

    user_info = user_info_response.json()
    user_uuid = user_info['id']

    token = create_access_token(
        user_uuid=user_uuid,
        microsoft_access_token=access_token,
        microsoft_refresh_token=refresh_token,
        expires_at=expires_at
    )

    if (await get_user_by_uuid(user_uuid, session)) is None:
        await create_user(uuid_str=user_uuid, session=session)

        prefix = 'info:'
        await redis_db.set_dict(f'{prefix}{user_uuid}', user_info_response.json())
        await redis_db.set_dict(f'{prefix}{user_uuid}_temp', 1, ex=3600 * 24)

    return GetToken(
        token=token
    )

async def auth_refresh_token(refresh_token: str, session: AsyncSession):
    
    try:
        token = await microsoft_oauth_client.refresh_token(
            refresh_token=refresh_token
        )
    except RefreshTokenError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_TOKEN
        )

    return await get_token_by_microsoft_access_token(token, session)

# Получение пользователя по UUID
async def get_user_by_uuid(uuid: str, session: AsyncSession) -> UserRead | None:
    result = await session.execute(select(user.c.uuid, user.c.is_superuser, user.c.group_id).where(user.c.uuid == uuid))
    data = result.first()

    if data is None:
        return  None
    
    group = await get_group_by_id(id=data.group_id, session=session)
    if group is None:
        group = await get_default_group(session=session)

    return UserRead(
        uuid=data.uuid,
        is_superuser=data.is_superuser,
        group=group
    )

async def get_default_group(session: AsyncSession) -> GroupRead | None:
    stmt = select(group_db.c.name, group_db.c.permissions, group_db.c.is_default, group_db.c.id).where(group_db.c.is_default == True)
    data = await session.execute(stmt)

    data = data.first()

    if data is None:
        return None

    return GroupRead(
        id=data.id,
        name=data.name,
        permissions=data.permissions,
        is_default=data.is_default
    )


async def get_microsoft_user_info(uuid: str) -> dict | None:
    return await redis_db.get_dict(f"info:{uuid}")


async def get_user_image_path(uuid: str) -> str | None:
    image_path = await redis_db.get(f"user_image:{uuid}_value")
    return image_path if image_path != "" else None


async def get_group_by_id(id: int, session: AsyncSession) -> GroupRead | None:
    stmt = select(group_db.c.name, group_db.c.permissions, group_db.c.is_default).where(group_db.c.id == id)
    data = await session.execute(stmt)

    data = data.first()

    if data is None:
        return None

    return GroupRead(
        id=id,
        name=data.name,
        permissions=data.permissions,
        is_default=data.is_default
    )

async def get_current_user(
        request: Request,
        token: str = Security(api_key_header),
        session: AsyncSession = Depends(get_async_session),
        repeat: bool = Depends(lambda: True, use_cache=False)
    ) -> UserToken:

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=INVALID_TOKEN
    )

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=TOKEN_NOT_FOUND
        )

    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])

        user_uuid: str = payload.get("sub")
        microsoft_token: str = payload.get("ma_token")
        microsoft_refresh_token: str = payload.get("mr_token")

        if user_uuid is None or microsoft_token is None:
            raise credentials_exception

    except ExpiredSignatureError:
        if repeat:
            payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM], options={"verify_exp": False})
            microsoft_refresh_token: str = payload.get("mr_token")

            new_token = await auth_refresh_token(microsoft_refresh_token, session)
            return await get_current_user(
                request=request,
                token=new_token.token,
                session=session,
                repeat=False
            )
    
        raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=TOKEN_HAS_EXPIRED
            )

    except InvalidTokenError:
        raise credentials_exception
    

    user = await get_user_by_uuid(user_uuid, session)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=FAILED_FETCH_USER_INFO
        )
    
    if repeat:
        token = None

    user = UserToken(
        uuid=user.uuid,
        group=user.group,
        microsoft_access_token=microsoft_token,
        microsoft_refresh_token=microsoft_refresh_token,
        is_superuser=user.is_superuser,
        new_token=token
    )
    
    request.state.__auth_user_data = user

    return user


async def get_current_user_optional(
        request: Request,
        token: str | None = Security(api_key_header),
        session: AsyncSession = Depends(get_async_session)
    ) -> UserToken | None:

    if token is None:
        return None
    
    try:
        return await get_current_user(request=request, token=token, session=session)
    except (HTTPException, InvalidTokenError, ExpiredSignatureError):
        pass
    
    return None
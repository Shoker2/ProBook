from ..details import *
from ..config import config
from ..schemas import *
from ..database import redis_db, get_async_session, create_group, delete_group as delete_group_db
from ..auth import *
from ..models_ import group as group_db
from ..permissions import get_current_user_with_perms, Permissions

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError
from sqlalchemy import update, select, insert, delete
from functools import partial

router = APIRouter(
    prefix="/group",
    tags=["group"]
)

@router.post('/create', response_model=BaseTokenResponse[GroupRead])
async def create_group(
        group: GroupCreate,
        user: UserToken = Depends(partial(get_current_user_with_perms, [Permissions.group_create.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    new_group = await create_group(
        name=group.name,
        permissions=group.permissions,
        session=session
    )

    group = GroupRead(
        id=new_group.id,
        name=new_group.name,
        permissions=new_group.permissions
    )

    return BaseTokenResponse(
        new_token=user.new_token,
        result=group
    )

@router.get('/{id}', response_model=BaseTokenResponse[GroupRead])
async def get_group(
        id: int,
        user: UserToken = Depends(partial(get_current_user_with_perms, [Permissions.group_view.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    group = await get_group_by_id(
        id=id,
        session=session
    )

    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=GROUP_IS_NOT_EXIST
        )

    return BaseTokenResponse(
        new_token=user.new_token,
        result=group
    )

@router.delete('/', response_model=BaseTokenResponse[str])
async def delete_group(
        id: int = Body(embed=True),
        user: UserToken = Depends(partial(get_current_user_with_perms, [Permissions.group_delete.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    await delete_group_db(
        id=id,
        session=session
    )

    return BaseTokenResponse(
        new_token=user.new_token,
        result=OK
    )

@router.put('/', response_model=BaseTokenResponse[str])
async def update_group(
        group: GroupUpdate,
        user: UserToken = Depends(partial(get_current_user_with_perms, [Permissions.group_edit.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    stmt = select(group_db).where(group_db.c.id == group.id)
    result = await session.execute(stmt)
    data = result.first()

    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    stmt = update(group_db).where(group_db.c.id == group.id)

    if group.name is not None:
        stmt = stmt.values(name=group.name)
    
    if group.permissions is not None:
        stmt = stmt.values(permissions=group.permissions)

    await session.execute(stmt)
    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=OK
    )
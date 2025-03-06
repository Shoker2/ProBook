
from ..details import *
from ..config import config
from ..schemas import *
from ..database import redis_db, get_async_session
from ..auth import *
from ..models_ import group as group_db, user as user_db
from ..permissions import get_depend_user_with_perms, Permissions

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError
from sqlalchemy import update, select, insert, delete
from ..action_history import *

router = APIRouter(
    prefix="/groups",
    tags=["groups"]
)

OBJECT_TABLE = "groups"

@router.post('/create', response_model=BaseTokenResponse[GroupRead])
async def create_group(
        group: GroupCreate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.groups_create.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    new_group = Group(
        name=group.name,
        permissions=group.permissions
    )
    
    session.add(new_group)

    await session.refresh(new_group)

    group = GroupRead(
        id=new_group.id,
        name=new_group.name,
        permissions=new_group.permissions,
        is_default=new_group.is_default
    )

    await add_action_to_history(ActionHistoryCreate(
        action=HistoryActions.create.value,
        subject_uuid=user.uuid,
        object_table=OBJECT_TABLE,
        object_id=group.id,
        detail=group.model_dump()
    ), session)

    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=group
    )

@router.get('/my')
async def get_my_group(
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.groups_view.value])),
    ):

    return BaseTokenResponse(
        new_token=user.new_token,
        result=user.group
    )

@router.get('/{id}', response_model=BaseTokenResponse[GroupRead])
async def get_group(
        id: int,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.groups_view.value])),
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

@router.get('/', response_model=BaseTokenResponse[list[GroupRead]])
async def get_all_groups(
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.groups_view.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    stmt = select(group_db.c.id, group_db.c.name, group_db.c.permissions, group_db.c.is_default)
    data = await session.execute(stmt)

    data = data.fetchall()

    groups: list[GroupRead] = []
    for group in data:
        groups.append(
            GroupRead(
                id=group.id,
                name=group.name,
                permissions=group.permissions,
                is_default=group.is_default
            )
        )

    return BaseTokenResponse(
        new_token=user.new_token,
        result=groups
    )

@router.delete('/{id}', response_model=BaseTokenResponse[str])
async def delete_group(
        id: int,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.groups_delete.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    old_data = (await get_group(id, user, session)).result

    await reset_group(id, session)
    stmt = delete(group).where(group.c.id == id)
    
    await session.execute(stmt)

    await add_action_to_history(ActionHistoryCreate(
        action=HistoryActions.delete.value,
        subject_uuid=user.uuid,
        object_table=OBJECT_TABLE,
        object_id=old_data.id,
        detail=old_data
    ), session)

    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=OK
    )

@router.put('/', response_model=BaseTokenResponse[GroupRead])
async def update_group(
        group: GroupUpdate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.groups_edit.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    op_detail = ActionHistoryDetailUpdate()

    stmt = select(group_db).where(group_db.c.id == group.id)
    result = await session.execute(stmt)
    data = result.first()

    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    stmt = update(group_db).where(group_db.c.id == group.id)

    if group.name is not None:
        stmt = stmt.values(name=group.name)
        op_detail.update("name", data._mapping["name"], group.name)
    
    if group.permissions is not None:
        stmt = stmt.values(permissions=group.permissions)
        op_detail.update("permissions", data._mapping["permissions"], group.permissions)
    
    if group.is_default is not None:
        stmt = stmt.values(is_default=group.is_default)
        op_detail.update("is_default", data._mapping["is_default"], group.is_default)

    await session.execute(stmt)

    if not op_detail.empty:
        await add_action_to_history(ActionHistoryCreate(
            action=HistoryActions.update.value,
            subject_uuid=user.uuid,
            object_table=OBJECT_TABLE,
            object_id=group.id,
            detail=op_detail
        ), session)

    await session.commit()

    select_statement = select(group_db).where(group_db.c.id == group.id)
    row = (await session.execute(select_statement)).fetchone()

    result = GroupRead(**row._mapping)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=result
    )

@router.post('/set_user_group', response_model=BaseTokenResponse[UserRead])
async def update_group(
        user_group: UserGroup,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.groups_add_user.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    op_detail = ActionHistoryDetailUpdate()

    if user_group.group_id is not None:
        stmt = select(group_db).where(group_db.c.id == user_group.group_id)
        result = await session.execute(stmt)
        data = result.first()

        if not data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    stmt = select(user_db).where(user_db.c.uuid == user_group.user_uuid)
    result = await session.execute(stmt)
    data = result.first()

    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    
    stmt = update(user_db).where(user_db.c.uuid == user_group.user_uuid).values(group_id=user_group.group_id)

    await session.execute(stmt)

    op_detail.update("group_id", data._mapping["group_id"], user_group.group_id)

    if not op_detail.empty:
        await add_action_to_history(ActionHistoryCreate(
            action=HistoryActions.update.value,
            subject_uuid=user.uuid,
            object_table="user",
            object_id=user_group.user_uuid,
            detail=op_detail
        ), session)

    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=await get_user_by_uuid(user_group.user_uuid, session)
    )
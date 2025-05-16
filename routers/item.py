from details import *
from config import config
from schemas import *
from auth import *
from models_ import item as item_db
from permissions import get_depend_user_with_perms, Permissions

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError
from sqlalchemy import update, select, insert, delete, func
from functools import partial
import math
from action_history import add_action_to_history, HistoryActions

router = APIRouter(
    prefix="/items",
    tags=["items"]
)

OBJECT_TABLE = "item"

@router.post('/', response_model=BaseTokenResponse[ItemRead])
async def create_item(
        item: ItemCreate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.items_create.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    insert_statement = item_db.insert().values(**item.model_dump())
    
    result = await session.execute(insert_statement)

    select_statement = item_db.select().where(item_db.c.id == result.inserted_primary_key[0])
    row = (await session.execute(select_statement)).fetchone()

    result = ItemRead(**row._mapping)

    await add_action_to_history(ActionHistoryCreate(
        action=HistoryActions.create.value,
        subject_uuid=user.uuid,
        object_table=OBJECT_TABLE,
        object_id=result.id,
        detail=row._mapping
    ), session)

    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=result
    )

@router.get('/{id}', response_model=ItemRead)
async def get_item(
        id: int,
        session: AsyncSession = Depends(get_async_session)
    ):

    select_statement = item_db.select().where(item_db.c.id == id)
    row = (await session.execute(select_statement)).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
        )

    result = ItemRead(**row._mapping)

    return result

@router.get('/', response_model=BasePageResponse[list[ItemRead]])
async def get_all_items(
        room_id: int | None = None,
        limit: int = 10,
        page: int = 1,
        session: AsyncSession = Depends(get_async_session)
    ):

    limit = min(max(1, limit), 60)
    page = max(1, page) - 1

    select_statement = item_db.select().limit(limit).offset(page * limit)

    if room_id is not None:
        select_statement = select_statement.where(item_db.c.room_id == room_id)

    rows = (await session.execute(select_statement)).fetchall()

    if rows is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
        )

    result = []

    for row in rows:
        result.append(ItemRead(**row._mapping))

    current_page = page + 1
    total_pages = await session.scalar(select(func.count(user_db.c.uuid)))
    total_pages = math.ceil(total_pages/limit)

    return BasePageResponse(
        current_page=current_page,
        total_page=total_pages,
        result=result
    )

@router.delete(
    '/{id}',
    response_model=BaseTokenResponse[str],
    responses={
        424: {
            "content": {
                "application/json": {
                    "example": {"new_token": "YOUR_TOKEN", "result":{"detail": ITEM_IS_IN_USE}}
                }
            }
        },
    }
)
async def delete_item(
        id: int,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.items_delete.value])),
        session: AsyncSession = Depends(get_async_session)
    ):
    del_item = await get_item(id=id, session=session)

    select_statement = item_db.delete().where(item_db.c.id == id)

    try:
        await session.execute(select_statement)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=ITEM_IS_IN_USE
        )
    
    await add_action_to_history(ActionHistoryCreate(
        action=HistoryActions.delete.value,
        subject_uuid=user.uuid,
        object_table=OBJECT_TABLE,
        object_id=del_item.id,
        detail=del_item.model_dump()
    ), session)
    
    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=OK
    )

@router.patch('/{id}', response_model=BaseTokenResponse[ItemRead])
async def update_item(
        item: ItemUpdate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.items_edit.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    op_detail = ActionHistoryDetailUpdate()
    old_data = await get_item(id=item.id, session=session)

    stmt = item_db.update().where(item_db.c.id == item.id)

    if item.name is not None:
        stmt = stmt.values(name=item.name)
        op_detail.update("name", old_data.name, item.name)
    
    if item.room_id is not None:
        stmt = stmt.values(room_id=item.room_id)
        op_detail.update("room_id", old_data.room_id, item.room_id)

    if stmt.whereclause is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST
        )

    await session.execute(stmt)

    if not op_detail.empty:
        await add_action_to_history(ActionHistoryCreate(
            action=HistoryActions.update.value,
            subject_uuid=user.uuid,
            object_table=OBJECT_TABLE,
            object_id=item.id,
            detail=op_detail
        ), session)

    await session.commit()

    select_statement = item_db.select().where(item_db.c.id == item.id)
    row = (await session.execute(select_statement)).fetchone()

    result = ItemRead(**row._mapping)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=result
    )
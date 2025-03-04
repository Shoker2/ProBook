from ..details import *
from ..config import config
from ..schemas import *
from ..database import redis_db, get_async_session, create_group as create_group_db, delete_group as delete_group_db
from ..auth import *
from ..models_ import item as item_db
from ..permissions import get_depend_user_with_perms, Permissions

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError
from sqlalchemy import update, select, insert, delete
from functools import partial

router = APIRouter(
    prefix="/items",
    tags=["items"]
)

@router.post('/create', response_model=BaseTokenResponse[ItemRead])
async def create_item(
        item: ItemCreate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.items_create.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    insert_statement = item_db.insert().values(**item.model_dump())
    
    result = await session.execute(insert_statement)
    await session.commit()

    select_statement = item_db.select().where(item_db.c.id == result.inserted_primary_key[0])
    row = (await session.execute(select_statement)).fetchone()

    result = ItemRead(**row._mapping)

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

@router.get('/', response_model=list[ItemRead])
async def get_all_items(
        session: AsyncSession = Depends(get_async_session)
    ):

    select_statement = item_db.select()
    rows = (await session.execute(select_statement)).fetchall()

    if rows is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
        )

    result = []

    for row in rows:
        result.append(ItemRead(**row._mapping))

    return result

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

    select_statement = item_db.delete().where(item_db.c.id == id)

    try:
        await session.execute(select_statement)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=ITEM_IS_IN_USE
        )
    
    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=OK
    )

@router.put('/{id}', response_model=BaseTokenResponse[ItemRead])
async def update_item(
        item: ItemUpdate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.items_edit.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    stmt = item_db.update().where(item_db.c.id == item.id)

    if item.name is not None:
        stmt = stmt.values(name=item.name)

    await session.execute(stmt)
    await session.commit()

    select_statement = item_db.select().where(item_db.c.id == item.id)
    row = (await session.execute(select_statement)).fetchone()

    result = ItemRead(**row._mapping)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=result
    )
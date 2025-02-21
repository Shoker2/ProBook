from ..details import *
from ..config import config
from ..schemas import *
from ..database import redis_db, get_async_session, create_group as create_group_db, delete_group as delete_group_db
from ..auth import *
from ..models_ import room as room_db, event as event_db, personal_reservation as personal_reservation_db
from ..permissions import get_depend_user_with_perms, Permissions

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError
from sqlalchemy import update, select, insert, delete
from functools import partial

router = APIRouter(
    prefix="/rooms",
    tags=["rooms"]
)

@router.post('/create', response_model=BaseTokenResponse[RoomRead])
async def create_item(
        room: RoomCreate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.rooms_create.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    insert_statement = room_db.insert().values(**room.model_dump())
    
    result = await session.execute(insert_statement)
    await session.commit()

    select_statement = room_db.select().where(room_db.c.id == result.inserted_primary_key[0])
    row = (await session.execute(select_statement)).fetchone()

    result = RoomRead(**row._mapping)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=result
    )

@router.get('/{id}', response_model=RoomRead)
async def get_item(
        id: int,
        session: AsyncSession = Depends(get_async_session)
    ):

    select_statement = room_db.select().where(room_db.c.id == id)
    row = (await session.execute(select_statement)).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
        )

    result = RoomRead(**row._mapping)

    return result

@router.get('/', response_model=list[RoomRead])
async def get_all_items(
        session: AsyncSession = Depends(get_async_session)
    ):

    select_statement = room_db.select()
    rows = (await session.execute(select_statement)).fetchall()

    if rows is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
        )

    result = []

    for row in rows:
        result.append(RoomRead(**row._mapping))

    return result

@router.delete('/{id}', response_model=BaseTokenResponse[str])
async def delete_item(
        id: int,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.rooms_delete.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    stmt = room_db.delete().where(room_db.c.id == id)
    await session.execute(stmt)

    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=OK
    )

@router.put('/{id}', response_model=BaseTokenResponse[RoomRead])
async def update_item(
        room: RoomUpdate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.rooms_edit.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    stmt = room_db.update().where(room_db.c.id == room.id)

    if room.name is not None:
        stmt = stmt.values(name=room.name)
    
    if room.capacity is not None:
        stmt = stmt.values(capacity=room.capacity)

    await session.execute(stmt)
    await session.commit()

    select_statement = room_db.select().where(room_db.c.id == room.id)
    row = (await session.execute(select_statement)).fetchone()

    result = RoomRead(**row._mapping)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=result
    )
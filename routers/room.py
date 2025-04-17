from details import *
from config import config
from schemas import *
from auth import *
from models_ import room as room_db, event as event_db, personal_reservation as personal_reservation_db
from permissions import get_depend_user_with_perms, Permissions

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError
from sqlalchemy import update, select, insert, delete
from action_history import *

router = APIRouter(
    prefix="/rooms",
    tags=["rooms"]
)

OBJECT_TABLE = "room"

@router.post('/', response_model=BaseTokenResponse[RoomRead])
async def create_item(
        room: RoomCreate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.rooms_create.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    insert_statement = room_db.insert().values(**room.model_dump())
    
    result = await session.execute(insert_statement)

    select_statement = room_db.select().where(room_db.c.id == result.inserted_primary_key[0])
    row = (await session.execute(select_statement)).fetchone()

    result = RoomRead(**row._mapping)

    await add_action_to_history(ActionHistoryCreate(
        action=HistoryActions.create.value,
        subject_uuid=user.uuid,
        object_table=OBJECT_TABLE,
        object_id=room.id,
        detail=row._mapping
    ), session)

    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=result
    )

@router.get('/{id}', response_model=RoomRead)
async def get_room(
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
async def get_all_rooms(
        limit: int = 10,
        page: int = 1,
        session: AsyncSession = Depends(get_async_session)
    ):

    limit = min(max(1, limit), 60)
    page = max(1, page) - 1

    select_statement = room_db.select().limit(limit).offset(page * limit)
    rows = (await session.execute(select_statement)).fetchall()

    if rows is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
        )

    result = []

    for row in rows:
        result.append(RoomRead(**row._mapping))

    return result

@router.delete(
    '/{id}',
    response_model=BaseTokenResponse[str],
    responses={
        424: {
            "content": {
                "application/json": {
                    "example": {"new_token": "YOUR_TOKEN", "result":{"detail": ROOM_IS_IN_USE}}
                }
            }
        },
    }
)
async def delete_room(
        id: int,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.rooms_delete.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    del_room = await get_room(id=id, session=session)
    stmt = room_db.delete().where(room_db.c.id == id)

    try:
        await session.execute(stmt)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=ROOM_IS_IN_USE
        )
    
    await add_action_to_history(ActionHistoryCreate(
        action=HistoryActions.delete.value,
        subject_uuid=user.uuid,
        object_table=OBJECT_TABLE,
        object_id=id,
        detail=del_room
    ), session)

    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=OK
    )

@router.patch('/{id}', response_model=BaseTokenResponse[RoomRead])
async def update_room(
        room: RoomUpdate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.rooms_edit.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    op_detail = ActionHistoryDetailUpdate()
    old_data = await get_room(id=room.id, session=session)

    stmt = room_db.update().where(room_db.c.id == room.id)

    if room.name is not None:
        stmt = stmt.values(name=room.name)
        op_detail.update("name", old_data.name, room.name)
    
    if room.capacity is not None:
        stmt = stmt.values(capacity=room.capacity)
        op_detail.update("capacity", old_data.capacity, room.capacity)
    
    if room.description is not None:
        stmt = stmt.values(description=room.description)
        op_detail.update("description", old_data.description, room.description)
    
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
            object_id=room.id,
            detail=op_detail
        ), session)

    await session.commit()

    select_statement = room_db.select().where(room_db.c.id == room.id)
    row = (await session.execute(select_statement)).fetchone()

    result = RoomRead(**row._mapping)

    return BaseTokenResponse(
        new_token=user.new_token,
        result=result
    )
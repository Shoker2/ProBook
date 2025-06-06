from details import *
from config import config
import logging
import os
from schemas import *
from auth import *
from models_ import room as room_db, event as event_db, personal_reservation as personal_reservation_db, schedule as schedule_db
from permissions import get_depend_user_with_perms, Permissions
from routers.uploader import STATIC_IMAGES_DIR

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError
from sqlalchemy import update, select, insert, delete, func
import math
from action_history import *
from shared.utils.schedule_utils import schedule_template_fix

router = APIRouter(
    prefix="/rooms",
    tags=["rooms"]
)

OBJECT_TABLE = "room"

@router.post('/', response_model=BaseTokenResponse[RoomRead])
async def create_room(
        room: RoomCreate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.rooms_create.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    insert_stmt = (
        room_db.insert()
        .returning(room_db.c.id)
        .values(**room.model_dump())
    )
    res = await session.execute(insert_stmt)
    new_id = res.scalar_one()

    select_stmt = room_db.select().where(room_db.c.id == new_id)
    row = (await session.execute(select_stmt)).fetchone()
    result = RoomRead(**row._mapping)

    await add_action_to_history(ActionHistoryCreate(
        action=HistoryActions.create.value,
        subject_uuid=user.uuid,
        object_table=OBJECT_TABLE,
        object_id=new_id,             
        detail=row._mapping
    ), session)

    await schedule_template_fix(session)
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

@router.get('/', response_model=BasePageResponse[list[RoomRead]])
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
    

    current_page = page + 1
    total_pages = await session.scalar(select(func.count(room_db.c.id)))
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
    
    try:
        stmt = schedule_db.delete().where(schedule_db.c.room_id == id)
        await session.execute(stmt)

        stmt = room_db.delete().where(room_db.c.id == id)
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
        detail=del_room.model_dump()
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

    if room.img is not None or room.img == "":
        if room.img == "":
            room.img = None
        elif not os.path.exists(f'{STATIC_IMAGES_DIR}/{room.img}'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=IMAGE_NOT_EXISTS
            )

        stmt = stmt.values(img=room.img)
        op_detail.update("img", old_data.img, room.img)
    
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
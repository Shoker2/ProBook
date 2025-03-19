from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Query
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as pg_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime
from schemas.token import BaseTokenResponse
from database import get_async_session
from permissions.utils import checking_for_permission
from permissions import Permissions
from schemas.event import (
    EventRead,
    EventCreate,
    EventEdit,
)
from uuid import UUID
from models_ import (
    event as event_db,
    user as user_db,
    room as room_db,
    item as item_db
)
import uuid
from sqlalchemy import (
    insert,
    select,
    delete,
    update,
    cast,
    or_,
    and_,
    func,
    Integer
)
from http import HTTPStatus
from typing import List
from auth import (
    get_current_user,
    UserToken,
)
from details import *
from shared import time_manager
router = APIRouter(
    prefix="/events",
    tags=["events"]
)


@router.post(
    "/",
    response_model=EventCreate
)
async def create_event(
    event_data: EventCreate,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):

    if not time_manager(event_data.date_start, event_data.date_end):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=TIME_VALIDATION_ERROR
        )

    room_query = select(room_db).where(room_db.c.id == event_data.room_id)
    room_result = await session.execute(room_query)
    room = room_result.first()

    event_data.moderated = event_data.moderated and checking_for_permission(Permissions.events_moderate.value, user)

    if not room:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=ROOM_NOT_FOUND
        )

    if event_data.needable_items:
        items_query = select(item_db).where(
            item_db.c.id.in_(event_data.needable_items)
        )
        items_result = await session.execute(items_query)
        found_items = items_result.fetchall()

        if len(found_items) != len(event_data.needable_items):
            found_ids = {item.id for item in found_items}
            missing_ids = set(event_data.needable_items) - found_ids # потом вспомнить
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=ITEMS_NOT_FOUND
            )

    event_dict = event_data.model_dump()
    event_dict['user_uuid'] = user.uuid
    if event_dict['date_start'].tzinfo is not None:
        event_dict['date_start'] = event_dict['date_start'].replace(
            tzinfo=None)

    if event_dict['date_end'].tzinfo is not None:
        event_dict['date_end'] = event_dict['date_end'].replace(
            tzinfo=None)

    overlapping_events_query = select(event_db).where(
        and_(
            event_db.c.room_id == event_data.room_id,
            func.date(event_db.c.date_start) == func.date(
                event_dict['date_start']),
            or_(
                and_(
                    event_db.c.date_start <= event_dict['date_start'],
                    event_db.c.date_end > event_dict['date_start']
                ),
                and_(
                    event_db.c.date_start < event_dict['date_end'],
                    event_db.c.date_end >= event_dict['date_end']
                ),
                and_(
                    event_db.c.date_start >= event_dict['date_start'],
                    event_db.c.date_end <= event_dict['date_end']
                )
            )
        )
    )

    result = await session.execute(overlapping_events_query)
    if result.first():
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=ROOM_IS_ALREADY
        )

    query = insert(event_db).values(**event_dict)
    await session.execute(query)
    await session.commit()

    return event_data


@router.get(
    '/my',
    response_model=List[EventRead]
)
async def my_events(
        current_user: UserToken = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session),
        room_id: int | None = Query(None, description="Необязательный фильтр по id"),
        needable_items: List[int] | None = Query(None, description="Необязательный фильтр по предметам"),
        date_start: datetime | None = Query(None, description="Начальная дата"),
        date_end: datetime | None = Query(None, description="Конечная дата"),
        limit: int = 10,
        page: int = 1,
):
    return await get_events(
        session = session,
        room_id = room_id,
        needable_items = needable_items,
        date_start = date_start,
        date_end = date_end,
        by_user = str(current_user.uuid),
        limit = limit,
        page = page,
    )


@router.get(
    "/{id}",
    response_model=EventRead
)
async def get_event(
    id: int,
    session: AsyncSession = Depends(get_async_session)
):

    query = select(event_db).where(event_db.c.id == id)
    result = await session.execute(query)

    event = result.first()

    if not event:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=EVENT_NOT_FOUND
        )

    return dict(event._mapping)


@router.get(
    "/",
    response_model=List[EventRead]
)
async def get_events(
    session: AsyncSession = Depends(get_async_session),
    room_id: int | None = Query(None, description="Необязательный фильтр по id"),
    needable_items: List[int] | None = Query(None, description="Необязательный фильтр по предметам"),
    date_start: datetime | None = Query(None, description="Начальная дата"),
    date_end: datetime | None = Query(None, description="Конечная дата"),
    by_user: str | None = Query(None, description="Кем был создан ивент"),
    limit: int = 10,
    page: int = 1,
):
    limit = min(max(1, limit), 60)
    page = max(1, page) - 1

    query = select(event_db).limit(limit).offset(page * limit)

    if date_start is not None and date_end is not None:
        query = query.where(
            (event_db.c.date_start <= date_end) 
            &  
            (event_db.c.date_end >= date_start)
            )

    elif date_start is not None:
        query = query.where(event_db.c.date_start >= date_start)
    
    elif date_end is not None:
        query = query.where(event_db.c.date_end <= date_end)

    if room_id is not None:
        query = query.where(event_db.c.room_id == room_id)
    
    if needable_items is not None and needable_items:
        query = query.where(
            cast(event_db.c.needable_items, ARRAY(Integer)).contains(needable_items)
            )
    
    if by_user is not None:
        try:
            by_user = uuid.UUID(str(by_user))
        except ValueError:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=INVALID_UUID
            )

        query = query.where(event_db.c.user_uuid == by_user)

    result = await session.execute(query)

    events = result.fetchall()
    response = [
                EventRead(**(event._mapping))
                for event in events
            ]
    return response


@router.delete(
    "/{id}"
)
async def delete_event(
    id: int,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    query = select(event_db).where(event_db.c.id == id)
    result = await session.execute(query)
    event = result.first()

    if not event:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=EVENT_NOT_FOUND
        )

    is_creator = event.user_uuid == user.uuid
    has_permission = checking_for_permission(
        Permissions.events_delete.value, user)
    if not is_creator and not has_permission:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=PERMISSION_IS_NOT_EXIST
        )

    delete_query = delete(event_db).where(event_db.c.id == id)

    await session.execute(delete_query)
    await session.commit()

    return "OK"


@router.put(
    "/",
    response_model=EventEdit
)
async def edit_event(
    event_data: EventEdit,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):

    if event_data.moderated is not None:
        is_moderator = checking_for_permission(
            Permissions.events_moderate.value, user)
        if not is_moderator:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=PERMISSION_IS_NOT_EXIST
            )

    if event_data.room_id is not None:
        stmt = select(room_db).where(room_db.c.id == event_data.room_id)
        result = await session.execute(stmt)
        room = result.first()

        if not room:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=ROOM_NOT_FOUND
            )

    if event_data.date_start is not None and event_data.date_end is not None:
        if not time_manager(event_data.date_start, event_data.date_end):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=TIME_VALIDATION_ERROR
            )

    if event_data.date_start is not None:
        if event_data.date_start.tzinfo is not None:
            event_data.date_start = event_data.date_start.replace(
                tzinfo=None)

    if event_data.date_end is not None:
        if event_data.date_end.tzinfo is not None:
            event_data.date_end = event_data.date_end.replace(
                tzinfo=None)

    if event_data.needable_items:
        items_query = select(item_db).where(
            item_db.c.id.in_(event_data.needable_items)
        )
        items_result = await session.execute(items_query)
        found_items = items_result.fetchall()

        if len(found_items) != len(event_data.needable_items):
            found_ids = {item.id for item in found_items}
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=ITEMS_NOT_FOUND
            )

    event_data = EventEdit(**event_data.model_dump())

    stmt = select(event_db).where(event_db.c.id == event_data.id)
    result = await session.execute(stmt)
    event = result.first()

    if not event:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=EVENT_NOT_FOUND
        )

    is_creator = event.user_uuid == user.uuid
    has_permission = checking_for_permission(
        Permissions.events_edit.value, user)
    if not is_creator or not has_permission:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=PERMISSION_IS_NOT_EXIST
        )

    if event_data.date_start is not None and event_data.date_end is not None:
        overlapping_events_query = select(event_db).where(
            and_(
                event_db.c.id != event_data.id,
                event_db.c.room_id == event_data.room_id,
                func.date(event_db.c.date_start) == func.date(
                    event_data.date_start),
                or_(
                    and_(
                        event_db.c.date_start <= event_data.date_start,
                        event_db.c.date_end > event_data.date_start
                    ),
                    and_(
                        event_db.c.date_start < event_data.date_end,
                        event_db.c.date_end >= event_data.date_end
                    ),
                    and_(
                        event_db.c.date_start >= event_data.date_start,
                        event_db.c.date_end <= event_data.date_end
                    )
                )
            )
        )

        result = await session.execute(overlapping_events_query)
        if result.first():
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=ROOM_IS_ALREADY
            )
    
    query = update(event_db).where(event_db.c.id == event_data.id).values(
        **event_data.model_dump(exclude_none=True))
    await session.execute(query)
    await session.commit()

    return event_data


@router.post("/participate/{id}", response_model=BaseTokenResponse[int])
async def participate_in_event(
    id: int,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    query = select(event_db).where(event_db.c.id == id)
    result = await session.execute(query)
    event = result.first()

    if not event:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=EVENT_NOT_FOUND
        )

    if event.user_uuid == user.uuid:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=EVENT_CREATOR
        )

    participants = list(event.participants) if event.participants else []
    if str(user.uuid) in [str(uuid) for uuid in participants]:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=EVENT_EXISTS
        )

    participants.append(user.uuid)

    stmt = update(event_db).where(event_db.c.id ==
                                  id).values(participants=participants)
    await session.execute(stmt)
    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=id
    )


@router.post("/unparticipate/{id}", response_model=BaseTokenResponse[int])
async def unparticipate_from_event(
    id: int,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    query = select(event_db).where(event_db.c.id == id)
    result = await session.execute(query)
    event = result.first()

    if not event:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=EVENT_NOT_FOUND
        )

    if event.user_uuid == user.uuid:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=EVENT_CREATOR
        )

    participants = list(event.participants) if event.participants else []

    if str(user.uuid) not in [str(uuid) for uuid in participants]:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=NOT_EVENT_CREATOR
        )

    participants.remove(user.uuid)
    stmt = update(event_db).where(event_db.c.id ==
                                  id).values(participants=participants)
    await session.execute(stmt)
    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=id
    )


@router.get("/participation/my", response_model=BaseTokenResponse[List[EventRead]])
async def get_my_participated_events(
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    query = select(event_db).where(
        or_(
            cast(event_db.c.participants, ARRAY(
                pg_UUID)).contains([user.uuid]),
            event_db.c.user_uuid == user.uuid
        )
    )
    result = await session.execute(query)
    events = result.fetchall()

    response = [
                EventRead(**(event._mapping))
                for event in events
            ]

    return BaseTokenResponse(
        new_token=user.new_token,
        result=response
    )


@router.get("/participation/{uuid}", response_model=BaseTokenResponse[List[EventRead]])
async def get_user_participated_events(
    uuid: UUID,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    user_query = select(user_db).where(user_db.c.uuid == uuid)
    user_result = await session.execute(user_query)
    if not user_result.first():
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=USER_NOT_FOUND
        )

    query = select(event_db).where(
        or_(
            cast(event_db.c.participants, ARRAY(pg_UUID)).contains([uuid]),
            event_db.c.user_uuid == uuid
        )
    )

    result = await session.execute(query)
    events = result.fetchall()

    response = [
                EventRead(**(event._mapping))
                for event in events
            ]
    return BaseTokenResponse(
        new_token=user.new_token,
        result=response
    )

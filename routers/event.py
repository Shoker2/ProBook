from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Query,
    status
)
import os
import math
from sqlalchemy.dialects.postgresql import ARRAY, UUID as pg_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import date, datetime, timedelta
from schemas.token import BaseTokenResponse, BasePageResponse, BaseTokenPageResponse
from database import get_async_session
from permissions.utils import checking_for_permission
from permissions import Permissions
from schemas.event import (
    EventCreate,
    EventEdit,
    EventEditGroup,
    EventRead,
    RepeatEventUpdate,
    Repeatability,
    Status as app_status)
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
    literal_column,
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
from routers.uploader import STATIC_IMAGES_DIR
from shared.utils.events import get_max_date, create_events_before, check_overlapping, repeatability
from shared import time_manager
from config import config
from action_history import add_action_to_history, HistoryActions
from schemas import ActionHistoryCreate, ActionHistoryDetailUpdate

OBJECT_TABLE = "event"

router = APIRouter(
    prefix="/events",
    tags=["events"]
)


@router.post(
    "/",
    response_model=EventRead
)
async def create_event(
    event_data: EventCreate,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    if event_data.img is not None and not os.path.exists(f'{STATIC_IMAGES_DIR}/{event_data.img}'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=IMAGE_NOT_EXISTS
        )
    
    event_data.date_start = event_data.date_start.replace(tzinfo=None)
    event_data.date_end = event_data.date_end.replace(tzinfo=None)

    if not time_manager(event_data.date_start, event_data.date_end):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=TIME_VALIDATION_ERROR
        )
    
    now_date = datetime.now().replace(hour=0, minute=0, microsecond=0, tzinfo=None)

    min_available_date = now_date + timedelta(days=config.get("Miscellaneous", "min_available_day_booking"))
    max_available_date = now_date + timedelta(days=config.get("Miscellaneous", "max_available_day_booking"))

    if min_available_date > event_data.date_start or event_data.date_end > max_available_date:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=DATETIME_NOT_AVAILABLE
        )

    room_query = select(room_db).where(room_db.c.id == event_data.room_id)
    room_result = await session.execute(room_query)
    room = room_result.first()

    if not checking_for_permission(Permissions.events_moderate.value, user):
        event_data.status = app_status.not_moderated.value

    if not room:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=ROOM_NOT_FOUND
        )
    
    if event_data.repeat not in Repeatability._value2member_map_:
        event_data.repeat = Repeatability.NO.value

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
        event_dict['date_start'] = event_dict['date_start']

    if event_dict['date_end'].tzinfo is not None:
        event_dict['date_end'] = event_dict['date_end']

    room_in_use = await check_overlapping(event_data.room_id, event_dict['date_start'], event_dict['date_end'], session)
    if not room_in_use:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ROOM_IS_ALREADY
        )

    query = insert(event_db).values(**event_dict).returning(literal_column('*'))
    res = await session.execute(query)
    res = res.first()

    repeat_res = RepeatEventUpdate(**res._mapping)
    
    if repeat_res.status == app_status.approve.value:
        await create_events_before(repeat_res, get_max_date(), session)

    await add_action_to_history(
        ActionHistoryCreate(
            action=HistoryActions.create.value,
            subject_uuid=user.uuid,
            object_table=OBJECT_TABLE,
            object_id=res.id,
            detail=event_dict
        ),
        session
    )
    
    await session.commit()

    return EventRead(**res._mapping)


@router.get(
    '/my',
    response_model=BaseTokenPageResponse[List[EventRead]]
)
async def my_events(
        current_user: UserToken = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session),
        room_id: int | None = Query(None, description="Необязательный фильтр по id"),
        needable_items: List[int] | None = Query(None, description="Необязательный фильтр по предметам"),
        date_start: datetime | None = Query(None, description="Начальная дата"),
        date_end: datetime | None = Query(None, description="Конечная дата"),
        status: int | None = None,
        limit: int = 10,
        page: int = 1,
):
    result = await get_events(
        session = session,
        room_id = room_id,
        needable_items = needable_items,
        date_start = date_start,
        date_end = date_end,
        by_user = str(current_user.uuid),
        limit = limit,
        page = page,
        status = status
    )

    return BaseTokenPageResponse(
        current_page=result.current_page,
        total_page=result.total_page,
        new_token=current_user.new_token,
        result=result.result,
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
    response_model=BasePageResponse[List[EventRead]]
)
async def get_events(
    session: AsyncSession = Depends(get_async_session),
    room_id: int | None = Query(None, description="Необязательный фильтр по id"),
    needable_items: List[int] | None = Query(None, description="Необязательный фильтр по предметам"),
    date_start: datetime | None = Query(None, description="Начальная дата"),
    date_end: datetime | None = Query(None, description="Конечная дата"),
    by_user: str | None = Query(None, description="Кем был создан ивент"),
    status: int | None = None,
    limit: int = 10,
    page: int = 1,
):
    limit = min(max(1, limit), 60)
    page = max(1, page) - 1

    query = select(event_db).limit(limit).offset(page * limit).order_by(event_db.c.date_start)

    if status is not None:
        query = query.where(event_db.c.status == status)

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

    current_page = page + 1
    total_pages = await session.scalar(select(func.count(user_db.c.uuid)))
    total_pages = math.ceil(total_pages/limit)

    return BasePageResponse(
        current_page=current_page,
        total_page=total_pages,
        result=response
    )


@router.delete(
    "/{id}"
)
async def delete_event(
    id: int,
    for_group: bool = False,
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

    event_group = RepeatEventUpdate(**event._mapping)

    if for_group:
        delete_query = delete(event_db).where(event_db.c.event_base_id == event_group.event_base_id)
    else:
        delete_query = delete(event_db).where(event_db.c.id == id)

    await session.execute(delete_query)
    
    await add_action_to_history(
        ActionHistoryCreate(
            action=HistoryActions.delete.value,
            subject_uuid=user.uuid,
            object_table=OBJECT_TABLE,
            object_id=id,
            detail=dict(event._mapping)
        ),
        session
    )
    
    await session.commit()

    return "OK"


@router.patch(
    "/",
    response_model=EventEdit
)
async def edit_event(
    event_data: EventEdit,
    for_group: bool = False,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):

    if event_data.status is not None:
        is_moderator = checking_for_permission(
            Permissions.events_moderate.value, user)
        if not is_moderator:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=PERMISSION_IS_NOT_EXIST
            )
    
    if event_data.img is not None or event_data.img == "":
        if event_data.img == "":
            event_data.img = None
        elif not os.path.exists(f'{STATIC_IMAGES_DIR}/{event_data.img}'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=IMAGE_NOT_EXISTS
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
        room_in_use = await check_overlapping(event_data.room_id, event_data.date_start, event_data.date_end, session)
        if not room_in_use:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ROOM_IS_ALREADY
            )
    
    if for_group and (event_data.room_id is not None or event_data.date_start is not None or event_data.date_end is not None or event_data.repeat is not None or event_data.status == app_status.approve.value):
        query = select(event_db).where(
            event_db.c.event_base_id == event.event_base_id,
            event_db.c.date_start >= datetime.now().replace(tzinfo=None),
        ).order_by(event_db.c.date_start.asc()).limit(1)

        res = await session.execute(query)
        res = res.first()

        repeat_res = RepeatEventUpdate(**res._mapping)

        query = delete(event_db).where(
            event_db.c.event_base_id == event.event_base_id,
            event_db.c.date_start >= repeat_res.date_start
        )
        await session.execute(query)

        repeat_res = repeat_res.model_copy(update=event_data.model_dump(exclude_none=True))

        if repeat_res.repeat not in Repeatability._value2member_map_:
            repeat_res.repeat = Repeatability.NO.value

        repeat_res = await create_event(event_data=EventCreate(**repeat_res.model_dump()), user=user, session=session) 

        query = select(event_db).where(
            event_db.c.id == repeat_res.id
        )

    
    elif for_group:
        query = update(event_db).where(event_db.c.event_base_id == event.event_base_id).values(**event_data.model_dump(exclude_none=True, exclude={'id'})).returning(literal_column('*'))

    else:
        query = update(event_db).where(event_db.c.id == event_data.id).values(**event_data.model_dump(exclude_none=True)).returning(literal_column('*'))
    
    res = await session.execute(query)
    res = res.first()

    # Добавляем запись в историю действий
    detail_update = ActionHistoryDetailUpdate()
    update_data = event_data.model_dump(exclude_none=True)
    
    for key, new_value in update_data.items():
        if key != 'id':
            detail_update.update(key, getattr(event, key), new_value)
    
    await add_action_to_history(
        ActionHistoryCreate(
            action=HistoryActions.update.value,
            subject_uuid=user.uuid,
            object_table=OBJECT_TABLE,
            object_id=event_data.id,
            detail=detail_update
        ),
        session
    )

    await session.commit()

    return EventEdit(**res._mapping)


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
    
    await add_action_to_history(
        ActionHistoryCreate(
            action=HistoryActions.update.value,
            subject_uuid=user.uuid,
            object_table=OBJECT_TABLE,
            object_id=id,
            detail={"action": "participate", "user_uuid": str(user.uuid)}
        ),
        session
    )
    
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
    
    await add_action_to_history(
        ActionHistoryCreate(
            action=HistoryActions.update.value,
            subject_uuid=user.uuid,
            object_table=OBJECT_TABLE,
            object_id=id,
            detail={"action": "unparticipate", "user_uuid": str(user.uuid)}
        ),
        session
    )
    
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

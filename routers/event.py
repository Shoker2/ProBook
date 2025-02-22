from fastapi import (
    APIRouter,
    HTTPException,
    Depends
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID as pg_UUID
from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas.token import BaseTokenResponse
from ..database import get_async_session
from ..permissions.utils import checking_for_permission
from ..permissions import Permissions
from ..schemas.event import (
    EventRead,
    EventCreate,
    EventEdit,
)
from uuid import UUID
from ..models_ import (
    event as event_db,
    user as user_db,
    room as room_db,
    item as item_db
)
from sqlalchemy import (
    insert,
    select,
    delete,
    update,
    cast,
    or_
)
from http import HTTPStatus
from typing import List
from ..auth import (
    get_current_user,
    UserToken,
)
from ..details import *
from ..shared import time_manager
router = APIRouter(
    prefix="/events",
    tags=["events"]
)


@router.post(
    "/create",
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

    user_query = select(user_db).where(
        user_db.c.uuid == user.uuid)
    user_result = await session.execute(user_query)

    if not user_result.first():
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=USER_NOT_FOUND
        )

    room_query = select(room_db).where(room_db.c.id == event_data.room_id)
    room_result = await session.execute(room_query)
    room = room_result.first()

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
            missing_ids = set(event_data.needable_items) - found_ids
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
):
    query = select(event_db).where(event_db.c.user_uuid == current_user.uuid)
    result = await session.execute(query)
    rows = result.fetchall()

    events_info = [
        EventRead(
            id=row._mapping["id"],
            room_id=row._mapping["room_id"],
            info_for_moderator=row._mapping["info_for_moderator"],
            title=row._mapping["title"],
            description=row._mapping["description"],
            participants=row._mapping["participants"],
            img=row._mapping["img"],
            repeat=row._mapping["repeat"],
            user_uuid=row._mapping["user_uuid"],
            date_start=row._mapping["date_start"],
            date_end=row._mapping["date_end"],
            moderated=row._mapping["moderated"],
            needable_items=row._mapping.get("needable_items", [])
        )
        for row in rows
        ]
    return events_info


@ router.get(
    "/{id}",
    response_model=EventRead
)
async def get_event(
    id: int,
    session: AsyncSession=Depends(get_async_session)
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


@ router.get(
    "/",
    response_model=list[EventRead]
)
async def get_all_events(
    session: AsyncSession=Depends(get_async_session)
):
    query = select(event_db)
    result = await session.execute(query)
    events = result.all()

    return [dict(event._mapping) for event in events]


@ router.delete(
    "/{id}"
)
async def delete_event(
    id: int,
    user: UserToken=Depends(get_current_user),
    session: AsyncSession=Depends(get_async_session)
):
    query = select(event_db).where(event_db.c.id == id)
    result = await session.execute(query)
    event = result.first()

    if not event:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=EVENT_NOT_FOUND
        )

    is_creator = event.user_uuid == user.uuid
    has_permission = checking_for_permission(
        Permissions.events_delete.value, user)
    if not is_creator or not has_permission:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=PERMISSION_IS_NOT_EXIST
        )

    delete_query = delete(event_db).where(event_db.c.id == id)

    await session.execute(delete_query)
    await session.commit()

    return "OK"


@ router.put(
    "/",
    response_model=EventEdit
)
async def edit_event(
    event_data: EventEdit,
    user: UserToken=Depends(get_current_user),
    session: AsyncSession=Depends(get_async_session)
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

    query = update(event_db).where(event_db.c.id == event_data.id).values(
        **event_data.model_dump(exclude_none=True))
    await session.execute(query)
    await session.commit()

    return event_data


@ router.post("/participate/{id}", response_model=BaseTokenResponse[int])
async def participate_in_event(
    id: int,
    user: UserToken=Depends(get_current_user),
    session: AsyncSession=Depends(get_async_session)
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


@ router.post("/unparticipate/{id}", response_model=BaseTokenResponse[int])
async def unparticipate_from_event(
    id: int,
    user: UserToken=Depends(get_current_user),
    session: AsyncSession=Depends(get_async_session)
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


@ router.get("/participation/my", response_model=BaseTokenResponse[List[EventRead]])
async def get_my_participated_events(
    user: UserToken=Depends(get_current_user),
    session: AsyncSession=Depends(get_async_session)
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

    events_list = [
        EventRead(
            id=event.id,
            room_id=event.room_id,
            info_for_moderator=event.info_for_moderator,
            title=event.title,
            description=event.description,
            participants=event.participants,
            img=event.img,
            repeat=event.repeat,
            user_uuid=event.user_uuid,
            date_start=event.date_start,
            date_end=event.date_end,
            moderated=event.moderated,
            needable_items=event.needable_items
        )
        for event in events
    ]

    return BaseTokenResponse(
        new_token=user.new_token,
        result=events_list
    )


@ router.get("/participation/{uuid}", response_model=BaseTokenResponse[List[EventRead]])
async def get_user_participated_events(
    uuid: UUID,
    user: UserToken=Depends(get_current_user),
    session: AsyncSession=Depends(get_async_session)
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

    events_list = [
        EventRead(
            id=event.id,
            room_id=event.room_id,
            info_for_moderator=event.info_for_moderator,
            title=event.title,
            description=event.description,
            participants=event.participants,
            img=event.img,
            repeat=event.repeat,
            user_uuid=event.user_uuid,
            date_start=event.date_start,
            date_end=event.date_end,
            moderated=event.moderated,
            needable_items=event.needable_items
        )
        for event in events
    ]
    return BaseTokenResponse(
        new_token=user.new_token,
        result=events_list
    )

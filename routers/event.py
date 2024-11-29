from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_async_session
from ..permissions.utils import checking_for_permission
from ..permissions import Permissions
from ..schemas.event import (
    EventCreate,
)
from ..models_ import (
    event as event_db,
    user as user_db,
    room as room_db
)
from sqlalchemy import (
    insert,
    select,
    delete
)
from http import HTTPStatus
from ..auth import get_current_user, UserToken

router = APIRouter(
    prefix="/event",
    tags=["event"]
)


@router.post(
    "/create"
)
async def create_event(
    event_data: EventCreate,
    current_user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):

    if event_data.date_start > event_data.date_end:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN
        )

    if event_data.user_uuid != current_user.uuid:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN
        )

    user_query = select(user_db).where(
        user_db.c.uuid == event_data.user_uuid)
    user_result = await session.execute(user_query)
    user = user_result.first()

    if not user:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND
        )

    room_query = select(room_db).where(room_db.c.id == event_data.room_id)
    room_result = await session.execute(room_query)
    room = room_result.first()

    if not room:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND
        )

    event_dict = event_data.model_dump()
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
    "/{id}"
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
            status_code=HTTPStatus.NOT_FOUND
        )

    return dict(event._mapping)


@router.delete(
    "/{id}"
)
async def delete_event(
    id: int,
    current_user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    query = select(event_db).where(event_db.c.id == id)
    result = await session.execute(query)
    event = result.first()

    if not event:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN
        )

    is_creator = event.user_uuid == current_user.uuid
    has_permission = checking_for_permission(
        Permissions.event_delete.value, current_user)
    if not is_creator or not has_permission:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN
        )

    delete_query = delete(event_db).where(event_db.c.id == id)

    await session.execute(delete_query)
    await session.commit()

    return "OK"


# TODO: 1) редактирование - может только создатель события и те у кого есть права на это

from fastapi import (
    APIRouter,
    HTTPException,
    Depends
)
from ..schemas.coworking import (
    CoworkingCreate,
    CoworkingEdit,
    CoworkingRead,
    ReadItem
)
from typing import List
from ..auth import get_current_user
from ..database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from ..auth import UserToken
from http import HTTPStatus
from ..details import *
from sqlalchemy import (
    select,
    insert,
    delete,
    update,
)
from ..permissions import (
    checking_for_permission,
    Permissions,
)
from ..shared import time_manager
from ..models_ import (
    user as user_db,
    personal_reservation as coworking_db,
    room as room_db,
    item as item_db,
)

router = APIRouter(
    prefix="/coworkings",
    tags=["coworkings"]
)


@router.post(
    "/create",
    response_model=CoworkingCreate
)
async def create_coworking(
    coworking_data: CoworkingCreate,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):

    if not time_manager(coworking_data.date_start, coworking_data.date_end):
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=TIME_VALIDATION_ERROR
        )

    if coworking_data.needable_items:
        items_query = select(item_db).where(
            item_db.c.id.in_(coworking_data.needable_items)
        )
        items_result = await session.execute(items_query)
        found_items = items_result.fetchall()

        if len(found_items) != len(coworking_data.needable_items):
            found_ids = {item.id for item in found_items}
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=ITEMS_NOT_FOUND
            )

    user_query = select(user_db).where(
        user_db.c.uuid == user.uuid)
    user_result = await session.execute(user_query)

    if not user_result.first():
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=USER_NOT_FOUND
        )

    coworking_query = select(coworking_db).where(
        coworking_db.c.room_id == coworking_data.room_id
    )
    coworking_result = await session.execute(coworking_query)
    coworking = coworking_result.first()

    if coworking:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT,
            detail=COWORKING_EXISTS
        )

    room_query = select(room_db).where(room_db.c.id == coworking_data.room_id)
    room_result = await session.execute(room_query)
    room = room_result.first()

    if not room:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=ROOM_NOT_FOUND
        )

    coworking_dict = coworking_data.model_dump()
    coworking_dict['user_uuid'] = user.uuid
    coworking_dict['moderated'] = False

    if coworking_dict['date_start'].tzinfo is not None:
        coworking_dict['date_start'] = coworking_dict['date_start'].replace(
            tzinfo=None)

    if coworking_dict['date_end'].tzinfo is not None:
        coworking_dict['date_end'] = coworking_dict['date_end'].replace(
            tzinfo=None)

    query = insert(coworking_db).values(**coworking_dict)
    await session.execute(query)
    await session.commit()

    return coworking_data


@router.get(
    '/my',
    response_model=List[ReadItem]
)
async def my_coworkings(
        current_user: UserToken = Depends(get_current_user),
        session: AsyncSession = Depends(get_async_session)
):
    query = select(coworking_db).where(
        coworking_db.c.user_uuid == current_user.uuid)
    result = await session.execute(query)
    rows = result.fetchall()
    events_info = [
        ReadItem(
            id=row._mapping["id"],
            room_id=row._mapping["room_id"],
            user_uuid=row._mapping["user_uuid"],
            info_for_moderator=row._mapping["info_for_moderator"],
            moderated=row._mapping["moderated"],
            needable_items=row._mapping.get("needable_items", []),
            date_start=row._mapping["date_start"],
            date_end=row._mapping["date_end"],
        )
        for row in rows
    ]
    return events_info


@router.get(
    "/{id}",
    response_model=ReadItem
)
async def get_coworking(
    id: int,
    session: AsyncSession = Depends(get_async_session)
):
    query = select(coworking_db).where(coworking_db.c.id == id)
    result = await session.execute(query)

    coworking = result.first()

    if not coworking:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=COWORKING_NOT_FOUND
        )

    return dict(coworking._mapping)


@router.get(
    "/",
    response_model=list[ReadItem]
)
async def get_all_coworkings(
    session: AsyncSession = Depends(get_async_session)
):
    query = select(coworking_db)
    result = await session.execute(query)
    coworkings = result.all()

    return [dict(coworking._mapping) for coworking in coworkings]


@router.delete("/{id}")
async def delete_coworking(
    id: int,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    query = select(coworking_db).where(
        coworking_db.c.id == id
    )
    result = await session.execute(query)

    coworking = result.first()

    if not coworking:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=COWORKING_NOT_FOUND
        )

    is_creator = coworking.user_uuid == user.uuid
    has_permission = checking_for_permission(
        Permissions.coworkings_delete.value, user)

    if not is_creator or not has_permission:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=PERMISSION_IS_NOT_EXIST
        )

    delete_query = delete(coworking_db).where(
        coworking_db.c.id == id
    )
    await session.execute(delete_query)
    await session.commit()

    return "OK"


@router.put(
    "/",
    response_model=CoworkingEdit
)
async def edit_coworking(
    coworking_data: CoworkingEdit,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):

    if coworking_data.moderated is not None:
        is_moderator = checking_for_permission(
            Permissions.coworkings_moderate.value, user)
        if not is_moderator:
            raise HTTPException(
                status_code=HTTPStatus.FORBIDDEN,
                detail=PERMISSION_IS_NOT_EXIST
            )

    stmt = select(coworking_db).where(
        coworking_db.c.id == coworking_data.id
    )
    result = await session.execute(stmt)
    coworking = result.first()

    if not coworking:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=COWORKING_NOT_FOUND
        )

    is_creator = coworking.user_uuid == user.uuid
    has_permission = checking_for_permission(
        Permissions.coworkings_edit.value, user)

    if not is_creator or not has_permission:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=PERMISSION_IS_NOT_EXIST
        )

    if coworking_data.room_id is not None:
        stmt = select(room_db).where(room_db.c.id == coworking_data.room_id)
        result = await session.execute(stmt)
        room = result.first()

        if not room:
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=ROOM_NOT_FOUND
            )

    if coworking_data.date_start is not None:
        if coworking_data.date_start.tzinfo is not None:
            coworking_data.date_start = coworking_data.date_start.replace(
                tzinfo=None)

    if coworking_data.date_end is not None:
        if coworking_data.date_end.tzinfo is not None:
            coworking_data.date_end = coworking_data.date_end.replace(
                tzinfo=None
            )

    if coworking_data.date_start is not None and coworking_data.date_end is not None:
        if not time_manager(coworking_data.date_start, coworking_data.date_end):
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=TIME_VALIDATION_ERROR
            )

    if coworking_data.needable_items:
        items_query = select(item_db).where(
            item_db.c.id.in_(coworking_data.needable_items)
        )
        items_result = await session.execute(items_query)
        found_items = items_result.fetchall()

        if len(found_items) != len(coworking_data.needable_items):
            found_ids = {item.id for item in found_items}
            missing_ids = set(coworking_data.needable_items) - found_ids
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=ITEMS_NOT_FOUND
            )

    coworking_data = CoworkingEdit(**coworking_data.model_dump())

    query = update(coworking_db).where(
        coworking_db.c.id == coworking_data.id
    ).values(**coworking_data.model_dump(exclude_none=True))
    await session.execute(query)
    await session.commit()

    return coworking_data

from fastapi import (
    APIRouter,
    HTTPException,
    Depends,
    Query
)
import math
from routers.item import OBJECT_TABLE
from schemas.coworking import (
    CoworkingCreate,
    CoworkingEdit,
    CoworkingRead,
    ReadItem,
    Status as app_status
)
from datetime import datetime, date, timedelta
from typing import List
from auth import get_current_user
from database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from auth import UserToken
from http import HTTPStatus
from details import *
from sqlalchemy import (
    select,
    insert,
    delete,
    update,
    or_,
    and_,
    func,
    cast,
    Integer
)
from sqlalchemy.dialects.postgresql import ARRAY, INTEGER
from permissions import (
    checking_for_permission,
    Permissions,
)
from shared import time_manager
import uuid
from models_ import (
    user as user_db,
    personal_reservation as coworking_db,
    room as room_db,
    item as item_db,
)
from config import config
from schemas import *
from auth import *
from action_history import add_action_to_history, HistoryActions

router = APIRouter(
    prefix="/coworkings",
    tags=["coworkings"]
)

OBJECT_TABLE = "personal_reservation"

@router.post("/", response_model=CoworkingRead)
async def create_coworking(
    coworking_data: CoworkingCreate,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    coworking_data.date_start = coworking_data.date_start.replace(tzinfo=None)
    coworking_data.date_end   = coworking_data.date_end.replace(tzinfo=None)
    if not time_manager(coworking_data.date_start, coworking_data.date_end):
        raise HTTPException(HTTPStatus.BAD_REQUEST, detail="TIME_VALIDATION_ERROR")
    min_days = int(config.get("Miscellaneous", "min_available_day_booking"))
    max_days = int(config.get("Miscellaneous", "max_available_day_booking"))
    today    = datetime.now().replace(hour=0, minute=0, microsecond=0)
    min_date = today + timedelta(days=min_days)
    max_date = today + timedelta(days=max_days)
    if coworking_data.date_start < min_date or coworking_data.date_end > max_date:
        raise HTTPException(HTTPStatus.BAD_REQUEST, detail="DATETIME_NOT_AVAILABLE")
    room_row = await session.execute(
        select(room_db).where(room_db.c.id == coworking_data.room_id)
    )
    if not room_row.first():
        raise HTTPException(HTTPStatus.NOT_FOUND, detail="ROOM_NOT_FOUND")
    if not checking_for_permission(Permissions.coworkings_moderate.value, user):
        coworking_data.status = app_status.not_moderated.value
    overlap = await session.execute(
        select(coworking_db).where(
            and_(
                coworking_db.c.room_id == coworking_data.room_id,
                coworking_db.c.status == app_status.approve.value,
                func.date(coworking_db.c.date_start) == func.date(coworking_data.date_start),
                or_(
                    and_(
                        coworking_db.c.date_start <= coworking_data.date_start,
                        coworking_db.c.date_end   >  coworking_data.date_start
                    ),
                    and_(
                        coworking_db.c.date_start <  coworking_data.date_end,
                        coworking_db.c.date_end   >= coworking_data.date_end
                    ),
                    and_(
                        coworking_db.c.date_start >= coworking_data.date_start,
                        coworking_db.c.date_end   <= coworking_data.date_end
                    ),
                ),
            )
        )
    )
    if overlap.first():
        raise HTTPException(HTTPStatus.CONFLICT, detail="ROOM_IS_ALREADY")
    insert_stmt = (
        insert(coworking_db)
        .values(**coworking_data.model_dump(), user_uuid=str(user.uuid))
        .returning(coworking_db)
    )
    res = await session.execute(insert_stmt)
    res = res.fetchone()

    await add_action_to_history(
        ActionHistoryCreate(
            action=HistoryActions.create.value,
            subject_uuid=user.uuid,
            object_table="personal_reservation",
            object_id=res.id,
            detail={**res._mapping, "user_uuid": str(user.uuid)}
        ),
        session
    )
    await session.commit()
    return res._mapping



@router.get(
    '/my',
    response_model=BaseTokenPageResponse[List[ReadItem]]
)
async def my_coworkings(
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
    result = await get_coworkings(
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
    response_model=BasePageResponse[list[ReadItem]]
)
async def get_coworkings(
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

    date_start = date_start.replace(tzinfo=None)
    date_end = date_end.replace(tzinfo=None)

    query = select(coworking_db).limit(limit).offset(page * limit).order_by(coworking_db.c.date_start)
    total_pages_stmt = select(func.count(coworking_db.c.id))

    if status is not None:
        query = query.where(coworking_db.c.status == status)
        total_pages_stmt = total_pages_stmt.where(coworking_db.c.status == status)

    if date_start is not None and date_end is not None:
        query = query.where(
            (coworking_db.c.date_start <= date_end) 
            &  
            (coworking_db.c.date_end >= date_start)
            )
        
        total_pages_stmt = total_pages_stmt.query.where(
            (coworking_db.c.date_start <= date_end) 
            &  
            (coworking_db.c.date_end >= date_start)
            )

    elif date_start is not None:
        query = query.where(coworking_db.c.date_start >= date_start)
        total_pages_stmt = total_pages_stmt.where(coworking_db.c.date_start >= date_start)
    
    elif date_end is not None:
        query = query.where(coworking_db.c.date_end <= date_end)
        total_pages_stmt = total_pages_stmt.where(coworking_db.c.date_end <= date_end)

    if room_id is not None:
        query = query.where(coworking_db.c.room_id == room_id)
        total_pages_stmt = total_pages_stmt.where(coworking_db.c.room_id == room_id)
    
    if needable_items is not None and needable_items:
        query = query.where(
            cast(coworking_db.c.needable_items, ARRAY(Integer)).contains(needable_items)
        )
        total_pages_stmt = total_pages_stmt.where(
            cast(coworking_db.c.needable_items, ARRAY(Integer)).contains(needable_items)
        )
    
    if by_user is not None:
        try:
            by_user = uuid.UUID(str(by_user))
        except ValueError:
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=INVALID_UUID
            )

        query = query.where(coworking_db.c.user_uuid == by_user)
        total_pages_stmt = total_pages_stmt.where(coworking_db.c.user_uuid == by_user)

    result = await session.execute(query)
    coworkings = result.fetchall()

    response = [
        ReadItem(**(coworking._mapping))
        for coworking in coworkings
    ]

    current_page = page + 1
    total_pages = await session.scalar(total_pages_stmt)
    total_pages = math.ceil(total_pages/limit)

    return BasePageResponse(
        current_page=current_page,
        total_page=total_pages,
        result=response
    )


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

    if not is_creator and not has_permission:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN,
            detail=PERMISSION_IS_NOT_EXIST
        )

    delete_query = delete(coworking_db).where(
        coworking_db.c.id == id
    )
    await session.execute(delete_query)
    
    await add_action_to_history(
        ActionHistoryCreate(
            action=HistoryActions.delete.value,
            subject_uuid=user.uuid,
            object_table="personal_reservation",
            object_id=id,
            detail=dict(coworking._mapping)
        ),
        session
    )
    
    await session.commit()

    return "OK"


@router.patch(
    "/",
    response_model=CoworkingEdit
)
async def edit_coworking(
    coworking_data: CoworkingEdit,
    user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):

    if coworking_data.status is not None:
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
            raise HTTPException(
                status_code=HTTPStatus.NOT_FOUND,
                detail=ITEMS_NOT_FOUND
            )

    if coworking_data.date_start is not None and coworking_data.date_end is not None:
        overlapping_query = select(coworking_db).where(
            and_(
                coworking_db.c.id != coworking_data.id,  # Exclude current coworking
                coworking_db.c.status == app_status.approve.value,
                coworking_db.c.room_id == coworking.room_id,
                func.date(coworking_db.c.date_start) == func.date(
                    coworking_data.date_start),
                or_(
                    and_(
                        coworking_db.c.date_start <= coworking_data.date_start,
                        coworking_db.c.date_end > coworking_data.date_start
                    ),
                    and_(
                        coworking_db.c.date_start < coworking_data.date_end,
                        coworking_db.c.date_end >= coworking_data.date_end
                    ),
                    and_(
                        coworking_db.c.date_start >= coworking_data.date_start,
                        coworking_db.c.date_end <= coworking_data.date_end
                    )
                )
            )
        )
        result = await session.execute(overlapping_query)
        if result.first():
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=COWORKING_IS_ALREADY
            )

    query = update(coworking_db).where(
        coworking_db.c.id == coworking_data.id
    ).values(**coworking_data.model_dump(exclude_none=True))
    await session.execute(query)
    
    detail_update = ActionHistoryDetailUpdate()
    update_data = coworking_data.model_dump(exclude_none=True)
    
    for key, new_value in update_data.items():
        if key != 'id':
            detail_update.update(key, getattr(coworking, key), new_value)
    
    await add_action_to_history(
        ActionHistoryCreate(
            action=HistoryActions.update.value,
            subject_uuid=user.uuid,
            object_table="personal_reservation",
            object_id=coworking_data.id,
            detail=detail_update
        ),
        session
    )
    
    await session.commit()

    return coworking_data

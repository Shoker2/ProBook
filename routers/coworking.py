from fastapi import (
    APIRouter,
    HTTPException,
    Depends
)
from ..schemas.coworking import (
    CoworkingCreate,
    CoworkingEdit,
)
from ..auth import get_current_user
from ..database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from ..auth import UserToken
from http import HTTPStatus
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
from ..models_ import (
    user as user_db,
    personal_reservation as coworking_db,
    room as room_db,
)

router = APIRouter(
    prefix="/coworking",
    tags=["coworking"]
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

    if coworking_data.user_uuid != user.uuid:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN
        )

    user_query = select(user_db).where(
        user_db.c.uuid == coworking_data.user_uuid)
    user_result = await session.execute(user_query)

    if not user_result.first():
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND
        )

    coworking_query = select(coworking_db).where(
        coworking_db.c.room_id == coworking_data.room_id
    )
    coworking_result = await session.execute(coworking_query)
    coworking = coworking_result.first()

    if coworking:
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT
        )

    room_query = select(room_db).where(room_db.c.id == coworking_data.room_id)
    room_result = await session.execute(room_query)
    room = room_result.first()

    if not room:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND
        )

    coworking_dict = coworking_data.model_dump()

    if coworking_dict['date'].tzinfo is not None:
        coworking_dict['date'] = coworking_dict['date'].replace(
            tzinfo=None)

    query = insert(coworking_db).values(**coworking_dict)
    await session.execute(query)
    await session.commit()

    return coworking_data


@router.get(
    "/{id}",
    response_model=CoworkingCreate
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
            status_code=HTTPStatus.NOT_FOUND
        )

    return dict(coworking._mapping)


@router.get(
    "/",
    response_model=list[CoworkingCreate]
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
            status_code=HTTPStatus.NOT_FOUND
        )

    is_creator = coworking.user_uuid == user.uuid
    has_permission = checking_for_permission(
        Permissions.coworking_delete.value, user)

    if not is_creator or not has_permission:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN
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
            Permissions.coworking_moderate.value, user)
        if not is_moderator:
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN)
    
    stmt = select(coworking_db).where(
        coworking_db.c.id == coworking_data.id
    )
    result = await session.execute(stmt)
    coworking = result.first()

    if not coworking:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND
        )

    is_creator = coworking.user_uuid == user.uuid
    has_permission = checking_for_permission(
        Permissions.coworking_edit.value, user)

    if not is_creator or not has_permission:
        raise HTTPException(
            status_code=HTTPStatus.FORBIDDEN
        )

    if coworking_data.room_id is not None:
        stmt = select(room_db).where(room_db.c.id == coworking_data.room_id)
        result = await session.execute(stmt)
        room = result.first()

        if not room:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND)
    
    if coworking_data.date is not None:
        if coworking_data.date.tzinfo is not None:
            coworking_data.date = coworking_data.date.replace(
                tzinfo=None)
    
    coworking_data = CoworkingEdit(**coworking_data.model_dump())
    
    query = update(coworking_db).where(
        coworking_db.c.id == coworking_data.id
    ).values(**coworking_data.model_dump(exclude_none=True))
    await session.execute(query)
    await session.commit()

    return coworking_data

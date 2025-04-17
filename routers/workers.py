from details import *
from config import config
from schemas import *
from auth import *
from models_ import worker as worker_db, user as user_db
from permissions import get_depend_user_with_perms, Permissions

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError
from sqlalchemy import update, select, insert, delete
from functools import partial
from action_history import add_action_to_history, HistoryActions
from schemas.user import UserToken

router = APIRouter(
    prefix="/workers",
    tags=["workers"]
)

OBJECT_TABLE = "worker"

@router.post('/', response_model=BaseTokenResponse[WorkerDBRead])
async def create_worker(
        worker: WorkerCreate,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.worker_create.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    select_statement = worker_db.select().where(worker_db.c.user_uuid == worker.user_uuid)
    row = (await session.execute(select_statement)).fetchone()

    if row is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=WORKER_ALREADY_EXISTS
        )

    try:
        insert_statement = worker_db.insert().values(**worker.model_dump())
        result = await session.execute(insert_statement)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=USER_NOT_FOUND
        )

    select_statement = worker_db.select().where(worker_db.c.user_uuid == worker.user_uuid)
    row = (await session.execute(select_statement)).fetchone()

    result = WorkerDBRead(**row._mapping)

    await add_action_to_history(ActionHistoryCreate(
        action=HistoryActions.create.value,
        subject_uuid=user.uuid,
        object_table=OBJECT_TABLE,
        object_id=result.user_uuid,
        detail=row._mapping
    ), session)

    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=result
    )

@router.get('/', response_model=list[UserReadMicrosoft])
async def get_workers(
        session: AsyncSession = Depends(get_async_session),
        current_user: UserToken | None = Depends(get_current_user_optional)
    ):

    select_statement = select(user_db).join(worker_db, worker_db.c.user_uuid == user_db.c.uuid)
    data = await session.execute(select_statement)
    rows = data.fetchall()

    users: list[UserReadMicrosoft] = []
    
    for user_ in rows:
        user_ = user_._mapping
    
        group = await get_group_by_id(id=user_['group_id'], session=session)
        if group is None:
            group = await get_default_group(session=session)

    
        microsoft_info = await get_microsoft_user_info(user_['uuid'])
        microsoft_image = await get_user_image_path(user_['uuid'])

        users.append(
            UserReadMicrosoft(
                uuid=user_['uuid'],
                is_superuser=user_['is_superuser'],
                group=group,
                microsoft= microsoft_info,
                image_path= microsoft_image
            )
        )

    return users

@router.delete(
    '/{uuid}',
    response_model=BaseTokenResponse[str]
)
async def delete_worker(
        uuid: uuid.UUID,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.worker_delete.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    select_statement = worker_db.delete().where(worker_db.c.user_uuid == uuid)

    await session.execute(select_statement)
    
    await add_action_to_history(ActionHistoryCreate(
        action=HistoryActions.delete.value,
        subject_uuid=user.uuid,
        object_table=OBJECT_TABLE,
        object_id=uuid,
        detail={'uuid': uuid}
    ), session)

    await session.commit()

    return BaseTokenResponse(
        new_token=user.new_token,
        result=OK
    )
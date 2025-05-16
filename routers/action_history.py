from details import *
from config import config
from schemas import *
from auth import *
from models_ import action_history as action_history_db
from permissions import get_depend_user_with_perms, Permissions

from fastapi import APIRouter, HTTPException, Request, Depends, Body, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from httpx_oauth.oauth2 import RefreshTokenError, GetAccessTokenError
from sqlalchemy import update, select, insert, delete, func
import math

router = APIRouter(
    prefix="/history",
    tags=["history"]
)

@router.get('/{id}', response_model=ActionHistoryRead)
async def get_action(
        id: int,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.action_history_view.value])),
        session: AsyncSession = Depends(get_async_session)
    ):

    select_statement = action_history_db.select().where(action_history_db.c.id == id)
    row = await session.execute(select_statement)
    row = row.fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
        )

    result = ActionHistoryRead(**row._mapping)
    
    return result

@router.get('/', response_model=BaseTokenPageResponse[list[ActionHistoryRead]])
async def get_all_actions(
        action: str | None = None,
        date_start: datetime | None = None,
        date_end: datetime | None = None,
        subject_uuid: uuid.UUID | None = None,
        object_table: str | None = None,
        object_id: int | str | None = None,
        limit: int = 10,
        page: int = 1,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.action_history_view.value])),
        session: AsyncSession = Depends(get_async_session)
    ):
    
    limit = min(max(1, limit), 60)
    page = max(1, page) - 1
    
    select_statement = action_history_db.select().limit(limit).offset(page * limit)
    total_pages_stmt = select(func.count(action_history_db.c.id))

    if action is not None:
        select_statement = select_statement.where(action_history_db.c.action == action)
        total_pages_stmt = total_pages_stmt.where(action_history_db.c.action == action)
    
    if date_start is not None:
        select_statement = select_statement.where(action_history_db.c.date >= date_start)
        total_pages_stmt = total_pages_stmt.where(action_history_db.c.date >= date_start)
    
    if date_end is not None:
        select_statement = select_statement.where(action_history_db.c.date <= date_end)
        total_pages_stmt = total_pages_stmt.where(action_history_db.c.date <= date_end)
    
    if subject_uuid is not None:
        select_statement = select_statement.where(action_history_db.c.subject_uuid == subject_uuid)
        total_pages_stmt = total_pages_stmt.where(action_history_db.c.subject_uuid == subject_uuid)
    
    if object_table is not None:
        select_statement = select_statement.where(action_history_db.c.object_table == object_table)
        total_pages_stmt = total_pages_stmt.where(action_history_db.c.object_table == object_table)
    
    if object_id is not None:
        object_id = str(object_id)

        select_statement = select_statement.where(action_history_db.c.object_id == object_id)
        total_pages_stmt = total_pages_stmt.where(action_history_db.c.object_id == object_id)

    rows = await session.execute(select_statement)
    rows = rows.fetchall()

    if rows is None:
        rows = []

    result = []

    for row in rows:
        result.append(ActionHistoryRead(**row._mapping))
    
    current_page = page + 1
    total_pages = await session.scalar(total_pages_stmt)
    total_pages = math.ceil(total_pages/limit)

    return BaseTokenPageResponse(
        new_token=user.new_token,
        result=result,
        current_page=current_page,
        total_page=total_pages
    )
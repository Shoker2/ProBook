from fastapi import (
    APIRouter,
    HTTPException,
    Depends
)
from ..database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from ..schemas.token import BaseTokenResponse
from http import HTTPStatus
from sqlalchemy import (
    select,
    insert,
    delete,
    update,
)
from ..auth import (
    UserToken,
    get_current_user,
)
from sqlalchemy import cast, Date
from ..permissions import Permissions, get_depend_user_with_perms
from ..details import *
from ..models_ import schedule
from ..schemas import ScheduleItem, ScheduleResponse, TemplateScheduleUpdate, CreateSchedule, TemplateResponse, TemplateItem
from datetime import datetime, timedelta, date
from ..shared import get_week_dates, validate_time_intervals


SCHEDULE_TEMPLATE = {
    1: "1000-01-01",
    2: "1000-01-02",
    3: "1000-01-03",
    4: "1000-01-04",
    5: "1000-01-05",
    6: "1000-01-06",
    7: "1000-01-07"
}


router = APIRouter(
    prefix="/schedule",
    tags=["schedule"]
)


@router.get("/template", response_model=TemplateResponse)
async def get_template(
    session: AsyncSession = Depends(get_async_session)
):
    query = select(schedule).where(
        schedule.c.date.between(
            datetime.strptime(SCHEDULE_TEMPLATE[1], '%Y-%m-%d').date(),
            datetime.strptime(SCHEDULE_TEMPLATE[7], '%Y-%m-%d').date()  
        )
    ).order_by(schedule.c.date)
    
    result = await session.execute(query)
    schedules = result.fetchall()
    
    date_to_day = {v: k for k, v in SCHEDULE_TEMPLATE.items()}
    
    schedule_items = [
        TemplateItem(
            day_number=date_to_day[row.date.strftime('%Y-%m-%d')],
            schedule_time=row.schedule_time
        )
        for row in schedules
    ]

    return TemplateResponse(result=schedule_items)


@router.put("/template", response_model=BaseTokenResponse[ScheduleResponse])
async def update_template(
    update_data: TemplateScheduleUpdate,
    current_user: UserToken = Depends(get_depend_user_with_perms([Permissions.template_change.value])),
    session: AsyncSession = Depends(get_async_session)
):
    
    try:
        validate_time_intervals(update_data.schedule_time)
    except ValueError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=str(exc)
        )
    
    if update_data.day_number not in SCHEDULE_TEMPLATE:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=INVALID_DAY_NUMBER
        )

    template_date = SCHEDULE_TEMPLATE[update_data.day_number]
    try:
        date_obj = datetime.strptime(template_date, '%Y-%m-%d').date()
    
    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=INVALID_DATE    
        )

    stmt = update(schedule).where(
        schedule.c.date == date_obj
    ).values(
        schedule_time=update_data.schedule_time
    )
    await session.execute(stmt)
    await session.commit()
    
    response = ScheduleResponse(
        result=[
            ScheduleItem(
                date=template_date,
                schedule_time=update_data.schedule_time
            )
        ]
    )
    return BaseTokenResponse(
        new_token=current_user.new_token,
        result=response
    )
    
@router.post("/", response_model=BaseTokenResponse[ScheduleResponse])
async def create_schedule(
    schedule_data: CreateSchedule,
    current_user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    
    try:
        validate_time_intervals(schedule_data.schedule_time)
    except ValueError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=str(exc),
        )
    
    date_obj = schedule_data.date
        
    query = select(schedule).where(schedule.c.date == date_obj)
    result = await session.execute(query)
    existing_schedule = result.first()
    
    if existing_schedule:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=SCHEDULE_EXISTS
        )

    stmt = insert(schedule).values(
        date=date_obj,
        schedule_time=schedule_data.schedule_time
    )
    await session.execute(stmt)
    await session.commit()

    response = ScheduleResponse(
        result = [
            ScheduleItem(
                date=schedule_data.date,
                schedule_time=schedule_data.schedule_time
            )
        ]
    )
    
    return BaseTokenResponse(
        new_token=current_user.new_token,
        result=response
    )


@router.delete("/{date}", response_model=BaseTokenResponse[ScheduleResponse])
async def delete_schedule(
    date: date, 
    current_user: UserToken = Depends(get_depend_user_with_perms(Permissions.schedule_delete.value)),
    session: AsyncSession = Depends(get_async_session)
):
    
    template_dates = set(SCHEDULE_TEMPLATE.values())
    if date.strftime("%Y-%m-%d") in template_dates:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=TEMPLATE_DELETED
        )
    
    date_obj = date
        
    query = select(schedule).where(schedule.c.date == date_obj)
    result = await session.execute(query)
    existing_schedule = result.first()
    
    if not existing_schedule:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=SCHEDULE_NOT_FOUND
        )
    
    stmt = delete(schedule).where(schedule.c.date == date_obj)
    await session.execute(stmt)
    await session.commit()
    
    response = ScheduleResponse(
        result=[
            ScheduleItem(
                date=date_obj,
                schedule_time=existing_schedule.schedule_time
            )
        ]
    )
    
    return BaseTokenResponse(
        new_token=current_user.new_token,
        result=response
    )


@router.get("/week", response_model=ScheduleResponse)
async def get_week_schedule(
    date: date | None = None,
    session: AsyncSession = Depends(get_async_session)
):
    
    target_date = datetime.now().date() if not date else date
    
    try:
        monday, sunday = get_week_dates(target_date)
    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=INVALID_DATE
        )

    template_query = select(schedule).where(
        schedule.c.date.between(
            datetime.strptime(SCHEDULE_TEMPLATE[1], '%Y-%m-%d').date(),
            datetime.strptime(SCHEDULE_TEMPLATE[7], '%Y-%m-%d').date()
        )
    ).order_by(schedule.c.date)
    template_result = await session.execute(template_query)
    template_schedule = template_result.fetchall()

    week_query = select(schedule).where(
        schedule.c.date.between(monday, sunday)
    ).order_by(schedule.c.date)
    week_result = await session.execute(week_query)
    week_schedule = week_result.fetchall()

    existing_dates = {row.date: row for row in week_schedule}

    schedule_items = []
    current_date = monday
    template_idx = 0

    while current_date <= sunday:
        if current_date in existing_dates:
            row = existing_dates[current_date]
            schedule_items.append(
                ScheduleItem(
                    date=row.date,
                    schedule_time=row.schedule_time
                )
            )
        else:
            template_row = template_schedule[template_idx]
            schedule_items.append(
                ScheduleItem(
                    date=current_date,
                    schedule_time=template_row.schedule_time
                )
            )
        current_date += timedelta(days=1)
        template_idx = (template_idx + 1) % 7

    return ScheduleResponse(result=schedule_items)

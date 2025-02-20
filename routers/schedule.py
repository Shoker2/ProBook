from fastapi import (
    APIRouter,
    HTTPException,
    Depends
)
from ..database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
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
from ..models_ import schedule
from ..schemas import ScheduleItem, ScheduleResponse, UpdateScheduleRequest
from datetime import datetime, timedelta
from ..shared import get_week_dates

router = APIRouter(
    prefix="/schedule",
    tags=["schedule"]
)


@router.get("/template", response_model=ScheduleResponse)
async def get_template(
    session: AsyncSession = Depends(get_async_session)
):
    query = select(schedule).order_by(schedule.c.date).limit(7)
    result = await session.execute(query)
    schedules = result.fetchall()
    schedule_items = [
        ScheduleItem(
            date=row.date.strftime("%d.%m.%Y"),
            schedule_time=row.schedule_time
        )
        for row in schedules
    ]

    return ScheduleResponse(response=schedule_items)


@router.put("/template", response_model=ScheduleResponse)
async def update_template(
    update_data: UpdateScheduleRequest,
    current_user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    query = select(schedule).order_by(schedule.c.date).limit(7)
    result = await session.execute(query)
    schedules = result.fetchall()

    update_date = datetime.strptime(update_data.date, '%d.%m.%Y').date()

    date_exists = False
    for row in schedules:
        if row.date == update_date:
            date_exists = True
            break

    if not date_exists:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detai="Дата не найдена среди шаблона"
        )

    stmt = update(schedule).where(
        schedule.c.date == update_date
    ).values(
        schedule_time=update_data.schedule_time
    )

    await session.execute(stmt)
    await session.commit()

    query = select(schedule).order_by(schedule.c.date).limit(7)
    result = await session.execute(query)
    schedules = result.fetchall()

    schedule_items = [
        ScheduleItem(
            date=row.date.strftime("%d.%m.%Y"),
            schedule_time=row.schedule_time
        )
        for row in schedules
    ]

    return ScheduleResponse(response=schedule_items)


@router.post("/create", response_model=UpdateScheduleRequest)
async def create_schedule(
    schedule_data: UpdateScheduleRequest,
    current_user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    new_date = datetime.strptime(schedule_data.date, '%d.%m.%Y').date()
    query = select(schedule).where(schedule.c.date == new_date)
    result = await session.execute(query)
    existing_schedule = result.first()

    if existing_schedule:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail='Расписание на эту дату уже существует'
        )
    stmt = insert(schedule).values(
        date=new_date,
        schedule_time=schedule_data.schedule_time
    )
    await session.execute(stmt)
    await session.commit()

    return schedule_data


@router.get("/template/{date}", response_model=ScheduleResponse)
async def get_schedule_by_date(
    date: str,
    session: AsyncSession = Depends(get_async_session)
):
    try:
        search_date = datetime.strptime(date, '%d.%m.%Y').date()
    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Неверный формат даты. Используйте формат DD.MM.YYYY"
        )

    query = select(schedule).where(schedule.c.date == search_date)
    result = await session.execute(query)
    schedule_row = result.first()

    if not schedule_row:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Расписание на эту дату не найдено"
        )

    schedule_items = [
        ScheduleItem(
            date=schedule_row.date.strftime("%d.%m.%Y"),
            schedule_time=schedule_row.schedule_time
        )
    ]
    return ScheduleResponse(response=schedule_items)


@router.put("/template/{date}", response_model=UpdateScheduleRequest)
async def update_schedule_time(
    schedule_data: UpdateScheduleRequest,
    current_user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    try:
        search_date = datetime.strptime(schedule_data.date, '%d.%m.%Y').date()

    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Неверный формат даты. Используйте формат DD.MM.YYYY"
        )

    query = select(schedule).where(schedule.c.date == search_date)
    result = await session.execute(query)
    existing_schedule = result.first()

    if not existing_schedule:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Расписание на эту дату не найдено"
        )

    stmt = update(schedule).where(
        schedule.c.date == search_date
    ).values(
        schedule_time=schedule_data.schedule_time
    )

    await session.execute(stmt)
    await session.commit()
    return schedule_data


@router.delete("/template/{date}", response_model=ScheduleResponse)
async def delete_schedule_by_date(
    date: str,
    current_user: UserToken = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session)
):
    try:
        delete_date = datetime.strptime(date, '%d.%m.%Y').date()
    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Неверный формат даты. Используйте формат DD.MM.YYYY"
        )

    query = select(schedule).where(schedule.c.date == delete_date)
    result = await session.execute(query)
    existing_schedule = result.first()

    if not existing_schedule:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Расписание на эту дату не найдено"
        )

    stmt = delete(schedule).where(schedule.c.date == delete_date)
    await session.execute(stmt)
    await session.commit()

    schedule_items = [
        ScheduleItem(
            date=existing_schedule.date.strftime("%d.%m.%Y"),
            schedule_time=existing_schedule.schedule_time
        )
    ]
    return ScheduleResponse(response=schedule_items)


@router.get("/week/{date}", response_model=ScheduleResponse)
async def get_week_schedule(
    date: str,
    session: AsyncSession = Depends(get_async_session)
):
    try:
        searching_date = datetime.strptime(date, '%d.%m.%Y').date()
    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail="Неверный формат даты. Используйте формат DD.MM.YYYY"
        )

    monday, sunday = get_week_dates(date)

    template_query = select(schedule).order_by(schedule.c.date).limit(7)
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
                    date=row.date.strftime("%d.%m.%Y"),
                    schedule_time=row.schedule_time
                )
            )
        else:
            template_row = template_schedule[template_idx]
            schedule_items.append(
                ScheduleItem(
                    date=current_date.strftime("%d.%m.%Y"),
                    schedule_time=template_row.schedule_time
                )
            )
        current_date += timedelta(days=1)
        template_idx = (template_idx + 1) % 7

    return ScheduleResponse(response=schedule_items)

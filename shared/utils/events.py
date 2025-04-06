import logging
from sqlalchemy import func
from sqlalchemy import (
	insert,
	select,
	or_,
	and_,
	func
)
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException, status

from schemas.event import RepeatEventUpdate, Status, Repeatability
from models_ import event as event_db
from details import ROOM_IS_ALREADY

TIMEDELTA = timedelta(days=40)

repeatability = {
	Repeatability.daily.value: relativedelta(days=1),
	Repeatability.weekly.value: relativedelta(weeks=1),
	Repeatability.monthly.value: relativedelta(months=1),
	Repeatability.yearly.value: relativedelta(year=1)
}


def get_max_date():
	return datetime.now() + TIMEDELTA


async def get_repeat_events(session: AsyncSession) -> list[RepeatEventUpdate]:
	subq = (
		select(
			event_db.c.event_base_id,
			func.max(event_db.c.date_start).label("date"),
		)
		.group_by(event_db.c.event_base_id)
		.subquery()
	)

	query = (
		select(event_db)
		.join(
			subq,
			and_(
				event_db.c.event_base_id == subq.c.event_base_id,
				event_db.c.date_start == subq.c.date
			)
		)
		.where(
			event_db.c.repeat.in_(repeatability.keys()),
			event_db.c.status == Status.approve.value
		)
	)

	result = await session.execute(query)
	events = [RepeatEventUpdate(**(event._mapping)) for event in result.all()]
	
	return events


async def check_overlapping(event_room_id: int, event_date_start: datetime, event_date_end: datetime, session: AsyncSession):
	overlapping_events_query = select(event_db).where(
			and_(
				event_db.c.status == Status.approve.value,
				event_db.c.room_id == event_room_id,
				func.date(event_db.c.date_start) == func.date(
					event_date_start),
				or_(
					and_(
						event_db.c.date_start <= event_date_start,
						event_db.c.date_end > event_date_start
					),
					and_(
						event_db.c.date_start < event_date_end,
						event_db.c.date_end >= event_date_end
					),
					and_(
						event_db.c.date_start >= event_date_start,
						event_db.c.date_end <= event_date_end
					)
				)
			)
		)
		
	result = await session.execute(overlapping_events_query)
	return result.first() is None


async def create_events_before(event: RepeatEventUpdate, date_max: datetime, session: AsyncSession, create_current = False):
	if event.repeat not in Repeatability._value2member_map_ or event.repeat is Repeatability.NO.value:
		return
	
	while True:
		if not create_current:
			event.date_start = event.date_start + repeatability[event.repeat]
			event.date_end = event.date_end + repeatability[event.repeat]

		if event.date_start > date_max:
			break

		room_in_use = await check_overlapping(event.room_id, event.date_start, event.date_end, session)
		if not room_in_use:
			raise HTTPException(
				status_code=status.HTTP_409_CONFLICT,
				detail=ROOM_IS_ALREADY
			)
		
		stmt = insert(event_db).values(**event.model_dump())
		await session.execute(stmt)

		if create_current:
			event.date_start = event.date_start + repeatability[event.repeat]
			event.date_end = event.date_end + repeatability[event.repeat]
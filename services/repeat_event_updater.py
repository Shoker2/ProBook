import logging
import asyncio
from sqlalchemy import func
from sqlalchemy import select, func, and_, insert
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from database import get_async_session
from schemas.event import EventRead
from models_ import event as event_db

TIMEDELTA = timedelta(days=40)

repeatability = {
	'daily': relativedelta(days=1),
	'weekly': relativedelta(weeks=1),
	'monthly': relativedelta(months=1),
	'yearly': relativedelta(year=1)
}

class RepeatEventUpdate(EventRead):
	id: SkipJsonSchema[int] = Field(exclude=True)
	event_base_id: int

async def repeat_event_updater():
	while True:
		async_generator = get_async_session()
		session = await anext(async_generator)

		subq = (
			select(
				event_db.c.event_base_id,
				func.max(event_db.c.date_start).label("date")
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
			.where(event_db.c.repeat.in_(repeatability.keys()))
		)

		result = await session.execute(query)
		events = [RepeatEventUpdate(**(event._mapping)) for event in result.all()]

		date_now = datetime.now()
		date_max = date_now + TIMEDELTA

		for event in events:
			while True:
				event.date_start = event.date_start + repeatability[event.repeat]
				event.date_end = event.date_end + repeatability[event.repeat]

				if event.date_start > date_max:
					break
				
				stmt = insert(event_db).values(**event.model_dump())
				await session.execute(stmt)

		await session.commit()
		await asyncio.sleep(24 * 3600)
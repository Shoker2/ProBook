import asyncio
from fastapi import HTTPException
import logging

from shared.utils.events import get_max_date, get_repeat_events, create_events_before
from database import get_async_session


async def repeat_event_updater():
	while True:
		async_generator = get_async_session()
		session = await anext(async_generator)

		date_max = get_max_date()
		events = await get_repeat_events(session)

		for event in events:
			try:
				await create_events_before(event, date_max, session)
			except HTTPException:
				pass

		await session.commit()
		await asyncio.sleep(24 * 3600)
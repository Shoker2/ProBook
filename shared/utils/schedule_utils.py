from datetime import datetime, timedelta
import re
from datetime import date
from database import async_session_maker
from sqlalchemy import (
    select,
    insert
)
from models_ import schedule, room as room_db
from mock_data import schedule_template

def get_week_dates(date_obj: date) -> tuple[date, date]:
    current_weekday = date_obj.weekday()

    monday = date_obj - timedelta(days=current_weekday)
    sunday = monday + timedelta(days=6)

    return monday, sunday


def validate_time_intervals(schedule_times: list[str]) -> None:
    pattern = re.compile(r"^([0-1]?\d|2[0-3]):[0-5]\d-([0-1]?\d|2[0-3]):[0-5]\d$")
    intervals: list[tuple[int, int, str]] = []

    for interval in schedule_times:
        if not pattern.match(interval):
            raise ValueError(f"Invalid time interval format: {interval}")
        
        start_str, end_str = interval.split('-')
        start = int(start_str[:2]) * 60 + int(start_str[3:])
        end   = int(end_str[:2])   * 60 + int(end_str[3:])
        if start >= end:
            raise ValueError(f"Start time must be before end time: {interval}")
        intervals.append((start, end, interval))

    intervals.sort(key=lambda x: x[0])

    for (prev_start, prev_end, prev_str), (curr_start, curr_end, curr_str) in zip(intervals, intervals[1:]):
        if curr_start < prev_end:
            raise ValueError(f"Overlapping intervals: {prev_str} and {curr_str}")


async def schedule_template_fix(session):
    query = select(room_db.c.id)
    room_id_result = await session.execute(query)
    
    for room_id in room_id_result.fetchall():
        room_id = room_id[0]

        for date, schedule_times in schedule_template.items():

            date_obj = datetime.strptime(
                date, '%d.%m.%Y').date()

            query = select(schedule).where(date_obj == schedule.c.date, schedule.c.room_id == room_id)
            result = await session.execute(query)
            schedule_row = result.first()
            if not schedule_row:
                stmt = insert(schedule).values(
                    date=date_obj,
                    schedule_time=schedule_times,
                    room_id=room_id
                )
                await session.execute(stmt)
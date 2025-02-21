from datetime import datetime, timedelta
import re
from datetime import date

def get_week_dates(date_obj: date) -> tuple[date, date]:
    current_weekday = date_obj.weekday()

    monday = date_obj - timedelta(days=current_weekday)
    sunday = monday + timedelta(days=6)

    return monday, sunday

def validate_time_intervals(schedule_times: list[str]) -> None:
    pattern = re.compile(r"^([0-1]?\d|2[0-3]):[0-5]\d-([0-1]?\d|2[0-3]):[0-5]\d$")
    for interval in schedule_times:
        if not pattern.match(interval):
            raise ValueError(f"Invalid time interval format: {interval}")

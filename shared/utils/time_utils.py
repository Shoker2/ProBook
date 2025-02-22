from datetime import datetime


def time_manager(date_start: datetime, date_end: datetime) -> bool:
    if date_start.date() != date_end.date():
        return False

    if date_start >= date_end:
        return False

    return True

from datetime import datetime, timedelta


def get_week_dates(date_str: str) -> tuple[datetime.date, datetime.date]:
    current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    current_weekday = current_date.weekday()

    monday = current_date - timedelta(days=current_weekday)
    sunday = monday + timedelta(days=6)

    return monday, sunday

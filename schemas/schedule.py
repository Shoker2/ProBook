from pydantic import BaseModel, validator
from typing import List
from datetime import datetime


class ScheduleItem(BaseModel):
    date: str
    schedule_time: List[str]


class ScheduleResponse(BaseModel):
    response: List[ScheduleItem]


class UpdateScheduleRequest(BaseModel):
    date: str
    schedule_time: List[str]

    @validator('date')
    def validate_date(cls, value):
        try:
            datetime.strptime(value, '%d.%m.%Y')
            return value
        except ValueError:
            raise ValueError('Дата должна быть в формате DD.MM.YYYY')

    @validator('schedule_time')
    def validate_schedule_time(cls, value):
        if not value:
            raise ValueError('Поле со временем не может быть пустым')

        validated_slots = []

        for time_range in value:
            time_slots = [t.strip() for t in time_range.split(',')]

            for time_slot in time_slots:

                try:
                    start, end = time_slot.split('-')
                    start_time = datetime.strptime(start.strip(), '%H:%M')
                    end_time = datetime.strptime(end.strip(), '%H:%M')

                    if end_time <= start_time:
                        raise ValueError(
                            f'Конечное время {end} должно быть позже чем стартовое {start}')

                    validated_slots.append(f"{start.strip()}-{end.strip()}")
                except ValueError:
                    raise ValueError("Время должно быть в формате HH:MM-HH:MM")

        return validated_slots

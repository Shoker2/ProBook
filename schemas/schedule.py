from pydantic import BaseModel, validator
from typing import List
from datetime import datetime, date
import re

class ScheduleItem(BaseModel):
    date: date
    schedule_time: List[str]

class TemplateItem(BaseModel):
    day_number: int
    schedule_time: List[str]


class TemplateResponse(BaseModel):
    result: List[TemplateItem]

class ScheduleResponse(BaseModel):
    result: List[ScheduleItem]


class TemplateScheduleUpdate(BaseModel):
    day_number: int
    schedule_time: List[str]



class CreateSchedule(BaseModel):
    date: date
    schedule_time: List[str]

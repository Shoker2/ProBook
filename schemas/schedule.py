from pydantic import BaseModel, validator
from typing import List
from datetime import datetime
import re

class ScheduleItem(BaseModel):
    date: str
    schedule_time: List[str]


class ScheduleResponse(BaseModel):
    result: List[ScheduleItem]


class TemplateScheduleUpdate(BaseModel):
    day_number: int
    schedule_time: List[str]



class CreateSchedule(BaseModel):
    date: str
    schedule_time: List[str]

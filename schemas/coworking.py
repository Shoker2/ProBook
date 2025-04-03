from pydantic import BaseModel, Field
from datetime import datetime, date
import uuid
from typing import List
from enum import Enum

class Status(Enum):
    not_moderated = 0
    approve = 1
    reject = 2


class CoworkingCreate(BaseModel):
    room_id: int
    info_for_moderator: str
    date_start: datetime
    date_end: datetime
    needable_items: List[int] | None = []
    status: int | None = Field(Status.not_moderated.value, gt=-1, le=2)


class CoworkingEdit(BaseModel):

    id: int
    room_id: int | None = None
    status: int | None = Field(Status.not_moderated.value, gt=-1, le=2)
    info_for_moderator: str | None = None
    date_start: datetime | None = None
    date_end: datetime | None = None
    cause_cancel: str | None = None
    needable_items: List[int] | None = None


class ReadItem(BaseModel):
    id: int
    room_id: int
    user_uuid: uuid.UUID
    info_for_moderator: str
    status: int
    needable_items: List[int]
    cause_cancel: str
    date_start: datetime
    date_end: datetime


class CoworkingRead(CoworkingEdit):
    user_uuid: uuid.UUID



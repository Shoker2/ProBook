from pydantic import BaseModel
from datetime import datetime, date
import uuid
from typing import List


class CoworkingCreate(BaseModel):
    room_id: int
    info_for_moderator: str
    date_start: datetime
    date_end: datetime
    needable_items: List[int] | None = None
    moderated: bool | None = None


class CoworkingEdit(BaseModel):

    id: int
    room_id: int | None = None
    moderated: bool | None = None
    info_for_moderator: str | None = None
    date_start: datetime | None = None
    date_end: datetime | None = None
    needable_items: List[int] | None = None


class ReadItem(BaseModel):
    id: int
    room_id: int
    user_uuid: uuid.UUID
    info_for_moderator: str
    moderated: bool
    needable_items: List[int]
    date_start: datetime
    date_end: datetime


class CoworkingRead(CoworkingEdit):
    user_uuid: uuid.UUID



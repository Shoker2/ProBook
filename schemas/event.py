from pydantic import BaseModel
from datetime import datetime, date
from typing import List, Optional
import uuid


class EventCreate(BaseModel):
    room_id: int
    info_for_moderator: str
    title: str
    description: str
    img: str | None = None
    repeat: str
    date_start: datetime
    date_end: datetime
    needable_items: List[int] | None = None


class EventEdit(BaseModel):

    id: int
    room_id: int | None = None
    info_for_moderator: str | None = None
    title: str | None = None
    description: str | None = None
    img: str | None = None
    repeat: str | None = None
    date_start: datetime | None = None
    date_end: datetime | None = None
    moderated: bool | None = None
    needable_items: List[int] | None = None


class EventRead(EventEdit):
    user_uuid: uuid.UUID
    participants: List[uuid.UUID]


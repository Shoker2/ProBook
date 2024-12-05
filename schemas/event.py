from pydantic import BaseModel
from datetime import datetime
from typing import List
import uuid

class EventCreate(BaseModel):

    room_id: int
    user_uuid: uuid.UUID
    info_for_moderator: str
    title: str
    description: str
    participants: List[uuid.UUID]
    img: str | None = None
    repeat: str
    date_start: datetime
    date_end: datetime
    moderated: bool = False


class EventEdit(BaseModel):
    
    id: int
    room_id: int | None = None
    info_for_moderator: str | None = None
    title: str | None = None
    description: str | None = None
    participants: List[uuid.UUID] | None = None
    img: str | None = None
    repeat: str | None = None
    date_start: datetime | None = None
    date_end: datetime | None = None
    moderated: bool | None = None

class EventRead(EventEdit):
    user_uuid: uuid.UUID
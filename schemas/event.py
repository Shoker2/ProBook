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
    
class InternalServerError(BaseModel):
    message: str


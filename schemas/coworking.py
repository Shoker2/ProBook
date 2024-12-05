from pydantic import BaseModel
from datetime import datetime
from typing import List
import uuid



class CoworkingCreate(BaseModel):
    
    room_id : int
    user_uuid: uuid.UUID
    info_for_moderator: str
    date: datetime
    moderated: bool = False

class CoworkingEdit(BaseModel):
    
    id: int
    room_id: int | None = None
    info_for_moderator: str | None = None
    date: datetime | None = None
    moderated: bool | None = None

class CoworkingRead(CoworkingEdit):
    user_uuid: uuid.UUID

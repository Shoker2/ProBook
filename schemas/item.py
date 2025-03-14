from pydantic import BaseModel

class ItemCreate(BaseModel):
    name: str
    room_id: int | None = None

class ItemRead(BaseModel):
    id: int
    name: str
    room_id: int | None = None

class ItemUpdate(BaseModel):
    id: int
    name: str | None = None
    room_id: int | None = None
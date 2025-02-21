from pydantic import BaseModel

class RoomCreate(BaseModel):
    name: str
    capacity: int

class RoomRead(BaseModel):
    id: int
    name: str
    capacity: int

class RoomUpdate(BaseModel):
    id: int
    name: str | None = None
    capacity: int | None = None
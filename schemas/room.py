from pydantic import BaseModel

class RoomCreate(BaseModel):
    name: str
    capacity: int
    img: str | None = None
    description: str | None = ""

class RoomRead(BaseModel):
    id: int
    name: str
    capacity: int
    img: str | None
    description: str

class RoomUpdate(BaseModel):
    id: int
    name: str | None = None
    capacity: int | None = None
    img: str | None = None
    description: str | None = None
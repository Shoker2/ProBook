from pydantic import BaseModel

class ItemCreate(BaseModel):
    name: str

class ItemRead(BaseModel):
    id: int
    name: str

class ItemUpdate(BaseModel):
    id: int
    name: str | None = None
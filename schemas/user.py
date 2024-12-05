from pydantic import BaseModel
import uuid

class GroupCreate(BaseModel):
    name: str
    permissions: list[str] = []

class GroupRead(BaseModel):
    id: int
    name: str
    permissions: list[str]
    is_default: bool

class GroupUpdate(BaseModel):
    id: int
    name: str | None = None
    permissions: list[str] | None = None
    is_default: bool = None

class UserCreate(BaseModel):
    uuid: uuid.UUID
    is_superuser: bool = False

class UserRead(UserCreate):
    group: GroupRead | None

class UserToken(UserRead):
    microsoft_access_token: str
    microsoft_refresh_token: str
    new_token: str | None
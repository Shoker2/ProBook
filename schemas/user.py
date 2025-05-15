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
    name: str | None
    is_superuser: bool = False

class UserRead(UserCreate):
    group: GroupRead | None

class UserReadMicrosoft(UserRead):
    microsoft: dict | None = None
    image_path: str | None = None

class UserToken(UserRead):
    microsoft_access_token: str
    microsoft_refresh_token: str
    new_token: str | None

class UserGroup(BaseModel):
    user_uuid: uuid.UUID
    group_id: int | None = None


class WorkerDBRead(BaseModel):
    user_uuid: uuid.UUID

class WorkerCreate(BaseModel):
    user_uuid: uuid.UUID
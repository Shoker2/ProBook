from pydantic import BaseModel, Field
from typing import Optional, List, TypeVar, Generic
from pydantic.networks import EmailStr
from datetime import datetime
import uuid

T = TypeVar("T")

class UserCreate(BaseModel):
    uuid: uuid.UUID
    is_superuser: bool = False

class UserRead(UserCreate):
    pass

class UserToken(UserRead):
    microsoft_access_token: str
    microsoft_refresh_token: str
    new_token: str | None

class GetToken(BaseModel):
    token: str

class GetAuthorizationUrl(BaseModel):
    authorization_url: str

class BaseTokenResponse(BaseModel, Generic[T]):
    new_token: str | None = Field(examples=["YOUR_TOKEN"])
    result: T
from pydantic import BaseModel, Field
from typing import TypeVar, Generic

T = TypeVar("T")

class GetToken(BaseModel):
    token: str

class GetAuthorizationUrl(BaseModel):
    authorization_url: str

class BaseTokenResponse(BaseModel, Generic[T]):
    new_token: str | None = Field(examples=["YOUR_TOKEN"])
    result: T


class BasePageResponse(BaseModel, Generic[T]):
    current_page: int
    total_page: int
    result: T

class BaseTokenPageResponse(BaseTokenResponse):
    current_page: int
    total_page: int
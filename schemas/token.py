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
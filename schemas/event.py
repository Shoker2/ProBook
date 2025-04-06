from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema
from datetime import datetime, date
from typing import List, Optional
import uuid
from enum import Enum

class Status(Enum):
	not_moderated = 0
	approve = 1
	reject = 2

class EventCreate(BaseModel):
	room_id: int
	info_for_moderator: str
	title: str
	description: str
	img: str | None = None
	repeat: str
	date_start: datetime
	date_end: datetime
	needable_items: List[int] | None = []
	status: int | None = Field(Status.not_moderated.value, gt=-1, le=2)


class EventEdit(BaseModel):

	id: int
	room_id: int | None = None
	info_for_moderator: str | None = None
	title: str | None = None
	description: str | None = None
	img: str | None = None
	repeat: str | None = None
	date_start: datetime | None = None
	date_end: datetime | None = None
	status: int | None = Field(Status.not_moderated.value, gt=-1, le=2)
	cause_cancel: str | None = None
	needable_items: List[int] | None = None


class EventRead(EventEdit):
	user_uuid: uuid.UUID
	cause_cancel: str
	participants: List[uuid.UUID]


class RepeatEventUpdate(EventEdit):
	id: SkipJsonSchema[int] = Field(exclude=True)
	event_base_id: int
	user_uuid: uuid.UUID
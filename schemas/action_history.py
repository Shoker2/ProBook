from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from pydantic.json_schema import SkipJsonSchema

class ActionHistoryDetailUpdate(BaseModel):
    old: dict = {}
    new: dict = {}

    empty: SkipJsonSchema[bool] = Field(exclude=True, default=True)

    def update(self, selection: str, old, new):
        if old != new:
            self.old[selection] = old
            self.new[selection] = new
            self.empty = False


class ActionHistoryRead(BaseModel):
    id: int
    action: str
    date: datetime
    subject_uuid: UUID
    object_table: str
    object_id: int | UUID | str | None = None
    detail: dict | ActionHistoryDetailUpdate

class ActionHistoryCreate(BaseModel):
    action: str
    subject_uuid: UUID
    object_table: str
    object_id: int | UUID | str | None = None
    detail: dict | ActionHistoryDetailUpdate
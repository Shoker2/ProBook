from models_ import action_history as action_history_db
from schemas import ActionHistoryCreate

from sqlalchemy.ext.asyncio import AsyncSession
import json
from uuid import UUID
from enum import Enum

class HistoryActions(Enum):
    create = "create"
    update = "update"
    delete = "delete"


class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return obj.hex
        return json.JSONEncoder.default(self, obj)

async def add_action_to_history(action: ActionHistoryCreate, session: AsyncSession):
    action.object_id = str(action.object_id)
    stmt = action_history_db.insert().values(**json.loads(json.dumps(action.model_dump(), cls=UUIDEncoder)))
    await session.execute(stmt)
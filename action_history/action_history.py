from models_ import action_history as action_history_db
from schemas import ActionHistoryCreate

from sqlalchemy.ext.asyncio import AsyncSession
import json
from uuid import UUID
from enum import Enum
from datetime import date, datetime

class HistoryActions(Enum):
    create = "create"
    update = "update"
    delete = "delete"

class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        
        if isinstance(obj, UUID):
            return obj.hex
        
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        
        if isinstance(obj, Enum):
            return obj.value
        
        return super().default(obj)

async def add_action_to_history(action: ActionHistoryCreate, session: AsyncSession):
    action.object_id = str(action.object_id)

    raw = action.model_dump()
    payload = json.loads(json.dumps(raw, cls=UUIDEncoder))

    stmt = action_history_db.insert().values(**payload)
    await session.execute(stmt)

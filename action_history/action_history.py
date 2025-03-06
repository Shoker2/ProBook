from ..models_ import action_history as action_history_db
from ..schemas import ActionHistoryCreate
from sqlalchemy.ext.asyncio import AsyncSession

from enum import Enum

class HistoryActions(Enum):
    create = "create"
    update = "update"
    delete = "delete"

async def add_action_to_history(action: ActionHistoryCreate, session: AsyncSession):
    action.object_id = str(action.object_id)
    stmt = action_history_db.insert().values(**action.model_dump())
    await session.execute(stmt)
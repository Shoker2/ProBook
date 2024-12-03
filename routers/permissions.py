from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from functools import partial
from sqlalchemy import update, select, insert, delete

from ..details import *
from ..config import config
from ..schemas import *
from ..database import redis_db, get_async_session, create_group as create_group_db, delete_group as delete_group_db
from ..auth import *
from ..models_ import group as group_db
from ..permissions import get_depend_user_with_perms, Permissions, PERMISSION_DESC


router = APIRouter(
    prefix="/permissions",
    tags=["permissions"]
)

@router.get('/{name}', response_model=BaseTokenResponse[PermissionModel])
async def get_group(
        name: str,
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.group_view.value]))
    ):

    if name not in [e.value for e in Permissions]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=PERMISSION_IS_NOT_EXIST
        )

    return BaseTokenResponse(
        new_token=user.new_token,
        result=PermissionModel(
            name=name,
            description=PERMISSION_DESC.get(name, None)
        )
    )

@router.get('/', response_model=BaseTokenResponse[list[PermissionModel]])
async def get_all_groups(
        user: UserToken = Depends(get_depend_user_with_perms([Permissions.group_edit.value])),
    ):

    permissions: list[PermissionModel] = []
    for perm in [e.value for e in Permissions]:
        permissions.append(
            PermissionModel(
                name=perm,
                description=PERMISSION_DESC.get(perm, None)
            )
        )


    return BaseTokenResponse(
        new_token=user.new_token,
        result=permissions
    )
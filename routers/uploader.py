from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile,
    Depends
)
from schemas.token import BaseTokenResponse
from fastapi.params import File
import os
import hmac
import hashlib
from auth import get_current_user
from schemas.uploader import (
    ImgSave,
    ImgDelete
)
from sqlalchemy import (
    insert,
    select,
    delete,
    update,
    cast,
    or_,
    and_,
    literal_column,
    func,
    Integer
)

from models_ import (
    event as event_db,
    room as room_db
)

from auth import UserToken
from datetime import datetime
from config import config
from permissions import Permissions, get_depend_user_with_perms
import logging
from action_history import add_action_to_history, HistoryActions
from schemas import ActionHistoryCreate
from database import get_async_session
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(
    prefix="/img",
    tags=["img"]
)

OBJECT_TABLE = "image"
STATIC_IMAGES_DIR = "./static/img"
ALGORITHM = "HS256"
SECRET = config['Miscellaneous']['secret']


@router.post("/", response_model=BaseTokenResponse[ImgSave])
async def upload(
    current_user: UserToken = Depends(get_depend_user_with_perms([Permissions.image_upload.value])),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session)
):
    data_to_hash = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{current_user.uuid}"
    hash_name = hmac.new(SECRET.encode(), data_to_hash.encode(), hashlib.sha256).hexdigest()

    type_of_image = ".png" 
    if file.filename.endswith(".png"):
        type_of_image = ".png"
    elif file.filename.endswith(".jpg") or file.filename.endswith(".jpeg"):
        type_of_image = ".jpeg"

    file_name = str(hash_name) + type_of_image  # сохраняем в переменную
    new_path = os.path.join(STATIC_IMAGES_DIR, file_name)

    try:
        with open(new_path, "wb") as buffer:
            buffer.write(await file.read())
    except Exception as e:
        logging.exception(e)
        raise HTTPException(status_code=500, detail="Failed to save file")

    res = ImgSave(
        date=datetime.utcnow(),
        file_name=file_name,  
        content_type=file.content_type
    )
    
    await add_action_to_history(
        ActionHistoryCreate(
            action=HistoryActions.create.value,
            subject_uuid=current_user.uuid,
            object_table=OBJECT_TABLE,
            object_id=file_name,
            detail={
                "file_name": file_name,
                "content_type": file.content_type,
                "original_filename": file.filename
            }
        ),
        session
    )
    
    await session.commit()
    
    return BaseTokenResponse(
        new_token=current_user.new_token,
        result=res
    )



@router.delete("/{file_name}", response_model=BaseTokenResponse[ImgDelete])
async def delete_file(
        file_name: str,
        current_user: UserToken = Depends(get_depend_user_with_perms([Permissions.image_delete.value])),
        session: AsyncSession = Depends(get_async_session)
):
    files_list = os.listdir(STATIC_IMAGES_DIR)

    if file_name in files_list:

        file_path = os.path.join(STATIC_IMAGES_DIR, file_name)

        os.remove(file_path)

        res = ImgDelete(
            date=datetime.utcnow(),
            file_name=file_name,
            message="File successfully deleted"
        )

        action_detail = {"file_name": file_name}

        stmt = update(event_db).where(event_db.c.img == file_name).returning(event_db.c.id).values(img=None)
        events = await session.execute(stmt)
        events = events.scalars().all()
        if len(events) > 0:
            action_detail["events"] = events

        stmt = update(room_db).where(room_db.c.img == file_name).returning(room_db.c.id).values(img=None)
        rooms = await session.execute(stmt)
        rooms = rooms.scalars().all()
        if len(rooms) > 0:
            action_detail["rooms"] = rooms

        await add_action_to_history(
            ActionHistoryCreate(
                action=HistoryActions.delete.value,
                subject_uuid=current_user.uuid,
                object_table=OBJECT_TABLE,
                object_id=file_name,
                detail=action_detail
            ),
            session
        )
        
        await session.commit()

        return BaseTokenResponse(
            new_token=current_user.new_token,
            result=res
        )
    else:
        raise HTTPException(status_code=404, detail="File doesn't exist")
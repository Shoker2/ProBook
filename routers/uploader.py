from fastapi import (
    APIRouter,
    HTTPException,
    UploadFile
)
from ..schemas.token import BaseTokenResponse
from fastapi.params import Depends, File
import os
import hmac
import hashlib
from ..auth import get_current_user
from ..schemas.uploader import (
    ImgSave,
    ImgDelete)
from ..auth import UserToken
from datetime import datetime
from ..config import config
router = APIRouter(
    prefix="/uploader",
    tags=["uploader"]
)
from ..permissions import Permissions, get_depend_user_with_perms

static_dir = "./static"
ALGORITHM = "HS256"
SECRET = config['Miscellaneous']['secret']


@router.post("/upload", response_model=BaseTokenResponse[ImgSave])
async def upload(
    current_user: UserToken = Depends(get_depend_user_with_perms([Permissions.file_upload.value])),
    file: UploadFile = File(...)
):
    data_to_hash = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{current_user.uuid}"
    hash_name = hmac.new(SECRET.encode(), data_to_hash.encode(), hashlib.sha256).hexdigest()

    type_of_image = ".png" 
    if file.filename.endswith(".png"):
        type_of_image = ".png"
    elif file.filename.endswith(".jpg") or file.filename.endswith(".jpeg"):
        type_of_image = ".jpeg"

    file_name = f"{hash_name}"  # сохраняем в переменную
    new_path = f"static/{file_name}"

    try:
        with open(new_path, "wb") as buffer:
            buffer.write(await file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to save file")

    res = ImgSave(
        date=datetime.utcnow(),
        file_name=file_name,  # используем ту же переменную
        content_type=file.content_type + {type_of_image}
    )
    
    return BaseTokenResponse(
        new_token=current_user.new_token,
        result=res
    )



@router.delete("/{file_hash_name}", response_model=BaseTokenResponse[ImgDelete])
async def delete_file(
        file_hash_name: str,
        current_user: UserToken = Depends(get_depend_user_with_perms([Permissions.file_delete.value]))
):
    files_list = os.listdir(static_dir)

    if file_hash_name in files_list:

        file_path = os.path.join(static_dir, file_hash_name)

        os.remove(file_path)

        res = ImgDelete(
            date=datetime.utcnow(),
            file_name=file_hash_name,
            message="File successfully deleted"
        )
        return BaseTokenResponse(
            new_token=current_user.new_token,
            result=res
        )
    else:
        raise HTTPException(status_code=404, detail="File doesn't exist")



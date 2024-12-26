from pydantic import BaseModel
from datetime import datetime

class ImgSave(BaseModel):
    date: datetime
    file_name: str
    content_type: str


class ImgDelete(BaseModel):
    date: datetime
    file_name: str
    message: str
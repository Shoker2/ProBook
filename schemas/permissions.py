from pydantic import BaseModel

class PermissionModel(BaseModel):
    name: str
    description: str | None = None

    def __str__(self):
        return self.name
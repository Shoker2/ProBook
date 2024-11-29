from enum import Enum

class Permissions(Enum):
    group_create = "group.create"
    group_delete = "group.delete"
    group_edit = "group.edit"
    group_view = "group.view"
    
    event_delete = "event_delete"
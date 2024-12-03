from enum import Enum

class Permissions(Enum):
    group_create = "group.create"
    group_delete = "group.delete"
    group_edit = "group.edit"
    group_view = "group.view"
    
    event_delete = "event.delete"
    event_edit = "event.edit"
    event_moderate = "event.moderate"
    
    coworking_delete = "coworking.delete"
    coworking_edit = "coworking.edit"
    coworking_moderate = "coworking.moderate"

PERMISSION_DESC = {
    Permissions.group_create.value: "Creation group",
    Permissions.group_delete.value: "Delete group",
}
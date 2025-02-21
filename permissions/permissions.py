from enum import Enum

class Permissions(Enum):
    groups_add_user = "groups.add_user"

    groups_create = "groups.create"
    groups_delete = "groups.delete"
    groups_edit = "groups.edit"
    groups_view = "groups.view"
    
    events_delete = "event.delete"
    events_edit = "event.edit"
    events_moderate = "event.moderate"
    
    coworkings_delete = "coworking.delete"
    coworkings_edit = "coworking.edit"
    coworkings_moderate = "coworking.moderate"

    permissions_view = "permissions.view"

    items_create = "items.create"
    items_delete = "items.delete"
    items_edit = "items.edit"
    items_view = "items.view"

    rooms_create = "rooms.create"
    rooms_delete = "rooms.delete"
    rooms_edit = "rooms.edit"

    image_upload = "image.upload"
    image_delete = "image.delete"

PERMISSION_DESC = {
    Permissions.groups_create.value: "Creation group",
    Permissions.groups_delete.value: "Delete group",
}
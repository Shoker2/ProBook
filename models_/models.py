from sqlalchemy import MetaData, Table, Integer, Column, String, TIMESTAMP, ARRAY, Boolean, CheckConstraint, Float, ForeignKey, UUID, TEXT
from datetime import datetime

meta_data = MetaData()

group = Table(
    "group",
    meta_data,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("permissions", ARRAY(String), nullable=False),
    Column("is_default", Boolean, server_default="false", nullable=False),
)

user = Table(
    "user",
    meta_data,
    Column("uuid", UUID, nullable=False, index=True, primary_key=True),
    Column("is_superuser", Boolean, server_default="false", nullable=False),
    Column("group_id", ForeignKey("group.id"), nullable=True)
)


room = Table(
    "room",
    meta_data,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("capacity", Integer, nullable=False)
)

personal_reservation = Table(
    "personal_reservation",
    meta_data,
    Column("id", Integer, primary_key=True),
    Column("room_id", ForeignKey("room.id"), nullable=False),
    Column("user_uuid", ForeignKey("user.uuid"), nullable=False),
    Column("info_for_moderator", TEXT, nullable=False),
    Column("date", TIMESTAMP, nullable=False),
    Column("moderated", Boolean, nullable=False, server_default="false")
)

event = Table(
    "event",
    meta_data,
    Column("id", Integer, primary_key=True),
    Column("room_id", ForeignKey("room.id"), nullable=False),
    Column("user_uuid", ForeignKey("user.uuid"), nullable=False),
    Column("info_for_moderator", TEXT, nullable=False),

    Column("title", String, nullable=False),
    Column("description", TEXT, nullable=False),
    Column("participants", ARRAY(UUID), nullable=False, server_default="{}"),
    Column("img", String),
    Column("repeat", String),  # No (None) | Every: day, week, two week

    Column("date_start", TIMESTAMP, nullable=False),
    Column("date_end", TIMESTAMP, nullable=False),
    Column("moderated", Boolean, nullable=False, server_default="false")
)

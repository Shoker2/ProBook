from sqlalchemy import (
    MetaData,
    Table,
    Integer,
    Column,
    String,
    TIMESTAMP,
    ARRAY,
    Boolean,
    SMALLINT,
    CheckConstraint,
    Float,
    Sequence,
    ForeignKey,
    UUID,
    TEXT,
    DATE,
    JSON,
)
from datetime import datetime
meta_data = MetaData()

EVENT_BASE_ID_SEQ = Sequence('event_base_id_seq', metadata=meta_data)

group = Table(
    "group",
    meta_data,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("permissions", ARRAY(String), nullable=False),
    Column("is_default", Boolean, server_default="false", nullable=False),
)

item = Table(
    "item",
    meta_data,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("room_id", ForeignKey("room.id"), nullable=True, index=True)
)

user = Table(
    "user",
    meta_data,
    Column("uuid", UUID, nullable=False, index=True, primary_key=True),
    Column("name", String),
    Column("is_superuser", Boolean, server_default="false", nullable=False),
    Column("group_id", ForeignKey("group.id"), nullable=True, index=True)
)


room = Table(
    "room",
    meta_data,
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("capacity", Integer, nullable=False),
    Column("img", String, index=True),
    Column("description", TEXT, nullable=False, server_default="")
)

personal_reservation = Table(
    "personal_reservation",
    meta_data,
    Column("id", Integer, primary_key=True),
    Column("room_id", ForeignKey("room.id"), nullable=False, index=True),
    Column("user_uuid", ForeignKey("user.uuid"), nullable=False, index=True),
    Column("info_for_moderator", TEXT, nullable=False),
    Column("needable_items", ARRAY(Integer),
           nullable=False, server_default="{}"),
    Column("date_start", TIMESTAMP, nullable=False, index=True),
    Column("date_end", TIMESTAMP, nullable=False, index=True),
    Column("status", SMALLINT, nullable=False, server_default="0", index=True ),
    
    Column("cause_cancel", TEXT, nullable=False, server_default="")
)

event = Table(
    "event",
    meta_data,
    Column("id", Integer, primary_key=True),
    Column("event_base_id", Integer, EVENT_BASE_ID_SEQ, nullable=False, server_default=EVENT_BASE_ID_SEQ.next_value()),

    Column("room_id", ForeignKey("room.id"), nullable=False, index=True),
    Column("user_uuid", ForeignKey("user.uuid"), nullable=False, index=True),
    Column("info_for_moderator", TEXT, nullable=False),

    Column("title", String, nullable=False),
    Column("description", TEXT, nullable=False),
    Column("participants", ARRAY(UUID), nullable=False, server_default="{}"),
    Column("needable_items", ARRAY(Integer),
           nullable=False, server_default="{}"),
    Column("img", String, index=True),
    Column("repeat", String, index=True),

    Column("date_start", TIMESTAMP, nullable=False, index=True),
    Column("date_end", TIMESTAMP, nullable=False, index=True),
    Column("status", SMALLINT, nullable=False, server_default="0", index=True), # 0 - Not moderated, 1 - approve, 2 - reject

    Column("cause_cancel", TEXT, nullable=False, server_default="")
)

schedule = Table(
    "schedule",
    meta_data,
    Column("id", Integer, primary_key=True),
    Column("date", DATE, nullable=False, index=True),
    Column("schedule_time", ARRAY(String), nullable=False),
    Column("room_id", ForeignKey("room.id"), nullable=False, index=True)
)


action_history = Table(
    "action_history",
    meta_data,
    Column("id", Integer, primary_key=True),
    Column("action", String, nullable=False, index=True),
    Column("date", TIMESTAMP, nullable=False, default=datetime.utcnow, index=True),
    Column("subject_uuid", ForeignKey("user.uuid"), nullable=False),
    Column("object_table", String, nullable=False),
    Column("object_id", String, nullable=False),
    Column("detail", JSON, nullable=False),
)

worker = Table(
    "worker",
    meta_data,
    Column("user_uuid", ForeignKey("user.uuid"), nullable=False, primary_key=True)
)
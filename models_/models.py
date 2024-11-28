from sqlalchemy import MetaData, Table, Integer, Column, String, TIMESTAMP,ARRAY, Boolean, CheckConstraint, Float, ForeignKey, UUID
from datetime import datetime

meta_data = MetaData()

group = Table(
    "group",
    meta_data, 
    Column("id", Integer, primary_key=True),
    Column("name", String, nullable=False),
    Column("permissions", ARRAY(String), nullable=False)
)

user = Table(
    "user",
    meta_data, 
    Column("uuid", UUID, nullable = False, index=True, primary_key=True),
    Column("is_superuser", Boolean, default=False, nullable=False),
    Column("group_id", ForeignKey("group.id"), nullable = False)
)



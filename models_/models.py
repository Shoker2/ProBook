from sqlalchemy import MetaData, Table, Integer, Column, String, TIMESTAMP,ARRAY, Boolean, CheckConstraint, Float, ForeignKey, UUID
from datetime import datetime

meta_data = MetaData()

user = Table(
    "user",
    meta_data,
    # Column("id", Integer, primary_key=True), 
    Column("uuid", UUID, nullable = False, index=True, primary_key=True),
    Column("is_superuser", Boolean, default=False, nullable=False)
)
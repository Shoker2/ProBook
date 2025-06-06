from config import config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typing import AsyncGenerator, Optional
from fastapi import Depends
from sqlalchemy import Integer, Column, String, TIMESTAMP, Boolean, ARRAY, UUID
from datetime import datetime
from config import config
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import update, select, insert, delete
import uuid

from models_ import user, group

DATABASE_URL =  f"postgresql+asyncpg://{config['Database']['DB_USER']}:{config['Database']['DB_PASS']}@{config['Database']['DB_HOST']}:{config['Database']['DB_PORT']}/{config['Database']['DB_NAME']}"

engine = create_async_engine(DATABASE_URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

SECRET = config['Miscellaneous']['secret']
ALGORITHM = "HS256"


class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "user"
    uuid = Column(UUID, nullable=False, index=True, primary_key=True)
    is_superuser = Column(Boolean, default=False, nullable=False)


class Group(Base):
    __tablename__ = "group"
    id = Column("id", Integer, primary_key=True)
    name = Column("name", String, nullable=False)
    permissions = Column("permissions", ARRAY(String), nullable=False)
    is_default = Column("is_default", Boolean, server_default="false", nullable=False)



async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

# Создание нового пользователя
async def create_user(uuid_str: str, is_superuser: bool = False, session: AsyncSession = Depends(get_async_session)) -> User:
    new_user = User(uuid=uuid.UUID(uuid_str), is_superuser=is_superuser)
    session.add(new_user)

    await session.commit()
    await session.refresh(new_user)
    return new_user


async def reset_group(
    id: int,
    session: AsyncSession
):
    stmt = update(user).where(user.c.group_id == id).values(group_id=None)
    
    await session.execute(stmt)
    await session.commit()
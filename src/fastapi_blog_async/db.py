from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = "sqlite+aiosqlite:///blog.db"

async_db_engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


AsyncSessionLocal = async_sessionmaker(
    async_db_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


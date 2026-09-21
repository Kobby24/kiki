import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET_KEY"] = "test-secret"
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from app.main import app
from app.db.base import Base
from app.db.session import engine, SessionLocal


@pytest_asyncio.fixture(autouse=True)
async def reset_database():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as test_client:
        yield test_client

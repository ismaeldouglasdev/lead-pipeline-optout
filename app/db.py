"""Async database engine for the opt-out service.

Uses the DATABASE_URL env var. On Render, point it at a persistent Postgres
(Neon / Render Postgres free tiers). Local fallback is SQLite for development.
"""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./optouts.db")

if DATABASE_URL.startswith("sqlite") and "+" not in DATABASE_URL.split("://")[0]:
    DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://", 1)

if DATABASE_URL.startswith("postgres"):
    # asyncpg needs postgresql+asyncpg:// scheme
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    """FastAPI dependency yielding an async session."""
    async with AsyncSessionLocal() as session:
        yield session

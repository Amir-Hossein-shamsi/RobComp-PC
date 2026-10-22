"""Async database engine and schema bootstrap for Worker B."""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .models import Base

logger = logging.getLogger("worker_b.db")

engine = create_async_engine(
    settings.mysql_url,
    pool_pre_ping=True,   
    pool_recycle=1800,    
    pool_size=5,
    max_overflow=5,
    future=True,
)

SessionFactory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession
)


async def init_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Schema ready (RTDS table ensured).")

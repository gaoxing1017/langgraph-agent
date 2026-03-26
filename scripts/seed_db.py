#!/usr/bin/env python
"""Seed the development database with sample data."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from agent_framework.config.settings import get_settings
from agent_framework.persistence.models import RunLog, Session


async def seed() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)

    async with async_session() as session:
        # Seed a sample session
        sample_session = Session(
            id=str(uuid.uuid4()),
            thread_id="seed-thread-001",
            user_id="seed-user",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(sample_session)

        # Seed a sample run log
        run_log = RunLog(
            id=str(uuid.uuid4()),
            thread_id="seed-thread-001",
            run_id=str(uuid.uuid4()),
            status="completed",
            input_summary="What is 2+2?",
            output_summary="The answer is 4.",
            created_at=datetime.utcnow(),
        )
        session.add(run_log)
        await session.commit()

    await engine.dispose()
    print("Database seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())

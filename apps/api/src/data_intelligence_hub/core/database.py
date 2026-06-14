from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from data_intelligence_hub.core.config import get_settings

SchemaStatus = Literal["current", "pending", "missing", "timeout", "unavailable"]


@dataclass(frozen=True)
class DatabaseSchemaStatus:
    status: SchemaStatus
    current_revision: str | None
    head_revision: str | None


def create_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


engine = create_engine()
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


async def check_database() -> str:
    try:
        async with asyncio.timeout(1.5):
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except TimeoutError:
        return "timeout"
    except Exception:
        return "unavailable"
    return "connected"


async def check_database_schema() -> DatabaseSchemaStatus:
    try:
        head_revision = get_alembic_head_revision()
    except Exception:
        return DatabaseSchemaStatus(
            status="unavailable",
            current_revision=None,
            head_revision=None,
        )
    try:
        async with asyncio.timeout(1.5):
            async with engine.connect() as connection:
                result = await connection.execute(text("SELECT version_num FROM alembic_version"))
                versions = [str(version) for version in result.scalars().all()]
    except TimeoutError:
        return DatabaseSchemaStatus(
            status="timeout",
            current_revision=None,
            head_revision=head_revision,
        )
    except SQLAlchemyError as exc:
        return DatabaseSchemaStatus(
            status=_schema_error_status(exc),
            current_revision=None,
            head_revision=head_revision,
        )
    if len(versions) != 1:
        return DatabaseSchemaStatus(
            status="missing",
            current_revision=",".join(sorted(versions)) or None,
            head_revision=head_revision,
        )
    current_revision = versions[0]
    return DatabaseSchemaStatus(
        status="current" if current_revision == head_revision else "pending",
        current_revision=current_revision,
        head_revision=head_revision,
    )


def get_alembic_head_revision() -> str:
    api_root = Path(__file__).resolve().parents[3]
    config = Config(str(api_root / "alembic.ini"))
    config.set_main_option("script_location", str(api_root / "alembic"))
    script_directory = ScriptDirectory.from_config(config)
    heads = script_directory.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Expected exactly one Alembic head, found {len(heads)}")
    return heads[0]


def _schema_error_status(exc: SQLAlchemyError) -> SchemaStatus:
    error_text = str(exc).lower()
    if "alembic_version" in error_text and (
        "does not exist" in error_text
        or "no such table" in error_text
        or "undefinedtable" in error_text
    ):
        return "missing"
    return "unavailable"

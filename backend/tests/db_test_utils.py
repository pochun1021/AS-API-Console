from __future__ import annotations

import os
import re

from sqlalchemy.exc import OperationalError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")
_WORKER_ENV = "PYTEST_XDIST_WORKER"


def _base_test_database_url() -> str | None:
    settings = get_settings()
    return settings.test_database_url or settings.database_url


def worker_id() -> str | None:
    return os.environ.get(_WORKER_ENV) or None


def build_worker_test_database_url(base_url: str, worker: str | None) -> str:
    if not worker:
        return base_url

    url = make_url(base_url)
    if not url.database:
        raise ValueError("test database URL must include a database name")

    return str(url.set(database=f"{url.database}_{worker}"))


def configure_worker_test_database_env() -> None:
    base_url = _base_test_database_url()
    if not base_url:
        return

    worker = worker_id()
    if not worker:
        return

    os.environ["TEST_DATABASE_URL"] = build_worker_test_database_url(base_url, worker)
    get_settings.cache_clear()


def resolved_test_database_url() -> str | None:
    settings = get_settings()
    return settings.test_database_url or settings.database_url


def ensure_worker_test_database() -> str | None:
    db_url = resolved_test_database_url()
    if not db_url:
        return None

    worker = worker_id()
    if not worker:
        return db_url

    base_url = _base_test_database_url() or db_url
    target_url = make_url(db_url)
    base_engine_url = make_url(base_url)
    database = target_url.database
    if not database:
        raise RuntimeError(
            "Parallel pytest workers require TEST_DATABASE_URL/TEST_DB_* to include a base test database name."
        )
    if not _DB_NAME_RE.match(database):
        raise ValueError(f"unsafe database name for test database: {database}")

    engine = create_engine(base_engine_url, future=True)
    try:
        try:
            with engine.begin() as conn:
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{database}`"))
        except OperationalError as exc:
            raise RuntimeError(
                "Failed to create worker test database. "
                "Parallel pytest workers require the TEST_DATABASE_URL/TEST_DB_* credentials "
                f"to connect to the base test database and have CREATE DATABASE permission for `{database}`."
            ) from exc
    finally:
        engine.dispose()
    return db_url

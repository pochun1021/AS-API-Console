from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None
_engine_url: str | None = None
_session_factory = None


def resolved_test_database_url() -> str:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    if not db_url:
        raise RuntimeError("test database URL is not configured")
    return db_url


def get_test_engine() -> Engine:
    global _engine, _engine_url
    db_url = resolved_test_database_url()
    if _engine is None or _engine_url != db_url:
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(db_url, future=True)
        _engine_url = db_url
    return _engine


def get_test_session_factory():
    global _session_factory
    engine = get_test_engine()
    if _session_factory is None or _session_factory.kw["bind"] is not engine:
        _session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    return _session_factory


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_test_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def begin_connection():
    with get_test_engine().begin() as conn:
        yield conn


def reset_test_runtime() -> None:
    global _engine, _engine_url, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_url = None
    _session_factory = None

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


class _SessionLocalProxy:
    def __call__(self, *args, **kwargs) -> Session:
        factory = get_session_factory()
        return factory(*args, **kwargs)


_engine = None
_session_factory = None


def _database_url() -> str:
    settings = get_settings()
    return settings.test_database_url if settings.app_env.lower() == "test" else settings.database_url


def get_engine():
    global _engine
    db_url = _database_url()
    if _engine is None or str(_engine.url) != db_url:
        if _engine is not None:
            _engine.dispose()
        _engine = create_engine(db_url, future=True)
    return _engine


def get_session_factory():
    global _session_factory
    engine = get_engine()
    if _session_factory is None or _session_factory.kw["bind"] is not engine:
        _session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    return _session_factory


def reset_session_state() -> None:
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


SessionLocal = _SessionLocalProxy()


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()

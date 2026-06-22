from collections.abc import Generator
from datetime import UTC, datetime
import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("API_KEY_APPLICATION_GO_LIVE_AT", "2020-01-01T00:00:00+08:00")

from tests.db_test_utils import configure_worker_test_database_env, ensure_worker_test_database, worker_id

configure_worker_test_database_env()

from app.core.config import get_settings
get_settings.cache_clear()

from app.core.security import rate_limiter
from db.base import Base
from db import models  # noqa: F401
from db.models.limit_strategy_config import LimitStrategyConfig
from db.session import get_db, reset_session_state
from tests.db_runtime import reset_test_runtime

from app.main import app

API_BASE = "/main/api/v1"
_LIMIT_STRATEGY_CONFIG_ID = "global-limit-strategy-config"


def api_path(path: str) -> str:
    return f"{API_BASE}{path}"


def _seed_default_limit_strategy_config(db: Session) -> None:
    now = datetime.now(UTC)
    db.add(
        LimitStrategyConfig(
            id=_LIMIT_STRATEGY_CONFIG_ID,
            budget_max_budget="1000",
            budget_duration="monthly",
            rate_limit_tpm=10000,
            rate_limit_rpm=500,
            max_parallel_requests=0,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()


def _reset_test_schema(engine) -> None:
    Base.metadata.drop_all(bind=engine, checkfirst=True)
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        try:
            inspector = inspect(conn)
            existing_tables = inspector.get_table_names()
            for table_name in reversed(existing_tables):
                conn.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
        finally:
            conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    Base.metadata.create_all(bind=engine, checkfirst=True)


def _clear_test_data(engine) -> None:
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect in {"mysql", "mariadb"}:
            conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            try:
                for table in reversed(Base.metadata.sorted_tables):
                    conn.execute(text(f"DELETE FROM `{table.name}`"))
            finally:
                conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            return

        if dialect == "postgresql":
            conn.execute(text("SET session_replication_role = replica"))
            try:
                for table in reversed(Base.metadata.sorted_tables):
                    conn.execute(text(f'DELETE FROM "{table.name}"'))
            finally:
                conn.execute(text("SET session_replication_role = DEFAULT"))
            return

        if dialect == "sqlite":
            conn.execute(text("PRAGMA foreign_keys=OFF"))
            try:
                for table in reversed(Base.metadata.sorted_tables):
                    conn.execute(text(f'DELETE FROM "{table.name}"'))
            finally:
                conn.execute(text("PRAGMA foreign_keys=ON"))
            return

        raise RuntimeError(f"unsupported test database dialect for reset: {dialect}")


def _build_test_db_diagnostics(engine) -> dict[str, str | None]:
    settings = get_settings()
    diagnostics: dict[str, str | None] = {
        "worker_id": worker_id(),
        "settings_test_database_url": settings.test_database_url,
        "settings_database_url": settings.database_url,
        "engine_url": str(engine.url),
        "current_database": None,
        "connection_id": None,
        "threads_connected": None,
    }
    try:
        with engine.connect() as conn:
            diagnostics["current_database"] = conn.execute(text("SELECT DATABASE()")).scalar()
            diagnostics["connection_id"] = str(conn.execute(text("SELECT CONNECTION_ID()")).scalar())
            threads_connected_row = conn.execute(text("SHOW STATUS LIKE 'Threads_connected'")).fetchone()
            diagnostics["threads_connected"] = str(threads_connected_row[1]) if threads_connected_row else None
    except Exception as exc:  # pragma: no cover - diagnostics path only
        diagnostics["current_database"] = f"<unavailable: {exc}>"
        diagnostics["connection_id"] = f"<unavailable: {exc}>"
        diagnostics["threads_connected"] = f"<unavailable: {exc}>"
    return diagnostics


def _format_test_db_diagnostics(diagnostics: dict[str, str | None]) -> str:
    ordered_keys = (
        "worker_id",
        "settings_test_database_url",
        "settings_database_url",
        "engine_url",
        "current_database",
        "connection_id",
        "threads_connected",
    )
    return ", ".join(f"{key}={diagnostics.get(key)}" for key in ordered_keys)


@pytest.fixture(autouse=True)
def reset_test_environment(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
    monkeypatch.setenv("API_KEY_APPLICATION_GO_LIVE_AT", "2020-01-01T00:00:00+08:00")
    monkeypatch.delenv("ALLOW_HEADER_AUTH", raising=False)
    get_settings.cache_clear()
    reset_session_state()
    reset_test_runtime()
    yield
    get_settings.cache_clear()
    reset_session_state()
    reset_test_runtime()


@pytest.fixture(autouse=True)
def disable_provider_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: False)
    rate_limiter.reset()


@pytest.fixture(scope="session", autouse=True)
def prepare_worker_test_database() -> Generator[None, None, None]:
    ensure_worker_test_database()
    yield


@pytest.fixture(scope="session")
def test_db_engine(prepare_worker_test_database) -> Generator:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    if not db_url:
        pytest.skip("Set TEST_DATABASE_URL, TEST_DB_*, DATABASE_URL, or DB_* to run tests.")

    engine = create_engine(db_url, future=True, poolclass=NullPool)
    try:
        _reset_test_schema(engine)
        yield engine
    except Exception as exc:
        diagnostics = _build_test_db_diagnostics(engine)
        raise RuntimeError(
            "Failed to prepare session-scoped test schema: "
            f"{_format_test_db_diagnostics(diagnostics)}"
        ) from exc
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def testing_session_local(test_db_engine):
    return sessionmaker(bind=test_db_engine, autoflush=False, autocommit=False, class_=Session)


@pytest.fixture(autouse=True)
def reset_test_database(test_db_engine, testing_session_local) -> Generator[None, None, None]:
    try:
        _clear_test_data(test_db_engine)
    except Exception as exc:
        diagnostics = _build_test_db_diagnostics(test_db_engine)
        raise RuntimeError(
            "Failed to clear test data before test setup: "
            f"{_format_test_db_diagnostics(diagnostics)}"
        ) from exc

    with testing_session_local() as seed_db:
        _seed_default_limit_strategy_config(seed_db)

    yield


@pytest.fixture()
def client(testing_session_local) -> Generator[TestClient, None, None]:
    reset_session_state()

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    try:
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
    except Exception as exc:
        diagnostics = _build_test_db_diagnostics(testing_session_local.kw["bind"])
        raise RuntimeError(
            "Failed during client fixture setup: "
            f"{_format_test_db_diagnostics(diagnostics)}"
        ) from exc
    finally:
        app.dependency_overrides.clear()
        reset_session_state()


def build_headers(
    *, role: str, account: str, email: str, sysid: int | str, name: str = "Tester", department: str = "IT"
) -> dict[str, str]:
    return {
        "x-account": account,
        "x-name": name,
        "x-email": email,
        "x-department": department,
        "x-sysid": str(sysid),
        "x-role": role,
    }


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return build_headers(role="admin", account="admin", email="admin@example.com", sysid="1001")


@pytest.fixture()
def user_headers() -> dict[str, str]:
    return build_headers(role="user", account="user1", email="user1@example.com", sysid="2001")

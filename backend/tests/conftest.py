from collections.abc import Generator
from datetime import UTC, datetime
import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

from app.core.config import get_settings
from app.core.security import rate_limiter
from db.base import Base
from db import models  # noqa: F401
from db.models.limit_strategy_config import LimitStrategyConfig
from db.session import get_db
from tests.db_test_utils import configure_worker_test_database_env, ensure_worker_test_database

configure_worker_test_database_env()
get_settings.cache_clear()

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
    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DROP TABLE IF EXISTS `{table.name}`"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def disable_provider_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: False)
    rate_limiter.reset()


@pytest.fixture(scope="session", autouse=True)
def prepare_worker_test_database() -> Generator[None, None, None]:
    ensure_worker_test_database()
    yield


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    if not db_url:
        pytest.skip("Set TEST_DATABASE_URL, TEST_DB_*, DATABASE_URL, or DB_* to run tests.")

    engine = create_engine(db_url, future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    _reset_test_schema(engine)
    with TestingSessionLocal() as seed_db:
        _seed_default_limit_strategy_config(seed_db)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    _reset_test_schema(engine)
    app.dependency_overrides.clear()


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

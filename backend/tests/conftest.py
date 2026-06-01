from collections.abc import Generator
import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

from app.main import app
from app.core.config import get_settings
from app.core.security import rate_limiter
from db.base import Base
from db import models  # noqa: F401
from db.session import get_db


@pytest.fixture(autouse=True)
def disable_provider_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.provider_client.ProviderClient.is_configured", lambda self: False)
    rate_limiter.reset()


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    settings = get_settings()
    db_url = settings.test_database_url or settings.database_url
    if not db_url:
        pytest.skip("Set TEST_DATABASE_URL, TEST_DB_*, DATABASE_URL, or DB_* to run tests.")

    engine = create_engine(db_url, future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)
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

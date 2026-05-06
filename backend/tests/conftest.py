from collections.abc import Generator
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app
from db.base import Base
from db import models  # noqa: F401
from db.session import get_db


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
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
    app.dependency_overrides.clear()


def build_headers(*, role: str, account: str, email: str, sysid: str, name: str = "Tester", department: str = "IT") -> dict[str, str]:
    return {
        "x-account": account,
        "x-name": name,
        "x-email": email,
        "x-department": department,
        "x-sysid": sysid,
        "x-role": role,
    }


@pytest.fixture()
def admin_headers() -> dict[str, str]:
    return build_headers(role="admin", account="admin", email="admin@example.com", sysid="admin-1")


@pytest.fixture()
def user_headers() -> dict[str, str]:
    return build_headers(role="user", account="user1", email="user1@example.com", sysid="user-1")

"""Create the isolated, fixed SQLite fixture used by docs/issue-58-reconciliation.md."""

from __future__ import annotations

import argparse
from datetime import UTC, date, datetime
from pathlib import Path
import sys
from uuid import NAMESPACE_DNS, uuid5

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.base import Base  # noqa: E402
from db import models  # noqa: E402,F401
from db.models.admins import Admin  # noqa: E402
from db.models.api_keys import ApiKey  # noqa: E402
from db.models.applications import ApiKeyApplication  # noqa: E402


ROWS = (
    ("alice", "Alice Chen", "IT", "active", 1),
    ("alice", "Alice Chen", "R&D", "revoked", 2),
    ("bob", "Bob Lin", "IT", "active", 3),
    ("bob", "Bob Lin", "IT", "active", 4),
    ("carol", "Carol Wu", "IT", "expired", 5),
    ("dave", "Dave Ho", "R&D", "active", 6),
    ("erin", "Erin Lin", "IT", "revoked", 7),
    ("frank", "Frank Wu", "R&D", "active", 8),
    ("grace", "Grace Lee", "IT", "active", 9),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="new SQLite database path outside the repository")
    args = parser.parse_args()
    database = args.database.resolve()
    if database.exists():
        parser.error(f"refusing to overwrite existing database: {database}")
    if database.suffix != ".sqlite":
        parser.error("database path must end in .sqlite")
    if database.is_relative_to(Path(__file__).resolve().parents[2]):
        parser.error("database must be outside the repository")

    database.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{database}", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Admin(
            id=900001, account="evidence.admin", email="evidence.admin@example.com",
            name="Evidence Admin", department="IT", status="active",
            created_by="issue58_fixture", updated_by="issue58_fixture",
        ))
        for account, name, department, status, day in ROWS:
            application_id = str(uuid5(NAMESPACE_DNS, f"issue58-application-{day}"))
            key_id = str(uuid5(NAMESPACE_DNS, f"issue58-key-{day}"))
            expires_at = datetime(2026, 5, 4, tzinfo=UTC) if status == "expired" else datetime(2099, 1, 1, tzinfo=UTC)
            session.add(ApiKeyApplication(
                id=application_id, account=account, name=name,
                email=f"{account}@example.com", department=department,
                application_date=date(2026, 5, day), duration_days=30,
                original_duration_days=30, purpose="Issue 58 reconciliation fixture",
                status=status, issued_at=datetime(2026, 5, day, tzinfo=UTC),
                expires_at=expires_at, sysid=910000 + day,
            ))
            session.add(ApiKey(
                id=key_id, application_id=application_id,
                key_hash=f"issue58-hash-{day}", masked_key=f"AS-****{day:02d}",
                status=status,
            ))
        session.commit()
    engine.dispose()
    print(f"Created isolated fixture: {database} ({len(ROWS)} applications, {len(ROWS)} keys)")


if __name__ == "__main__":
    main()

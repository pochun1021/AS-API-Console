from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import sys

from sqlalchemy import select, update

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db import models  # noqa: F401
from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync expired API keys from effective status into DB status fields."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Maximum rows to update per batch (default: 1000).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show number of rows that would be updated without committing changes.",
    )
    return parser.parse_args()


def _collect_target_key_ids(*, batch_size: int) -> list[str]:
    now = datetime.now(UTC)
    stmt = (
        select(ApiKey.id)
        .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
        .where(ApiKey.status == "active")
        .where(ApiKeyApplication.expires_at < now)
        .limit(batch_size)
    )

    with SessionLocal() as session:
        return [row[0] for row in session.execute(stmt).all()]


def run_once(*, batch_size: int, dry_run: bool) -> int:
    key_ids = _collect_target_key_ids(batch_size=batch_size)
    if not key_ids:
        return 0

    if dry_run:
        return len(key_ids)

    now = datetime.now(UTC)
    with SessionLocal() as session:
        session.execute(update(ApiKey).where(ApiKey.id.in_(key_ids)).values(status="expired"))
        session.execute(
            update(ApiKeyApplication)
            .where(ApiKeyApplication.id.in_(select(ApiKey.application_id).where(ApiKey.id.in_(key_ids))))
            .values(status="expired", updated_at=now)
        )
        session.commit()
    return len(key_ids)


def main() -> None:
    args = parse_args()
    updated = run_once(batch_size=args.batch_size, dry_run=args.dry_run)
    mode = "dry-run" if args.dry_run else "sync"
    print(f"expired-key-{mode} updated_count={updated} batch_size={args.batch_size}")


if __name__ == "__main__":
    main()

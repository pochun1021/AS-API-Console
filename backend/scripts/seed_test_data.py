from __future__ import annotations

import argparse
import hashlib
import secrets
from pathlib import Path
import sys
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import models  # noqa: F401
from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from db.models.users import User
from db.models.whitelist import ApiKeyWhitelist
from db.session import SessionLocal
from app.core.config import get_settings
from app.services.crypto_service import CryptoService


def _hash_key(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def _mask_key(plaintext: str) -> str:
    return f"{plaintext[:7]}****{plaintext[-4:]}"


def _generate_seed_api_key() -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    suffix = "".join(secrets.choice(alphabet) for _ in range(30))
    return f"AS-{suffix}"


def _build_users(now: datetime) -> list[User]:
    return [
        User(
            id="admin-seed-001",
            account="admin.seed",
            email="admin.seed@example.com",
            name="Admin Seed",
            role="admin",
            status="active",
            created_at=now,
            updated_at=now,
        ),
        User(
            id="admin-seed-002",
            account="admin.inactive.seed",
            email="admin.inactive.seed@example.com",
            name="Admin Inactive Seed",
            role="admin",
            status="inactive",
            created_at=now,
            updated_at=now,
        ),
        *[
            User(
                id=f"user-seed-{idx:03d}",
                account=f"user{idx}",
                email=f"user{idx}@example.com",
                name=f"User {idx}",
                role="user",
                status="active",
                created_at=now,
                updated_at=now,
            )
            for idx in range(1, 7)
        ],
    ]


def _build_whitelists(now: datetime) -> list[ApiKeyWhitelist]:
    whitelists: list[ApiKeyWhitelist] = []
    for idx in range(1, 7):
        whitelists.append(
            ApiKeyWhitelist(
                id=str(uuid.uuid4()),
                email=f"user{idx}@example.com",
                status="active",
                note="seed active",
                created_by="admin.seed",
                updated_by="admin.seed",
                created_at=now,
                updated_at=now,
            )
        )
    for idx in range(7, 9):
        whitelists.append(
            ApiKeyWhitelist(
                id=str(uuid.uuid4()),
                email=f"user{idx}@example.com",
                status="inactive",
                note="seed inactive",
                created_by="admin.seed",
                updated_by="admin.seed",
                created_at=now,
                updated_at=now,
            )
        )
    return whitelists


def _calc_expires_at(issued_at: datetime, duration_months: int) -> datetime:
    month = issued_at.month - 1 + duration_months
    year = issued_at.year + month // 12
    month = month % 12 + 1
    day = min(issued_at.day, 28)
    return issued_at.replace(year=year, month=month, day=day)


def _build_applications_and_keys(now: datetime) -> tuple[list[ApiKeyApplication], list[ApiKey]]:
    statuses = (["active"] * 8) + (["revoked"] * 7) + (["expired"] * 5)
    durations = [1, 6, 12]
    departments = ["IT", "R&D", "Data", "Platform"]
    purposes = ["integration test", "internal dashboard", "batch sync", "analytics"]

    applications: list[ApiKeyApplication] = []
    keys: list[ApiKey] = []
    settings = get_settings()
    crypto = CryptoService(settings.api_key_encryption_secret)

    for idx, status in enumerate(statuses, start=1):
        user_no = ((idx - 1) % 6) + 1
        user_id = f"user-seed-{user_no:03d}"
        account = f"user{user_no}"
        email = f"user{user_no}@example.com"
        issued_at = now - timedelta(days=idx * 7)
        duration_months = durations[idx % len(durations)]
        expires_at = _calc_expires_at(issued_at, duration_months)
        application_id = str(uuid.uuid4())
        sysid = user_id
        revoked_at = issued_at + timedelta(days=3) if status == "revoked" else None

        application = ApiKeyApplication(
            id=application_id,
            account=account,
            user_id=user_id,
            name=f"User {user_no}",
            email=email,
            department=departments[idx % len(departments)],
            application_date=(date.today() - timedelta(days=min(idx * 5, 180))),
            duration_months=duration_months,
            purpose=purposes[idx % len(purposes)],
            status=status,
            issued_at=issued_at,
            expires_at=expires_at,
            revoked_at=revoked_at,
            sysid=sysid,
            created_at=issued_at,
            updated_at=issued_at,
        )
        key_plain = _generate_seed_api_key()
        key = ApiKey(
            id=str(uuid.uuid4()),
            application_id=application_id,
            key_hash=_hash_key(key_plain),
            key_prefix="AS-",
            masked_key=_mask_key(key_plain),
            key_ciphertext=crypto.encrypt(key_plain),
            key_kek_version=settings.api_key_kek_version,
            length=30,
            security_level="high",
            status=status,
            created_at=issued_at,
        )

        applications.append(application)
        keys.append(key)

    return applications, keys


def _reset_seed_scope(session: Session) -> None:
    seed_user_ids = [f"user-seed-{idx:03d}" for idx in range(1, 7)] + ["admin-seed-001", "admin-seed-002"]
    app_ids = [row[0] for row in session.query(ApiKeyApplication.id).filter(ApiKeyApplication.user_id.in_(seed_user_ids)).all()]
    if app_ids:
        session.execute(delete(ApiKey).where(ApiKey.application_id.in_(app_ids)))
    session.execute(delete(ApiKeyApplication).where(ApiKeyApplication.user_id.in_(seed_user_ids)))
    session.execute(delete(ApiKeyWhitelist).where(ApiKeyWhitelist.email.like("user%@example.com")))
    session.execute(delete(User).where(User.id.in_(seed_user_ids)))


def seed_small(reset: bool) -> dict[str, int]:
    now = datetime.now(UTC)
    users = _build_users(now)
    whitelists = _build_whitelists(now)
    applications, keys = _build_applications_and_keys(now)

    with SessionLocal() as session:
        if reset:
            _reset_seed_scope(session)

        session.add_all(users)
        session.add_all(whitelists)
        session.add_all(applications)
        session.add_all(keys)
        session.commit()

    return {
        "users": len(users),
        "whitelists": len(whitelists),
        "applications": len(applications),
        "api_keys": len(keys),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed small test data set into AS API Console database.")
    parser.add_argument("--size", choices=["small"], default="small")
    parser.add_argument("--no-reset", action="store_true", help="Do not clear existing seed scope before insert.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reset = not args.no_reset
    result = seed_small(reset=reset)
    print(
        "Seed completed: "
        f"users={result['users']}, "
        f"whitelists={result['whitelists']}, "
        f"applications={result['applications']}, "
        f"api_keys={result['api_keys']}, "
        f"reset={reset}"
    )


if __name__ == "__main__":
    main()

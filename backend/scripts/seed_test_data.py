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
from db.models.admins import Admin
from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
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


def _build_admins(now: datetime) -> list[Admin]:
    return [
        Admin(
            id=900001,
            account="admin.seed",
            email="admin.seed@example.com",
            name="Admin Seed",
            department="Security",
            status="active",
            created_by="seed_script",
            updated_by="seed_script",
            created_at=now,
            updated_at=now,
        ),
        Admin(
            id=900002,
            account="admin.inactive.seed",
            email="admin.inactive.seed@example.com",
            name="Admin Inactive Seed",
            department="Security",
            status="inactive",
            created_by="seed_script",
            updated_by="seed_script",
            created_at=now,
            updated_at=now,
        ),
    ]


def _build_whitelists(now: datetime) -> list[ApiKeyWhitelist]:
    whitelist_seeds = [
        ("alice.seed", "Alice Seed", 910001, "alice.seed@example.com", "active", "seed active - platform"),
        ("bob.seed", "Bob Seed", 910002, "bob.seed@example.com", "active", "seed active - qa"),
        ("carol.seed", "Carol Seed", 910003, "carol.seed@example.com", "active", "seed active - data"),
        ("david.seed", "David Seed", 910004, "david.seed@example.com", "active", "seed active - backend"),
        ("eva.seed", "Eva Seed", 910005, "eva.seed@example.com", "active", "seed active - frontend"),
        ("frank.seed", "Frank Seed", 910006, "frank.seed@example.com", "active", "seed active - secops"),
        ("grace.seed", "Grace Seed", 910007, "grace.seed@example.com", "inactive", "seed inactive - offboarded"),
        ("henry.seed", "Henry Seed", 910008, "henry.seed@example.com", "inactive", "seed inactive - archived"),
        ("irene.seed", "Irene Seed", 910009, "irene.seed@example.com", "active", "seed active - temporary"),
        ("jack.seed", "Jack Seed", 910010, "jack.seed@example.com", "inactive", "seed inactive - project ended"),
    ]
    whitelists: list[ApiKeyWhitelist] = []
    for account, name, sysid, email, status, note in whitelist_seeds:
        whitelists.append(
            ApiKeyWhitelist(
                id=str(uuid.uuid4()),
                sysid=sysid,
                account=account,
                name=name,
                email=email,
                status=status,
                note=note,
                created_by="admin.seed",
                updated_by="admin.seed",
                created_at=now,
                updated_at=now,
            )
        )
    return whitelists


def _calc_expires_at(issued_at: datetime, duration_days: int) -> datetime:
    return issued_at + timedelta(days=duration_days)


def _build_applications_and_keys(now: datetime) -> tuple[list[ApiKeyApplication], list[ApiKey]]:
    statuses = (["active"] * 8) + (["revoked"] * 7) + (["expired"] * 5)
    durations = [30, 180, 360]
    departments = ["IT", "R&D", "Data", "Platform"]
    purposes = ["integration test", "internal dashboard", "batch sync", "analytics"]

    applications: list[ApiKeyApplication] = []
    keys: list[ApiKey] = []
    settings = get_settings()
    crypto = CryptoService(settings.api_key_encryption_secret)

    for idx, status in enumerate(statuses, start=1):
        user_no = ((idx - 1) % 6) + 1
        sysid = 920000 + user_no
        account = f"user{user_no}"
        email = f"user{user_no}@example.com"
        issued_at = now - timedelta(days=idx * 7)
        duration_days = durations[idx % len(durations)]
        expires_at = _calc_expires_at(issued_at, duration_days)
        application_id = str(uuid.uuid4())
        revoked_at = issued_at + timedelta(days=3) if status == "revoked" else None
        # Keep seed rows aligned with combined strategy policy.
        max_budget = "1000"
        budget_duration = "monthly"
        tpm_limit = 10000
        rpm_limit = 120

        application = ApiKeyApplication(
            id=application_id,
            account=account,
            name=f"User {user_no}",
            email=email,
            department=departments[idx % len(departments)],
            application_date=(date.today() - timedelta(days=min(idx * 5, 180))),
            duration_days=duration_days,
            original_duration_days=duration_days,
            purpose=purposes[idx % len(purposes)],
            max_budget=max_budget,
            budget_duration=budget_duration,
            tpm_limit=tpm_limit,
            rpm_limit=rpm_limit,
            status=status,
            issued_at=issued_at,
            expires_at=expires_at,
            revoked_at=revoked_at,
            sysid=sysid,
            is_proxy_submission=False,
            proxy_operator_account=None,
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
    seed_sysids = [920000 + idx for idx in range(1, 7)] + [900001, 900002]
    app_ids = [row[0] for row in session.query(ApiKeyApplication.id).filter(ApiKeyApplication.sysid.in_(seed_sysids)).all()]
    if app_ids:
        session.execute(delete(ApiKey).where(ApiKey.application_id.in_(app_ids)))
    session.execute(delete(ApiKeyApplication).where(ApiKeyApplication.sysid.in_(seed_sysids)))
    session.execute(delete(ApiKeyWhitelist).where(ApiKeyWhitelist.sysid.between(910001, 910199)))
    session.execute(delete(ApiKeyWhitelist).where(ApiKeyWhitelist.email.like("%seed@example.com")))
    session.execute(delete(ApiKeyWhitelist).where(ApiKeyWhitelist.email.like("user%@example.com")))
    session.execute(delete(Admin).where(Admin.id.in_([900001, 900002])))


def seed_small(reset: bool) -> dict[str, int]:
    now = datetime.now(UTC)
    admins = _build_admins(now)
    whitelists = _build_whitelists(now)
    applications, keys = _build_applications_and_keys(now)

    with SessionLocal() as session:
        if reset:
            _reset_seed_scope(session)

        session.add_all(admins)
        session.add_all(whitelists)
        session.add_all(applications)
        session.add_all(keys)
        session.commit()

    return {
        "admins": len(admins),
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
        f"admins={result['admins']}, "
        f"whitelists={result['whitelists']}, "
        f"applications={result['applications']}, "
        f"api_keys={result['api_keys']}, "
        f"reset={reset}"
    )


if __name__ == "__main__":
    main()

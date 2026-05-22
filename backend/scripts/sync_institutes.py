from __future__ import annotations

import argparse
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.institute_sync_service import InstituteSyncService
from app.services.persnl_soap_service import PersnlSoapService, PersnlSoapUnavailableError
from db import models  # noqa: F401
from db.session import SessionLocal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync institute master data from Persnl SOAP to local DB.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without writing to DB.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    soap = PersnlSoapService()
    soap.initialize()
    if not soap.logged_in:
        print(f"sync-institutes failed reason={soap.unavailable_reason or 'soap login failed'}")
        raise SystemExit(1)

    try:
        remote_institutes = soap.get_institutes()
    except PersnlSoapUnavailableError as exc:
        print(f"sync-institutes failed reason={exc}")
        raise SystemExit(1) from exc

    with SessionLocal() as session:
        result = InstituteSyncService(session).sync(remote_institutes, dry_run=args.dry_run)

    mode = "dry-run" if args.dry_run else "sync"
    print(
        "sync-institutes "
        f"mode={mode} "
        f"fetched={result.fetched_count} "
        f"inserted={result.inserted_count} "
        f"updated={result.updated_count} "
        f"unchanged={result.unchanged_count} "
        f"deactivated={result.deactivated_count}"
    )


if __name__ == "__main__":
    main()

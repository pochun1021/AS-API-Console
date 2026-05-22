from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.institute import Institute


@dataclass(slots=True)
class InstituteSyncResult:
    fetched_count: int
    inserted_count: int
    updated_count: int
    unchanged_count: int
    deactivated_count: int


class InstituteSyncService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def sync(self, remote_institutes: list[dict], dry_run: bool = False) -> InstituteSyncResult:
        existing_rows = self.session.execute(select(Institute)).scalars().all()
        existing_by_code = {row.inst_code: row for row in existing_rows}
        incoming_by_code = {item["instCode"]: item for item in remote_institutes}

        inserted_count = 0
        updated_count = 0
        unchanged_count = 0
        deactivated_count = 0
        now = datetime.now(timezone.utc)

        for inst_code, item in incoming_by_code.items():
            existing = existing_by_code.get(inst_code)
            if existing is None:
                inserted_count += 1
                if dry_run:
                    continue
                self.session.add(
                    Institute(
                        inst_code=inst_code,
                        inst_name=item["instName"],
                        abb_inst_name=item.get("abb_instName"),
                        einst_name=item.get("einstName"),
                        division=item.get("division"),
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                )
                continue

            changed = any(
                [
                    existing.inst_name != item["instName"],
                    existing.abb_inst_name != item.get("abb_instName"),
                    existing.einst_name != item.get("einstName"),
                    existing.division != item.get("division"),
                    existing.status != "active",
                ]
            )
            if not changed:
                unchanged_count += 1
                continue

            updated_count += 1
            if dry_run:
                continue
            existing.inst_name = item["instName"]
            existing.abb_inst_name = item.get("abb_instName")
            existing.einst_name = item.get("einstName")
            existing.division = item.get("division")
            existing.status = "active"
            existing.updated_at = now
            self.session.add(existing)

        for inst_code, existing in existing_by_code.items():
            if inst_code in incoming_by_code or existing.status == "inactive":
                continue
            deactivated_count += 1
            if dry_run:
                continue
            existing.status = "inactive"
            existing.updated_at = now
            self.session.add(existing)

        if not dry_run:
            self.session.commit()

        return InstituteSyncResult(
            fetched_count=len(remote_institutes),
            inserted_count=inserted_count,
            updated_count=updated_count,
            unchanged_count=unchanged_count,
            deactivated_count=deactivated_count,
        )

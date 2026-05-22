from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models.institute import Institute


class InstitutesService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_active(self) -> dict:
        stmt = select(Institute).where(Institute.status == "active").order_by(Institute.inst_code.asc())
        rows = self.session.execute(stmt).scalars().all()
        items = [
            {
                "inst_code": row.inst_code,
                "inst_name": row.inst_name,
                "abb_inst_name": row.abb_inst_name,
                "einst_name": row.einst_name,
                "division": row.division,
            }
            for row in rows
        ]
        return {"items": items, "total": len(items)}

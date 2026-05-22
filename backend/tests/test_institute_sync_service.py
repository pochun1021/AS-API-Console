from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.services.institute_sync_service import InstituteSyncService
from db.base import Base
from db.models.institute import Institute


def _build_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)
    return testing_session()


def test_sync_institutes_inserts_updates_and_deactivates():
    session = _build_session()
    session.add(
        Institute(
            inst_code="01",
            inst_name="舊名稱",
            abb_inst_name="舊簡稱",
            einst_name="Old Name",
            division="1",
            status="active",
        )
    )
    session.add(
        Institute(
            inst_code="99",
            inst_name="待停用",
            abb_inst_name=None,
            einst_name=None,
            division=None,
            status="active",
        )
    )
    session.commit()

    result = InstituteSyncService(session).sync(
        [
            {"instCode": "01", "instName": "新名稱", "abb_instName": "新簡稱", "einstName": "New Name", "division": "2"},
            {"instCode": "02", "instName": "新單位", "abb_instName": "新單位", "einstName": "New Dept", "division": "1"},
        ]
    )

    assert result.fetched_count == 2
    assert result.inserted_count == 1
    assert result.updated_count == 1
    assert result.unchanged_count == 0
    assert result.deactivated_count == 1

    rows = {row.inst_code: row for row in session.execute(select(Institute)).scalars().all()}
    assert rows["01"].inst_name == "新名稱"
    assert rows["01"].status == "active"
    assert rows["02"].inst_name == "新單位"
    assert rows["02"].status == "active"
    assert rows["99"].status == "inactive"


def test_sync_institutes_dry_run_does_not_mutate():
    session = _build_session()

    result = InstituteSyncService(session).sync(
        [{"instCode": "01", "instName": "院本部", "abb_instName": "院本部", "einstName": "HQ", "division": "1"}],
        dry_run=True,
    )

    assert result.inserted_count == 1
    assert session.execute(select(Institute)).scalars().all() == []

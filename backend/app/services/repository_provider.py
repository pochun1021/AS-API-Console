from sqlalchemy.orm import Session

from db.repositories import (
    SQLAlchemyAdminRepository,
    SQLAlchemyApiKeyRepository,
    SQLAlchemyWhitelistRepository,
)


def get_admin_repository(session: Session) -> SQLAlchemyAdminRepository:
    return SQLAlchemyAdminRepository(session)


def get_whitelist_repository(session: Session) -> SQLAlchemyWhitelistRepository:
    return SQLAlchemyWhitelistRepository(session)


def get_api_key_repository(session: Session) -> SQLAlchemyApiKeyRepository:
    return SQLAlchemyApiKeyRepository(session)

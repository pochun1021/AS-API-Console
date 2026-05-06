from sqlalchemy.orm import Session

from db.repositories import (
    SQLAlchemyApiKeyRepository,
    SQLAlchemyUserRepository,
    SQLAlchemyWhitelistRepository,
)


def get_user_repository(session: Session) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(session)


def get_whitelist_repository(session: Session) -> SQLAlchemyWhitelistRepository:
    return SQLAlchemyWhitelistRepository(session)


def get_api_key_repository(session: Session) -> SQLAlchemyApiKeyRepository:
    return SQLAlchemyApiKeyRepository(session)

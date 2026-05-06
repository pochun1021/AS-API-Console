from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from db.models.users import User
from db.models.whitelist import ApiKeyWhitelist
from db.repositories.interfaces import ApiKeyRepository, UserRepository, WhitelistRepository
from db.repositories.types import (
    ApiKeyCreateInput,
    ApiKeyDetail,
    ApiKeyListItem,
    ApplicationCreateInput,
    AuthIdentity,
    WhitelistCreateInput,
    WhitelistUpdateInput,
)


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, user_id: str) -> User | None:
        return self.session.get(User, user_id)

    def get_by_account(self, account: str) -> User | None:
        stmt = select(User).where(User.account == account)
        return self.session.scalar(stmt)

    def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        return self.session.scalar(stmt)

    def search(self, keyword: str, limit: int = 20) -> list[User]:
        like = f"%{keyword}%"
        stmt = (
            select(User)
            .where(User.account.like(like) | User.email.like(like) | User.name.like(like))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def update_role(self, user_id: str, role: str) -> User | None:
        user = self.get_by_id(user_id)
        if not user:
            return None
        user.role = role
        user.updated_at = datetime.now(timezone.utc)
        self.session.add(user)
        self.session.flush()
        return user

    def upsert_from_auth(self, identity: AuthIdentity) -> User:
        user = self.get_by_account(identity.account)
        now = datetime.now(timezone.utc)
        if user is None:
            user = User(
                id=identity.sysid,
                account=identity.account,
                email=identity.email.lower(),
                name=identity.name,
                role="user",
                status="active",
                created_at=now,
                updated_at=now,
            )
        else:
            user.name = identity.name
            user.email = identity.email.lower()
            user.updated_at = now
        self.session.add(user)
        self.session.flush()
        return user


class SQLAlchemyWhitelistRepository(WhitelistRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, data: WhitelistCreateInput) -> ApiKeyWhitelist:
        now = datetime.now(timezone.utc)
        whitelist = ApiKeyWhitelist(
            id=data.id,
            email=data.email.lower(),
            status="active",
            note=data.note,
            created_by=data.created_by,
            updated_by=data.created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(whitelist)
        self.session.flush()
        return whitelist

    def list(self, status: str | None = None, limit: int = 100, offset: int = 0) -> list[ApiKeyWhitelist]:
        stmt: Select[tuple[ApiKeyWhitelist]] = select(ApiKeyWhitelist).order_by(ApiKeyWhitelist.created_at.desc())
        if status:
            stmt = stmt.where(ApiKeyWhitelist.status == status)
        stmt = stmt.limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def get_by_id(self, whitelist_id: str) -> ApiKeyWhitelist | None:
        return self.session.get(ApiKeyWhitelist, whitelist_id)

    def find_active_by_email(self, email: str) -> ApiKeyWhitelist | None:
        stmt = select(ApiKeyWhitelist).where(
            ApiKeyWhitelist.email == email.lower(), ApiKeyWhitelist.status == "active"
        )
        return self.session.scalar(stmt)

    def update_status(self, whitelist_id: str, data: WhitelistUpdateInput) -> ApiKeyWhitelist | None:
        whitelist = self.get_by_id(whitelist_id)
        if whitelist is None:
            return None
        whitelist.status = data.status
        whitelist.note = data.note
        whitelist.updated_by = data.updated_by
        whitelist.updated_at = datetime.now(timezone.utc)
        self.session.add(whitelist)
        self.session.flush()
        return whitelist


class SQLAlchemyApiKeyRepository(ApiKeyRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_application(self, data: ApplicationCreateInput) -> ApiKeyApplication:
        application = ApiKeyApplication(
            id=str(uuid4()),
            account=data.identity.account,
            user_id=data.user_id,
            name=data.identity.name,
            email=data.identity.email.lower(),
            department=data.identity.department,
            application_date=data.application_date,
            duration_months=data.duration_months,
            purpose=data.purpose,
            status="active",
            issued_at=data.issued_at,
            expires_at=data.expires_at,
            revoked_at=None,
            sysid=data.identity.sysid,
            created_at=data.issued_at,
            updated_at=data.issued_at,
        )
        self.session.add(application)
        self.session.flush()
        return application

    def create_key(self, data: ApiKeyCreateInput) -> ApiKey:
        key = ApiKey(
            id=str(uuid4()),
            application_id=data.application_id,
            key_hash=data.key_hash,
            key_prefix="AS-",
            length=30,
            security_level="high",
            status=data.status,
            created_at=datetime.now(timezone.utc),
        )
        self.session.add(key)
        self.session.flush()
        return key

    def list_keys(
        self,
        *,
        requester_role: str,
        requester_account: str,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ApiKeyListItem]:
        stmt = (
            select(ApiKey, ApiKeyApplication)
            .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
            .order_by(ApiKey.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if requester_role == "user":
            stmt = stmt.where(ApiKeyApplication.account == requester_account)
        if status:
            stmt = stmt.where(ApiKey.status == status)
        rows = self.session.execute(stmt).all()
        return [
            ApiKeyListItem(
                id=row.ApiKey.id,
                status=row.ApiKey.status,
                key_prefix=row.ApiKey.key_prefix,
                owner_account=row.ApiKeyApplication.account,
                owner_name=row.ApiKeyApplication.name,
                expires_at=row.ApiKeyApplication.expires_at,
            )
            for row in rows
        ]

    def get_key_detail(self, key_id: str, requester_role: str, requester_account: str) -> ApiKeyDetail | None:
        stmt = select(ApiKey, ApiKeyApplication).join(
            ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id
        )
        stmt = stmt.where(ApiKey.id == key_id)
        if requester_role == "user":
            stmt = stmt.where(ApiKeyApplication.account == requester_account)

        row = self.session.execute(stmt).first()
        if row is None:
            return None

        return ApiKeyDetail(
            id=row.ApiKey.id,
            status=row.ApiKey.status,
            key_prefix=row.ApiKey.key_prefix,
            owner_account=row.ApiKeyApplication.account,
            owner_name=row.ApiKeyApplication.name,
            purpose=row.ApiKeyApplication.purpose,
            department=row.ApiKeyApplication.department,
            application_date=row.ApiKeyApplication.application_date,
            duration_months=row.ApiKeyApplication.duration_months,
            created_at=row.ApiKey.created_at,
            expires_at=row.ApiKeyApplication.expires_at,
        )

    def revoke_key(self, key_id: str, requester_role: str, requester_account: str) -> ApiKey | None:
        stmt = select(ApiKey, ApiKeyApplication).join(
            ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id
        )
        stmt = stmt.where(ApiKey.id == key_id)
        if requester_role == "user":
            stmt = stmt.where(ApiKeyApplication.account == requester_account)

        row = self.session.execute(stmt).first()
        if row is None:
            return None

        key = row.ApiKey
        if key.status != "active":
            return None

        key.status = "revoked"
        row.ApiKeyApplication.status = "revoked"
        row.ApiKeyApplication.revoked_at = datetime.now(timezone.utc)
        row.ApiKeyApplication.updated_at = datetime.now(timezone.utc)
        self.session.add(key)
        self.session.add(row.ApiKeyApplication)
        self.session.flush()
        return key

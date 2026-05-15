from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from db.models.users import User
from db.models.whitelist import ApiKeyWhitelist
from db.repositories.interfaces import ApiKeyRepository, UserRepository, WhitelistRepository
from db.repositories.types import (
    ApiKeyAliasUpdateInput,
    ApiKeyCreateInput,
    ApiKeyDetail,
    ApiKeyListFilter,
    ApiKeyListItem,
    ApiKeySecretMaterial,
    ApiKeyUserStatisticsItem,
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

    def update_status(self, user_id: str, status: str) -> User | None:
        user = self.get_by_id(user_id)
        if not user:
            return None
        user.status = status
        user.updated_at = datetime.now(timezone.utc)
        self.session.add(user)
        self.session.flush()
        return user

    def update_preferred_locale(self, user_id: str, preferred_locale: str | None) -> User | None:
        user = self.get_by_id(user_id)
        if not user:
            return None
        user.preferred_locale = preferred_locale
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
                preferred_locale=None,
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

    def get_by_email(self, email: str) -> ApiKeyWhitelist | None:
        stmt = select(ApiKeyWhitelist).where(ApiKeyWhitelist.email == email.lower())
        return self.session.scalar(stmt)

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
            masked_key=data.masked_key,
            key_ciphertext=data.key_ciphertext,
            key_kek_version=data.key_kek_version,
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
        filters: ApiKeyListFilter,
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
        if filters.status:
            stmt = stmt.where(ApiKey.status == filters.status)
        if filters.owner_account:
            stmt = stmt.where(ApiKeyApplication.account == filters.owner_account)
        if filters.from_date:
            stmt = stmt.where(ApiKeyApplication.application_date >= filters.from_date)
        if filters.to_date:
            stmt = stmt.where(ApiKeyApplication.application_date <= filters.to_date)
        rows = self.session.execute(stmt).all()
        return [
            ApiKeyListItem(
                id=row.ApiKey.id,
                status=row.ApiKey.status,
                masked_key=row.ApiKey.masked_key,
                key_alias=row.ApiKey.key_alias,
                application_date=row.ApiKeyApplication.application_date,
                duration_months=row.ApiKeyApplication.duration_months,
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
            masked_key=row.ApiKey.masked_key,
            key_alias=row.ApiKey.key_alias,
            owner_account=row.ApiKeyApplication.account,
            owner_name=row.ApiKeyApplication.name,
            purpose=row.ApiKeyApplication.purpose,
            department=row.ApiKeyApplication.department,
            application_date=row.ApiKeyApplication.application_date,
            duration_months=row.ApiKeyApplication.duration_months,
            created_at=row.ApiKey.created_at,
            expires_at=row.ApiKeyApplication.expires_at,
        )

    def get_key_secret_material(
        self, key_id: str, requester_role: str, requester_account: str
    ) -> ApiKeySecretMaterial | None:
        stmt = select(ApiKey, ApiKeyApplication).join(
            ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id
        )
        stmt = stmt.where(ApiKey.id == key_id)
        if requester_role == "user":
            stmt = stmt.where(ApiKeyApplication.account == requester_account)

        row = self.session.execute(stmt).first()
        if row is None:
            return None

        return ApiKeySecretMaterial(
            id=row.ApiKey.id,
            status=row.ApiKey.status,
            owner_account=row.ApiKeyApplication.account,
            key_ciphertext=row.ApiKey.key_ciphertext,
            key_kek_version=row.ApiKey.key_kek_version,
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

    def update_key_alias(
        self, key_id: str, requester_role: str, requester_account: str, data: ApiKeyAliasUpdateInput
    ) -> ApiKeyDetail | None:
        stmt = select(ApiKey, ApiKeyApplication).join(
            ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id
        )
        stmt = stmt.where(ApiKey.id == key_id)
        if requester_role == "user":
            stmt = stmt.where(ApiKeyApplication.account == requester_account)

        row = self.session.execute(stmt).first()
        if row is None:
            return None

        row.ApiKey.key_alias = data.key_alias
        self.session.add(row.ApiKey)
        self.session.flush()

        return ApiKeyDetail(
            id=row.ApiKey.id,
            status=row.ApiKey.status,
            masked_key=row.ApiKey.masked_key,
            key_alias=row.ApiKey.key_alias,
            owner_account=row.ApiKeyApplication.account,
            owner_name=row.ApiKeyApplication.name,
            purpose=row.ApiKeyApplication.purpose,
            department=row.ApiKeyApplication.department,
            application_date=row.ApiKeyApplication.application_date,
            duration_months=row.ApiKeyApplication.duration_months,
            created_at=row.ApiKey.created_at,
            expires_at=row.ApiKeyApplication.expires_at,
        )

    def list_user_statistics(
        self,
        *,
        scope: str,
        q: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        sort_by: str = "total_applications",
        sort_dir: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ApiKeyUserStatisticsItem], int]:
        active_count = func.sum(case((ApiKey.status == "active", 1), else_=0)).label("active_count")
        revoked_count = func.sum(case((ApiKey.status == "revoked", 1), else_=0)).label("revoked_count")
        expired_count = func.sum(case((ApiKey.status == "expired", 1), else_=0)).label("expired_count")
        total_applications = func.count(ApiKeyApplication.id).label("total_applications")
        last_applied_at = func.max(ApiKeyApplication.application_date).label("last_applied_at")

        stmt = (
            select(
                ApiKeyApplication.account.label("owner_account"),
                ApiKeyApplication.name.label("owner_name"),
                ApiKeyApplication.email.label("owner_email"),
                func.max(ApiKeyApplication.department).label("owner_department"),
                total_applications,
                active_count,
                revoked_count,
                expired_count,
                last_applied_at,
            )
            .join(ApiKey, ApiKey.application_id == ApiKeyApplication.id)
        )

        if scope != "all":
            stmt = stmt.where(ApiKey.status == scope)
        if from_date is not None:
            stmt = stmt.where(ApiKeyApplication.application_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(ApiKeyApplication.application_date <= to_date)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                ApiKeyApplication.account.like(like)
                | ApiKeyApplication.name.like(like)
                | ApiKeyApplication.email.like(like)
            )

        stmt = stmt.group_by(ApiKeyApplication.account, ApiKeyApplication.name, ApiKeyApplication.email)

        allowed_sort_columns = {
            "owner_account": "owner_account",
            "owner_name": "owner_name",
            "owner_email": "owner_email",
            "owner_department": "owner_department",
            "total_applications": "total_applications",
            "active_count": "active_count",
            "revoked_count": "revoked_count",
            "expired_count": "expired_count",
            "last_applied_at": "last_applied_at",
        }
        sort_key = allowed_sort_columns.get(sort_by, "total_applications")
        sort_expr = stmt.selected_columns[sort_key]
        if sort_dir == "asc":
            stmt = stmt.order_by(sort_expr.asc(), stmt.selected_columns["owner_account"].asc())
        else:
            stmt = stmt.order_by(sort_expr.desc(), stmt.selected_columns["owner_account"].asc())

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = int(self.session.scalar(total_stmt) or 0)

        stmt = stmt.limit(limit).offset(offset)
        rows = self.session.execute(stmt).all()

        return (
            [
                ApiKeyUserStatisticsItem(
                    owner_account=row.owner_account,
                    owner_name=row.owner_name,
                    owner_email=row.owner_email,
                    owner_department=row.owner_department or "",
                    total_applications=int(row.total_applications),
                    active_count=int(row.active_count or 0),
                    revoked_count=int(row.revoked_count or 0),
                    expired_count=int(row.expired_count or 0),
                    last_applied_at=row.last_applied_at,
                )
                for row in rows
            ],
            total,
        )

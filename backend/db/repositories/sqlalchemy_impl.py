from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from db.models.admins import Admin
from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from db.models.whitelist import ApiKeyWhitelist
from db.repositories.interfaces import ApiKeyRepository, WhitelistRepository
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


class SQLAlchemyAdminRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_id(self, admin_id: int) -> Admin | None:
        return self.session.get(Admin, admin_id)

    def get_by_account(self, account: str) -> Admin | None:
        stmt = select(Admin).where(Admin.account == account)
        return self.session.scalar(stmt)

    def get_active_by_id(self, admin_id: int) -> Admin | None:
        stmt = select(Admin).where(Admin.id == admin_id, Admin.status == "active")
        return self.session.scalar(stmt)

    def search(self, keyword: str, limit: int = 20) -> list[Admin]:
        like = f"%{keyword}%"
        where_clause = Admin.account.like(like) | Admin.email.like(like) | Admin.name.like(like)
        if keyword.isdigit():
            where_clause = where_clause | (Admin.id == int(keyword))
        stmt = select(Admin).where(where_clause).limit(limit)
        return list(self.session.scalars(stmt).all())

    def list_all(self, limit: int = 100, offset: int = 0) -> list[Admin]:
        stmt = (
            select(Admin)
            .order_by(Admin.status.asc(), Admin.updated_at.desc(), Admin.created_at.desc(), Admin.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(stmt).all())

    def list_active_emails(self) -> list[str]:
        stmt = select(Admin.email).where(Admin.status == "active")
        rows = self.session.execute(stmt).all()
        return [str(row[0]).lower() for row in rows if row[0]]

    def upsert_from_auth(self, identity: AuthIdentity, *, created_by: str) -> Admin:
        admin = self.get_by_id(identity.sysid) or self.get_by_account(identity.account)
        now = datetime.now(timezone.utc)
        if admin is None:
            admin = Admin(
                id=identity.sysid,
                account=identity.account,
                email=identity.email.lower(),
                name=identity.name,
                department=identity.department,
                status="active",
                created_by=created_by,
                updated_by=created_by,
                created_at=now,
                updated_at=now,
            )
        else:
            admin.account = identity.account
            admin.name = identity.name
            admin.email = identity.email.lower()
            admin.department = identity.department
            admin.status = "active"
            admin.updated_by = created_by
            admin.updated_at = now
        self.session.add(admin)
        self.session.flush()
        return admin

    def create(self, *, admin_id: int, account: str, name: str, email: str, department: str, created_by: str) -> Admin:
        now = datetime.now(timezone.utc)
        admin = Admin(
            id=admin_id,
            account=account,
            email=email.lower(),
            name=name,
            department=department,
            status="active",
            created_by=created_by,
            updated_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(admin)
        self.session.flush()
        return admin

    def set_status(self, admin_id: int, *, status: str, updated_by: str) -> Admin | None:
        admin = self.get_by_id(admin_id)
        if admin is None:
            return None
        admin.status = status
        admin.updated_by = updated_by
        admin.updated_at = datetime.now(timezone.utc)
        self.session.add(admin)
        self.session.flush()
        return admin

    def delete(self, admin_id: int) -> Admin | None:
        admin = self.get_by_id(admin_id)
        if admin is None:
            return None
        self.session.delete(admin)
        self.session.flush()
        return admin


class SQLAlchemyWhitelistRepository(WhitelistRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, data: WhitelistCreateInput) -> ApiKeyWhitelist:
        now = datetime.now(timezone.utc)
        whitelist = ApiKeyWhitelist(
            id=data.id,
            sysid=data.sysid,
            account=data.account,
            name=data.name,
            email=data.email.lower() if data.email else None,
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

    def get_by_sysid(self, sysid: int) -> ApiKeyWhitelist | None:
        stmt = select(ApiKeyWhitelist).where(ApiKeyWhitelist.sysid == sysid)
        return self.session.scalar(stmt)

    def find_active_by_sysid(self, sysid: int) -> ApiKeyWhitelist | None:
        stmt = select(ApiKeyWhitelist).where(
            ApiKeyWhitelist.sysid == sysid, ApiKeyWhitelist.status == "active"
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

    def delete(self, whitelist_id: str) -> ApiKeyWhitelist | None:
        whitelist = self.get_by_id(whitelist_id)
        if whitelist is None:
            return None
        self.session.delete(whitelist)
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
            limit_strategy=data.limit_strategy,
            max_budget=data.max_budget,
            budget_duration=data.budget_duration,
            tpm_limit=data.tpm_limit,
            rpm_limit=data.rpm_limit,
            issuance_status=data.issuance_status,
            pending_issued_at=data.pending_issued_at,
            status="active",
            issued_at=data.issued_at,
            expires_at=data.expires_at,
            revoked_at=None,
            sysid=data.identity.sysid,
            is_proxy_submission=data.is_proxy_submission,
            operator_account=data.operator_identity.account,
            operator_name=data.operator_identity.name,
            operator_email=data.operator_identity.email.lower(),
            operator_department=data.operator_identity.department,
            operator_sysid=data.operator_identity.sysid,
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
            renewed_to_key_id=None,
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
    ) -> tuple[list[ApiKeyListItem], int]:
        now_utc = datetime.now(timezone.utc)
        effective_status = case(
            (
                (ApiKey.status == "active") & (ApiKeyApplication.expires_at < now_utc),
                "expired",
            ),
            else_=ApiKey.status,
        ).label("effective_status")
        base_stmt = (
            select(ApiKey, ApiKeyApplication, effective_status)
            .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
        )
        if requester_role == "user":
            base_stmt = base_stmt.where(ApiKeyApplication.account == requester_account)
            base_stmt = base_stmt.where(ApiKey.renewed_to_key_id.is_(None))
        if filters.status:
            base_stmt = base_stmt.where(effective_status == filters.status)
        if filters.owner_account:
            base_stmt = base_stmt.where(ApiKeyApplication.account == filters.owner_account)
        if filters.from_date:
            base_stmt = base_stmt.where(ApiKeyApplication.application_date >= filters.from_date)
        if filters.to_date:
            base_stmt = base_stmt.where(ApiKeyApplication.application_date <= filters.to_date)

        total_stmt = select(func.count()).select_from(base_stmt.order_by(None).subquery())
        total = int(self.session.scalar(total_stmt) or 0)

        stmt = base_stmt.order_by(ApiKey.created_at.desc()).limit(limit).offset(offset)
        rows = self.session.execute(stmt).all()
        return (
            [
                ApiKeyListItem(
                    id=row.ApiKey.id,
                    status=row.effective_status,
                    masked_key=row.ApiKey.masked_key,
                    key_alias=row.ApiKey.key_alias,
                    application_date=row.ApiKeyApplication.application_date,
                    duration_months=row.ApiKeyApplication.duration_months,
                    owner_account=row.ApiKeyApplication.account,
                    owner_name=row.ApiKeyApplication.name,
                    expires_at=row.ApiKeyApplication.expires_at,
                    expiration_notice_sent_at=row.ApiKey.expiration_notice_sent_at,
                )
                for row in rows
            ],
            total,
        )

    def get_key_detail(self, key_id: str, requester_role: str, requester_account: str) -> ApiKeyDetail | None:
        now_utc = datetime.now(timezone.utc)
        effective_status = case(
            (
                (ApiKey.status == "active") & (ApiKeyApplication.expires_at < now_utc),
                "expired",
            ),
            else_=ApiKey.status,
        ).label("effective_status")
        stmt = select(ApiKey, ApiKeyApplication, effective_status).join(
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
            status=row.effective_status,
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
            expiration_notice_sent_at=row.ApiKey.expiration_notice_sent_at,
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
        now_utc = datetime.now(timezone.utc)
        effective_status = case(
            (
                (ApiKey.status == "active") & (ApiKeyApplication.expires_at < now_utc),
                "expired",
            ),
            else_=ApiKey.status,
        )
        active_count = func.sum(case((effective_status == "active", 1), else_=0)).label("active_count")
        revoked_count = func.sum(case((effective_status == "revoked", 1), else_=0)).label("revoked_count")
        expired_count = func.sum(case((effective_status == "expired", 1), else_=0)).label("expired_count")
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
            stmt = stmt.where(effective_status == scope)
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

        sort_expressions = {
            "owner_account": ApiKeyApplication.account,
            "owner_name": ApiKeyApplication.name,
            "owner_email": ApiKeyApplication.email,
            "owner_department": func.max(ApiKeyApplication.department),
            "total_applications": total_applications,
            "active_count": active_count,
            "revoked_count": revoked_count,
            "expired_count": expired_count,
            "last_applied_at": last_applied_at,
        }
        sort_expr = sort_expressions.get(sort_by, total_applications)
        if sort_dir == "asc":
            stmt = stmt.order_by(sort_expr.asc(), ApiKeyApplication.account.asc())
        else:
            stmt = stmt.order_by(sort_expr.desc(), ApiKeyApplication.account.asc())

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

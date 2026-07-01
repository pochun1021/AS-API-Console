from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Select, and_, case, distinct, func, literal, select
from sqlalchemy.orm import Session, aliased

from db.models.api_key_usage_snapshots import ApiKeyUsageSnapshot
from db.models.admins import Admin
from db.models.announcement import Announcement
from db.models.api_keys import ApiKey
from db.models.applications import ApiKeyApplication
from db.models.whitelist import ApiKeyWhitelist
from db.repositories.interfaces import AnnouncementRepository, ApiKeyRepository, WhitelistRepository
from db.repositories.types import (
    AdminListFilter,
    AnnouncementCreateInput,
    AnnouncementListFilter,
    AnnouncementUpdateInput,
    ApiKeyAliasUpdateInput,
    ApiKeyCreateInput,
    ApiKeyDetail,
    ApiKeyListFilter,
    ApiKeyListItem,
    ApiKeySecretMaterial,
    ApiKeyUsageBucketItem,
    ApiKeyUsageSeriesItem,
    ApiKeyUsageTotal,
    ApiKeyUserStatisticsFilter,
    ApiKeyUserStatisticsItem,
    ApplicationCreateInput,
    AuthIdentity,
    WhitelistCreateInput,
    WhitelistListFilter,
    WhitelistUpdateInput,
)


def _contains_ci(column, value: str):
    return func.lower(column).like(f"%{value.lower()}%")


class SQLAlchemyAnnouncementRepository(AnnouncementRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _apply_list_filters(stmt: Select, filters: AnnouncementListFilter) -> Select:
        if filters.title:
            stmt = stmt.where(_contains_ci(Announcement.title, filters.title))
        if filters.status:
            stmt = stmt.where(Announcement.status == filters.status)
        if filters.publish_from_from:
            stmt = stmt.where(Announcement.publish_from >= filters.publish_from_from)
        if filters.publish_from_to:
            stmt = stmt.where(Announcement.publish_from <= filters.publish_from_to)
        if filters.publish_to_from:
            stmt = stmt.where(Announcement.publish_to >= filters.publish_to_from)
        if filters.publish_to_to:
            stmt = stmt.where(Announcement.publish_to <= filters.publish_to_to)
        if filters.updated_from:
            stmt = stmt.where(Announcement.updated_at >= filters.updated_from)
        if filters.updated_to:
            stmt = stmt.where(Announcement.updated_at <= filters.updated_to)
        return stmt

    def create(self, data: AnnouncementCreateInput) -> Announcement:
        now = datetime.now(timezone.utc)
        announcement = Announcement(
            id=data.id,
            title=data.title,
            body=data.body,
            status=data.status,
            publish_from=data.publish_from,
            publish_to=data.publish_to,
            created_by=data.created_by,
            updated_by=data.created_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(announcement)
        self.session.flush()
        return announcement

    def list(
        self,
        filters: AnnouncementListFilter,
        *,
        active_only: bool = False,
        now: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Announcement], int]:
        sortable_columns = {
            "title": Announcement.title,
            "status": Announcement.status,
            "publish_from": Announcement.publish_from,
            "publish_to": Announcement.publish_to,
            "created_at": Announcement.created_at,
            "updated_at": Announcement.updated_at,
        }
        sort_column = sortable_columns.get(filters.sort_by, Announcement.updated_at)
        sort_dir = "asc" if filters.sort_dir == "asc" else "desc"

        stmt: Select[tuple[Announcement]] = select(Announcement)
        if active_only:
            current_time = now or datetime.now(timezone.utc)
            stmt = stmt.where(
                Announcement.status == "active",
                (Announcement.publish_from.is_(None) | (Announcement.publish_from <= current_time)),
                (Announcement.publish_to.is_(None) | (Announcement.publish_to >= current_time)),
            )
        stmt = self._apply_list_filters(stmt, filters)
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = int(self.session.scalar(count_stmt) or 0)

        if active_only and filters.sort_by == "updated_at" and filters.sort_dir == "desc":
            stmt = stmt.order_by(
                case((Announcement.publish_from.is_(None), 1), else_=0).asc(),
                Announcement.publish_from.desc(),
                Announcement.updated_at.desc(),
                Announcement.id.desc(),
            )
        elif sort_dir == "asc":
            stmt = stmt.order_by(sort_column.asc(), Announcement.id.asc())
        else:
            stmt = stmt.order_by(sort_column.desc(), Announcement.id.desc())

        stmt = stmt.limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all()), total

    def get_by_id(self, announcement_id: str) -> Announcement | None:
        return self.session.get(Announcement, announcement_id)

    def update(self, announcement_id: str, data: AnnouncementUpdateInput) -> Announcement | None:
        announcement = self.get_by_id(announcement_id)
        if announcement is None:
            return None
        announcement.title = data.title
        announcement.body = data.body
        announcement.status = data.status
        announcement.publish_from = data.publish_from
        announcement.publish_to = data.publish_to
        announcement.updated_by = data.updated_by
        announcement.updated_at = datetime.now(timezone.utc)
        self.session.add(announcement)
        self.session.flush()
        return announcement

    def delete(self, announcement_id: str) -> Announcement | None:
        announcement = self.get_by_id(announcement_id)
        if announcement is None:
            return None
        self.session.delete(announcement)
        self.session.flush()
        return announcement


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

    @staticmethod
    def _apply_list_filters(stmt: Select, filters: AdminListFilter) -> Select:
        if filters.status:
            stmt = stmt.where(Admin.status == filters.status)
        if filters.sysid is not None:
            stmt = stmt.where(Admin.id == filters.sysid)
        if filters.account:
            stmt = stmt.where(_contains_ci(Admin.account, filters.account))
        if filters.name:
            stmt = stmt.where(_contains_ci(Admin.name, filters.name))
        if filters.email:
            stmt = stmt.where(_contains_ci(Admin.email, filters.email))
        if filters.created_from:
            stmt = stmt.where(Admin.created_at >= filters.created_from)
        if filters.created_to:
            stmt = stmt.where(Admin.created_at <= filters.created_to)
        if filters.updated_from:
            stmt = stmt.where(Admin.updated_at >= filters.updated_from)
        if filters.updated_to:
            stmt = stmt.where(Admin.updated_at <= filters.updated_to)
        return stmt

    def list(
        self,
        filters: AdminListFilter,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Admin], int]:
        sortable_columns = {
            "sysid": Admin.id,
            "account": Admin.account,
            "name": Admin.name,
            "email": Admin.email,
            "status": Admin.status,
            "created_at": Admin.created_at,
            "updated_at": Admin.updated_at,
        }
        sort_column = sortable_columns.get(filters.sort_by, Admin.created_at)
        sort_dir = "asc" if filters.sort_dir == "asc" else "desc"

        stmt: Select[tuple[Admin]] = select(Admin)
        stmt = self._apply_list_filters(stmt, filters)
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = int(self.session.scalar(count_stmt) or 0)

        if sort_dir == "asc":
            stmt = stmt.order_by(sort_column.asc(), Admin.id.asc())
        else:
            stmt = stmt.order_by(sort_column.desc(), Admin.id.desc())

        stmt = stmt.limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all()), total

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

    @staticmethod
    def _apply_list_filters(stmt: Select, filters: WhitelistListFilter) -> Select:
        if filters.status:
            stmt = stmt.where(ApiKeyWhitelist.status == filters.status)
        if filters.sysid is not None:
            stmt = stmt.where(ApiKeyWhitelist.sysid == filters.sysid)
        if filters.account:
            stmt = stmt.where(_contains_ci(ApiKeyWhitelist.account, filters.account))
        if filters.name:
            stmt = stmt.where(_contains_ci(ApiKeyWhitelist.name, filters.name))
        if filters.email:
            stmt = stmt.where(_contains_ci(ApiKeyWhitelist.email, filters.email))
        if filters.created_from:
            stmt = stmt.where(ApiKeyWhitelist.created_at >= filters.created_from)
        if filters.created_to:
            stmt = stmt.where(ApiKeyWhitelist.created_at <= filters.created_to)
        if filters.updated_from:
            stmt = stmt.where(ApiKeyWhitelist.updated_at >= filters.updated_from)
        if filters.updated_to:
            stmt = stmt.where(ApiKeyWhitelist.updated_at <= filters.updated_to)
        return stmt

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

    def list(
        self,
        filters: WhitelistListFilter,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ApiKeyWhitelist], int]:
        sortable_columns = {
            "sysid": ApiKeyWhitelist.sysid,
            "account": ApiKeyWhitelist.account,
            "name": ApiKeyWhitelist.name,
            "email": ApiKeyWhitelist.email,
            "status": ApiKeyWhitelist.status,
            "created_at": ApiKeyWhitelist.created_at,
            "updated_at": ApiKeyWhitelist.updated_at,
        }
        sort_column = sortable_columns.get(filters.sort_by, ApiKeyWhitelist.created_at)
        sort_dir = "asc" if filters.sort_dir == "asc" else "desc"

        stmt: Select[tuple[ApiKeyWhitelist]] = select(ApiKeyWhitelist)
        stmt = self._apply_list_filters(stmt, filters)
        count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
        total = int(self.session.scalar(count_stmt) or 0)

        if sort_dir == "asc":
            stmt = stmt.order_by(sort_column.asc(), ApiKeyWhitelist.id.asc())
        else:
            stmt = stmt.order_by(sort_column.desc(), ApiKeyWhitelist.id.desc())

        stmt = stmt.limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all()), total

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
            name=data.identity.name,
            email=data.identity.email.lower(),
            department=data.identity.department,
            application_date=data.application_date,
            duration_days=data.duration_days,
            original_duration_days=data.original_duration_days,
            purpose=data.purpose,
            max_budget=data.max_budget,
            budget_duration=data.budget_duration,
            tpm_limit=data.tpm_limit,
            rpm_limit=data.rpm_limit,
            max_parallel_requests=data.max_parallel_requests,
            status="active",
            issued_at=data.issued_at,
            expires_at=data.expires_at,
            revoked_at=None,
            sysid=data.identity.sysid,
            is_proxy_submission=data.is_proxy_submission,
            proxy_operator_account=data.proxy_operator_account,
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
            key_prefix=data.key_prefix,
            masked_key=data.masked_key,
            key_alias=data.key_alias,
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

    def alias_exists(self, key_alias: str, *, exclude_key_id: str | None = None) -> bool:
        effective_default_alias = literal("for_") + ApiKeyApplication.account
        stmt = (
            select(ApiKey.id)
            .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
            .where(
                (ApiKey.key_alias == key_alias)
                | ((ApiKey.key_alias.is_(None)) & (effective_default_alias == key_alias))
            )
        )
        if exclude_key_id:
            stmt = stmt.where(ApiKey.id != exclude_key_id)
        return self.session.scalar(stmt.limit(1)) is not None

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
        effective_key_alias = func.coalesce(ApiKey.key_alias, literal("for_") + ApiKeyApplication.account).label("effective_key_alias")
        base_stmt = (
            select(ApiKey, ApiKeyApplication, effective_status, effective_key_alias)
            .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
        )
        if requester_role == "user":
            base_stmt = base_stmt.where(ApiKeyApplication.account == requester_account)
            base_stmt = base_stmt.where(ApiKey.renewed_to_key_id.is_(None))
        if filters.status:
            base_stmt = base_stmt.where(effective_status == filters.status)
        if filters.owner_account:
            base_stmt = base_stmt.where(_contains_ci(ApiKeyApplication.account, filters.owner_account))
        if filters.owner_name:
            base_stmt = base_stmt.where(_contains_ci(ApiKeyApplication.name, filters.owner_name))
        if filters.key_alias:
            base_stmt = base_stmt.where(_contains_ci(effective_key_alias, filters.key_alias))
        if filters.application_date_from:
            base_stmt = base_stmt.where(ApiKeyApplication.application_date >= filters.application_date_from)
        if filters.application_date_to:
            base_stmt = base_stmt.where(ApiKeyApplication.application_date <= filters.application_date_to)
        if filters.issued_at_from:
            base_stmt = base_stmt.where(ApiKeyApplication.issued_at >= filters.issued_at_from)
        if filters.issued_at_to:
            base_stmt = base_stmt.where(ApiKeyApplication.issued_at <= filters.issued_at_to)
        if filters.expires_from:
            base_stmt = base_stmt.where(ApiKeyApplication.expires_at >= filters.expires_from)
        if filters.expires_to:
            base_stmt = base_stmt.where(ApiKeyApplication.expires_at <= filters.expires_to)

        total_stmt = select(func.count()).select_from(base_stmt.order_by(None).subquery())
        total = int(self.session.scalar(total_stmt) or 0)

        sort_expressions = {
            "application_date": ApiKeyApplication.application_date,
            "duration_days": ApiKeyApplication.duration_days,
            "status": effective_status,
            "expires_at": ApiKeyApplication.expires_at,
            "masked_key": ApiKey.masked_key,
            "key_alias": effective_key_alias,
            "owner_account": ApiKeyApplication.account,
            "owner_name": ApiKeyApplication.name,
            "created_at": ApiKey.created_at,
        }
        sort_expr = sort_expressions.get(filters.sort_by, ApiKey.created_at)
        if filters.sort_dir == "asc":
            order_by = [sort_expr.asc(), ApiKey.id.asc()]
        else:
            order_by = [sort_expr.desc(), ApiKey.id.desc()]

        stmt = base_stmt.order_by(*order_by).limit(limit).offset(offset)
        rows = self.session.execute(stmt).all()
        items: list[ApiKeyListItem] = []
        for row in rows:
            items.append(
                ApiKeyListItem(
                    id=row.ApiKey.id,
                    status=row.effective_status,
                    masked_key=row.ApiKey.masked_key,
                    key_alias=row.ApiKey.key_alias,
                    created_at=row.ApiKey.created_at,
                    application_date=row.ApiKeyApplication.application_date,
                    duration_days=row.ApiKeyApplication.duration_days,
                    original_duration_days=row.ApiKeyApplication.original_duration_days,
                    owner_account=row.ApiKeyApplication.account,
                    owner_name=row.ApiKeyApplication.name,
                    expires_at=row.ApiKeyApplication.expires_at,
                    expiration_notice_sent_at=row.ApiKey.expiration_notice_sent_at,
                    max_budget=row.ApiKeyApplication.max_budget,
                    tpm_limit=row.ApiKeyApplication.tpm_limit,
                    rpm_limit=row.ApiKeyApplication.rpm_limit,
                    max_parallel_requests=row.ApiKeyApplication.max_parallel_requests,
                    usage_spend=float(row.ApiKey.usage_spend) if row.ApiKey.usage_spend is not None else None,
                    usage_prompt_tokens=row.ApiKey.usage_prompt_tokens,
                    usage_completion_tokens=row.ApiKey.usage_completion_tokens,
                    usage_total_tokens=row.ApiKey.usage_total_tokens,
                    usage_budget_reset_at=row.ApiKey.usage_budget_reset_at,
                    usage_synced_at=row.ApiKey.usage_synced_at,
                )
            )
        return (items, total)

    def list_usage_series(
        self,
        *,
        key_id: str,
        granularity: str,
        bucket_start_from: datetime,
        bucket_start_to: datetime,
    ) -> list[ApiKeyUsageSeriesItem]:
        stmt = (
            select(ApiKeyUsageSnapshot)
            .where(
                ApiKeyUsageSnapshot.api_key_id == key_id,
                ApiKeyUsageSnapshot.bucket_granularity == granularity,
                ApiKeyUsageSnapshot.bucket_start_utc.is_not(None),
                ApiKeyUsageSnapshot.bucket_end_utc.is_not(None),
                ApiKeyUsageSnapshot.bucket_start_utc >= bucket_start_from,
                ApiKeyUsageSnapshot.bucket_start_utc < bucket_start_to,
            )
            .order_by(ApiKeyUsageSnapshot.bucket_start_utc.asc(), ApiKeyUsageSnapshot.id.asc())
        )
        rows = self.session.scalars(stmt).all()
        return [
            ApiKeyUsageSeriesItem(
                bucket_start_utc=row.bucket_start_utc,
                bucket_end_utc=row.bucket_end_utc,
                prompt_tokens=row.prompt_tokens,
                completion_tokens=row.completion_tokens,
                total_tokens=row.total_tokens,
                spend=float(row.spend) if row.spend is not None else None,
            )
            for row in rows
            if row.bucket_start_utc is not None and row.bucket_end_utc is not None
        ]

    def list_usage_buckets_for_keys(
        self,
        *,
        key_ids: list[str],
        granularity: str,
        bucket_start_from: datetime,
        bucket_start_to: datetime,
    ) -> list[ApiKeyUsageBucketItem]:
        if not key_ids:
            return []

        stmt = (
            select(ApiKeyUsageSnapshot)
            .where(
                ApiKeyUsageSnapshot.api_key_id.in_(key_ids),
                ApiKeyUsageSnapshot.bucket_granularity == granularity,
                ApiKeyUsageSnapshot.bucket_start_utc.is_not(None),
                ApiKeyUsageSnapshot.bucket_end_utc.is_not(None),
                ApiKeyUsageSnapshot.bucket_end_utc > bucket_start_from,
                ApiKeyUsageSnapshot.bucket_start_utc < bucket_start_to,
            )
            .order_by(
                ApiKeyUsageSnapshot.api_key_id.asc(),
                ApiKeyUsageSnapshot.bucket_start_utc.asc(),
                ApiKeyUsageSnapshot.id.asc(),
            )
        )
        rows = self.session.scalars(stmt).all()
        return [
            ApiKeyUsageBucketItem(
                api_key_id=row.api_key_id,
                bucket_start_utc=row.bucket_start_utc,
                bucket_end_utc=row.bucket_end_utc,
                prompt_tokens=row.prompt_tokens,
                completion_tokens=row.completion_tokens,
                total_tokens=row.total_tokens,
                spend=float(row.spend) if row.spend is not None else None,
            )
            for row in rows
            if row.bucket_start_utc is not None and row.bucket_end_utc is not None
        ]

    def get_usage_total(
        self,
        *,
        requester_role: str,
        requester_account: str,
    ) -> ApiKeyUsageTotal:
        usage_stmt = (
            select(
                func.coalesce(func.sum(ApiKeyUsageSnapshot.prompt_tokens), 0),
                func.coalesce(func.sum(ApiKeyUsageSnapshot.completion_tokens), 0),
                func.coalesce(func.sum(ApiKeyUsageSnapshot.total_tokens), 0),
            )
            .select_from(ApiKeyUsageSnapshot)
            .join(ApiKey, ApiKey.id == ApiKeyUsageSnapshot.api_key_id)
            .join(ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id)
        )
        key_count_stmt = select(func.count(distinct(ApiKey.id))).select_from(ApiKey).join(
            ApiKeyApplication, ApiKey.application_id == ApiKeyApplication.id
        )
        if requester_role == "user":
            usage_stmt = usage_stmt.where(ApiKeyApplication.account == requester_account)
            usage_stmt = usage_stmt.where(ApiKey.renewed_to_key_id.is_(None))
            key_count_stmt = key_count_stmt.where(ApiKeyApplication.account == requester_account)
            key_count_stmt = key_count_stmt.where(ApiKey.renewed_to_key_id.is_(None))
        row = self.session.execute(usage_stmt).one()
        key_count = int(self.session.scalar(key_count_stmt) or 0)
        return ApiKeyUsageTotal(
            prompt_tokens=int(row[0] or 0),
            completion_tokens=int(row[1] or 0),
            total_tokens=int(row[2] or 0),
            key_count=key_count,
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
            duration_days=row.ApiKeyApplication.duration_days,
            original_duration_days=row.ApiKeyApplication.original_duration_days,
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
            duration_days=row.ApiKeyApplication.duration_days,
            original_duration_days=row.ApiKeyApplication.original_duration_days,
            created_at=row.ApiKey.created_at,
            expires_at=row.ApiKeyApplication.expires_at,
            expiration_notice_sent_at=row.ApiKey.expiration_notice_sent_at,
        )

    def list_user_statistics(
        self,
        *,
        scope: str,
        filters: ApiKeyUserStatisticsFilter,
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
        if filters.from_date is not None:
            stmt = stmt.where(ApiKeyApplication.application_date >= filters.from_date)
        if filters.to_date is not None:
            stmt = stmt.where(ApiKeyApplication.application_date <= filters.to_date)
        if filters.q:
            stmt = stmt.where(
                _contains_ci(ApiKeyApplication.account, filters.q)
                | _contains_ci(ApiKeyApplication.name, filters.q)
                | _contains_ci(ApiKeyApplication.email, filters.q)
            )
        if filters.owner_account:
            stmt = stmt.where(_contains_ci(ApiKeyApplication.account, filters.owner_account))
        if filters.owner_name:
            stmt = stmt.where(_contains_ci(ApiKeyApplication.name, filters.owner_name))
        if filters.owner_email:
            stmt = stmt.where(_contains_ci(ApiKeyApplication.email, filters.owner_email))
        if filters.owner_department:
            stmt = stmt.where(_contains_ci(ApiKeyApplication.department, filters.owner_department))

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

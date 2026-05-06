# DB Runbook

## 目的
本文件定義 AS API Console 後端資料層的實作現況與操作流程，包含：
- Schema 實作對照
- Migration 指令與日常流程
- 升級後驗證
- 常見問題排除

產品契約仍以 `docs/SPEC.md` 為準；本文件是工程執行與維運手冊。

## 技術與版本現況
- ORM：SQLAlchemy 2.x
- Migration：Alembic
- MVP 資料庫：SQLite（保留 PostgreSQL 相容設計）
- Alembic path：`backend/alembic.ini`
- Migration 目錄：`backend/db/migrations/versions`
- 目前 head revision：`0002_create_core_tables`

## Schema 實作對照

### `users`
- 核心欄位：`id`, `account`, `email`, `name`, `role`, `status`, `created_at`, `updated_at`
- 約束：
  - `account` unique
  - `email` unique
  - `role in ('user', 'admin')`
  - `status in ('active', 'inactive')`

### `api_key_whitelist`
- 核心欄位：`id`, `email`, `status`, `note`, `created_by`, `updated_by`, `created_at`, `updated_at`
- 約束：
  - `email` unique
  - `status in ('active', 'inactive')`

### `api_key_applications`
- 核心欄位：`id`, `account`, `user_id`, `name`, `email`, `department`, `application_date`, `duration_months`, `purpose`, `status`, `issued_at`, `expires_at`, `revoked_at`, `sysid`, `created_at`, `updated_at`
- 關聯：`user_id -> users.id`
- 約束：
  - `duration_months in (1, 6, 12)`
  - `status in ('active', 'revoked', 'expired')`

### `api_keys`
- 核心欄位：`id`, `application_id`, `key_hash`, `key_prefix`, `length`, `security_level`, `status`, `created_at`
- 關聯：`application_id -> api_key_applications.id`（unique）
- 約束：
  - `status in ('active', 'revoked', 'expired')`
  - `length = 30`
  - `security_level = 'high'`
- 注意：資料庫僅保存 `key_hash`，不保存明文 API key。

## Migration 操作

### 本地常用指令
```bash
cd backend
. .venv/bin/activate

alembic current
alembic history
alembic upgrade head
alembic downgrade -1
```

### 新增 migration 標準流程
1. 修改 SQLAlchemy models（`backend/db/models`）。
2. 產生 revision：
```bash
cd backend
. .venv/bin/activate
alembic revision -m "your message"
```
3. 編輯 revision 內容（建表/索引/約束/資料修補）。
4. 執行升級與驗證：
```bash
alembic upgrade head
alembic current
```
5. 確認 schema 與 `docs/SPEC.md` 契約一致後再提交。

## 升級後驗證

### 1) revision 檢查
```bash
cd backend
. .venv/bin/activate
alembic current
```
預期：顯示 `0002_create_core_tables (head)` 或更新後最新 head。

### 2) 表存在檢查（SQLite）
```bash
cd backend
sqlite3 as_api_console.db ".tables"
```
預期至少包含：
- `users`
- `api_key_whitelist`
- `api_key_applications`
- `api_keys`

### 3) 明文 key 安全檢查
- `api_keys` 表不應存在 plaintext 欄位。
- 僅可有 `key_hash` 作為金鑰儲存欄位。

## 常見問題

### `target database is not up to date`
- 先確認 migration 分支是否一致：
```bash
alembic history
alembic current
```
- 若本機為舊版，先 `alembic upgrade head`。

### revision 衝突（多人同時開發）
- 先 `git pull` 同步最新 migration。
- 視情況新增 merge revision，再升級確認。

### 本地 DB 要重建
- 僅限本地開發環境可重建，避免誤刪正式資料。
- 重建後需重新執行：
```bash
alembic upgrade head
```

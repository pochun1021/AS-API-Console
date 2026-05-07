# DB Runbook

## 目的
本文件定義 AS API Console 後端資料層的實作現況與操作流程，包含：
- Schema 實作對照
- Migration 指令與日常流程
- 升級後驗證
- 常見問題排除

產品契約仍以 `docs/SPEC.md` 為準；本文件是工程執行與維運手冊。
若本文件與 `docs/SPEC.md` 描述差異，應以 `docs/SPEC.md` 為準，並回補同步文件文字。

## 技術與版本現況
- ORM：SQLAlchemy 2.x
- Migration：Alembic
- MVP 資料庫：MariaDB（保留 PostgreSQL 相容設計）
- Python MariaDB driver：`mariadb`（需先安裝 MariaDB Connector/C，確保 `mariadb_config` 可用）
- Alembic path：`backend/alembic.ini`
- Migration 目錄：`backend/db/migrations/versions`
- 目前 head revision：`0002_create_core_tables`

## Schema 實作對照

### `users`
- 核心欄位：`id`, `account`, `email`, `name`, `role`, `status`, `created_at`, `updated_at`
- `id` 直接使用 auth context 的 `sysid`（MVP 唯一身分鍵）；API `GET /api/v1/users` 回傳 `sysid` 時，值等於 `id`
- 契約映射：auth identity source of truth 為 `account`、`name`、`email`、`department`、`sysid`（其中 `sysid = users.id`）
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
export DATABASE_URL='mariadb+mariadbconnector://<user>:<password>@<host>:3306/as_api_console'

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
export DATABASE_URL='mariadb+mariadbconnector://<user>:<password>@<host>:3306/as_api_console'
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
export DATABASE_URL='mariadb+mariadbconnector://<user>:<password>@<host>:3306/as_api_console'
alembic current
```
預期：顯示 `0002_create_core_tables (head)` 或更新後最新 head。

### 2) 表存在檢查（MariaDB）
```bash
mariadb -h <host> -u <user> -p as_api_console -e "SHOW TABLES;"
```
預期至少包含：
- `users`
- `api_key_whitelist`
- `api_key_applications`
- `api_keys`

### 3) 明文 key 安全檢查
- `api_keys` 表不應存在 plaintext 欄位。
- 僅可有 `key_hash` 作為金鑰儲存欄位。

## 測試資料（seed）操作

### 前置條件
- 已完成 migration 且 schema 為最新版本（`alembic upgrade head`）。
- `DATABASE_URL` 已正確設定並可連線。
- 於 `backend` 目錄執行指令。

### 指令
- 重建小型測試資料（預設模式，先清除既有 seed 範圍再重建）：
```bash
cd backend
uv run python scripts/seed_test_data.py
```
- 追加小型測試資料（不清除既有 seed 範圍）：
```bash
cd backend
uv run python scripts/seed_test_data.py --no-reset
```

### 寫入範圍（small）
- `users`：8 筆（含 2 位 admin seed + 6 位 user seed）
- `api_key_whitelist`：8 筆（含 active/inactive）
- `api_key_applications`：20 筆（含 `active|revoked|expired`）
- `api_keys`：20 筆（僅 `key_hash`，不含明文）

### 執行結果判讀
- 成功時輸出：
```text
Seed completed: users=8, whitelists=8, applications=20, api_keys=20, reset=<True|False>
```
- `reset=True`：代表先清除 seed 範圍再重建。
- `reset=False`：代表追加模式（`--no-reset`）。

### 驗證方式
1. 筆數驗證（MariaDB）：
```bash
mariadb -h <host> -u <user> -p as_api_console -e "
SELECT 'users' AS tbl, COUNT(*) AS cnt FROM users
UNION ALL
SELECT 'api_key_whitelist', COUNT(*) FROM api_key_whitelist
UNION ALL
SELECT 'api_key_applications', COUNT(*) FROM api_key_applications
UNION ALL
SELECT 'api_keys', COUNT(*) FROM api_keys;
"
```
2. 狀態分佈驗證：
```bash
mariadb -h <host> -u <user> -p as_api_console -e "
SELECT status, COUNT(*) FROM api_keys GROUP BY status ORDER BY status;
"
```
3. 安全驗證：
- `api_keys` 僅保存 `key_hash`，不得新增任何明文 key 欄位或查詢路徑。

### 注意事項
- 不加 `--no-reset` 時，腳本會清除既有 seed 範圍（指定 seed users 對應的 applications/keys 與 seed whitelist/users）後重建。
- 使用 `--no-reset` 連續執行可能因 unique 約束（如 `users.account`、`users.email`）產生衝突，建議僅在明確需要追加時使用。

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

### seed 腳本執行失敗（連線錯誤）
- 先確認 `DATABASE_URL` 是否正確、資料庫服務是否啟動、帳密/權限是否可用。
- 再次確認執行位置為 `backend`，並以 `uv run` 啟動腳本。

### seed 追加模式出現唯一鍵衝突
- 若無需保留既有 seed，改用預設模式（不帶 `--no-reset`）重建。
- 若需保留資料，先清理衝突資料再重跑 `--no-reset`。

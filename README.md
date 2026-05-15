# AS API Console

## 專案簡介
AS API Console 是一套 API Key 申請與管理系統，提供從申請、核發、查詢到停用的完整流程。MVP 聚焦在安全可控與最小可用：以「研究人員名單（職稱代碼）」與「特殊人員名單（原白名單）」做資格檢查、一次性明文顯示、一般使用者僅可查看本人紀錄，並可自行停用已生效 Key。

## 技術棧
- Backend
  - Python `>=3.12,<3.14`
  - FastAPI（API 與 OpenAPI 文件）
  - SQLAlchemy（ORM）
  - Alembic（資料庫 migration）
- Frontend
  - React
  - MUI
  - Vite
- Database
  - MariaDB（MVP）
  - PostgreSQL（後續可擴充）

## 目前狀態
已完成：
- Backend API（`/api/v1/*`）
- Frontend 頁面（Apply / API Keys / Whitelist Admin / Admin List / Admin Dashboard）
- 前後端串接（前端直連 real API）
- Backend 可直接提供 frontend build 後靜態頁
- 前端支援 `zh-TW`/`en` 語言切換，並可透過後端儲存使用者語言偏好

## 契約重點
- 產品/API/data 行為以 `docs/SPEC.md` 為唯一契約來源。
- Auth identity source of truth：`account`、`name`、`email`、`department`、`sysid`（由 auth context 提供）。
- 角色模型僅 `user` 與 `admin`。
- API 路徑維持 resource-oriented（避免 `/my/*`、`/admin/*` 命名）；受保護 API surface 以 `docs/SPEC.md` 為準。

## 啟動方式
1. 安裝依賴
```bash
brew install mariadb-connector-c

cd backend
uv sync
cd ../frontend
npm install
```

2. 建置前端
```bash
cd frontend
npm run build
```

3. 設定後端環境變數
```bash
cd backend
cp .env.example .env
```
- `APP_DOMAIN`：後端對外基底網址（預設 `http://localhost:8000`，方便後續部署調整）
- `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` / `DB_NAME`：MariaDB 連線組件（程式會自動組成 `DATABASE_URL`）
- `DATABASE_URL`：可選，若提供會覆蓋 `DB_*` 組合結果
- `TEST_DB_USER` / `TEST_DB_PASSWORD` / `TEST_DB_HOST` / `TEST_DB_PORT` / `TEST_DB_NAME`：測試資料庫連線組件（程式會自動組成 `TEST_DATABASE_URL`）
- `TEST_DATABASE_URL`：可選，若提供會覆蓋 `TEST_DB_*` 組合結果
- `RESEARCH_LIST_API_URL`：可選，外部研究人員資格查詢 API URL（設定後申請會即時查詢）
- `RESEARCH_LIST_TIMEOUT_SECONDS`：可選，外部查詢 timeout 秒數（預設 `3.0`）
- `RESEARCH_LIST_ALLOWED_TITLE_CODES`：可選，允許通過的職稱代碼清單（逗號分隔，例如 `RS01,RS02`）
- `API_KEY_ENCRYPTION_SECRET`：必填（正式環境），用於 API key 密文加解密的主密鑰來源
- `API_KEY_KEK_VERSION`：可選，金鑰版本標記（預設 `v1`）
- `PROVIDER_BASE_URL`：可選，外部 key provider base URL（例如 `https://provider.internal`）
- `PROVIDER_MASTER_KEY`：可選，呼叫 provider `/key/generate` 使用的主金鑰
- `PROVIDER_TIMEOUT_SECONDS`：可選，provider timeout 秒數（預設 `3.0`）

4. 啟動後端（同時提供 API + 前端頁面）
```bash
cd backend
uv run uvicorn app.main:app --reload
```

5. 開啟系統
- 前端頁面：`http://127.0.0.1:8000/`
- API 文件：`http://127.0.0.1:8000/docs`

## 前端更新流程
- 修改前端後重新執行：
```bash
cd frontend
npm run build
```
- 回到瀏覽器重新整理 `http://127.0.0.1:8000/` 即可看到更新。

## 開發備註
- 前端在開發模式提供 `Dev 身份切換`（admin/user），用於模擬 header 身份。
- 若有第三方 OAuth 整合，前端會優先使用 OAuth 回傳身分（需包含 `account`、`name`、`email`、`department`、`sysid`、`role`）：
  - `window.__AS_AUTH_CONTEXT__ = { ... }`，或
  - `sessionStorage["as-api-console-auth-context"] = JSON.stringify({ ... })`
- 當 OAuth 身分存在時，前端會隱藏 `Dev 身份切換`。
- Vite dev server 已設定 `/api` proxy 到 `http://127.0.0.1:8000`（若需 `npm run dev` 分離開發可直接使用）。
- 前端資料來源由 `VITE_API_PROVIDER` 控制：
  - 預設（`frontend/.env.development`）：`mock`
  - 切換 real API：
    ```bash
    cd frontend
    VITE_API_PROVIDER=real npm run dev
    ```
  - 使用 mock：
    ```bash
    cd frontend
    VITE_API_PROVIDER=mock npm run dev
    ```

## 測試資料生成（本機 DB）
1. 進入 backend（需先完成 migration 並確認 `DATABASE_URL` 可連線）：
```bash
cd backend
```
2. 重建小型測試資料集（預設會先清除既有 seed 範圍再重建）：
```bash
uv run python scripts/seed_test_data.py
```
3. 保留既有 seed 資料並追加：
```bash
uv run python scripts/seed_test_data.py --no-reset
```
- 成功輸出範例：
```text
Seed completed: users=8, whitelists=8, applications=20, api_keys=20, reset=True
```
- `reset=True` 代表本次先清除既有 seed 範圍再重建；`reset=False` 代表追加模式（`--no-reset`）。
- 詳細驗證與常見錯誤處理請見 `docs/runbook-db.md` 的「測試資料（seed）操作」章節。

## 測試
Backend：
```bash
cd backend
uv run pytest
```

Frontend：
```bash
cd frontend
npm run test
```

## 規格文件
- 產品與功能規格：`docs/SPEC.md`
- DB 操作與 migration runbook：`docs/runbook-db.md`

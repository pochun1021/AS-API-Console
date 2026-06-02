# AS API Console

## 專案簡介
AS API Console 是一套 API Key 申請與管理系統，提供從申請、核發、查詢到停用的完整流程。MVP 聚焦在安全可控與最小可用：以「研究人員名單（職稱代碼）」與「特殊人員名單（原白名單）」做資格檢查、申請成功即時核發並一次性明文顯示、一般使用者僅可查看本人紀錄，並可自行停用已生效 Key。API key lifecycle 採 external provider 為主權威，本地僅保存 encrypted secret material（`key_hash`、`key_ciphertext`、`key_kek_version`）。

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
- Backend API（`/main/api/v1/*`）
- Frontend 頁面（Apply / API Keys / Whitelist Admin / Admin List / Admin Dashboard）
- 前後端串接（前端直連 real API）
- Backend 可直接提供 frontend build 後靜態頁
- 前端支援 `zh-TW`/`en` 語言切換，並可透過後端儲存使用者語言偏好
- provider timeout/5xx 時直接回 `503 PROVIDER_UNAVAILABLE`（不建立 pending 申請）
- `renew` / `extend` / `revoke` 已對齊 provider-first 契約；本地僅於 provider 成功後同步狀態，`reveal` 僅供受控 break-glass
- #22 已同步完成 `api_key_applications` schema/migration、申請頁驗證訊息與 proxy 申請流程；仍有少量後端測試與文件收尾待補。

## 契約重點
- 產品/API/data 行為以 `docs/SPEC.md` 為唯一契約來源。
- Auth identity source of truth：`account`、`name`、`email`、`department`、`sysid`（由 auth context 提供；`sysid` 為純數字）。
- OAuth claims 映射：`account<-cn`、`name<-chName`、`email<-email`、`department<-instCode`、`sysid<-sysId`。
- 角色模型僅 `user` 與 `admin`。
- `admin` 可在申請 API 時代他人送件（`target_identity.account`）；姓名、Email、單位、sysid 由後端查詢目錄服務補齊，並保留操作者稽核欄位。
- application row 僅保存申請人快照（`account`、`name`、`email`、`department`、`sysid`）、`is_proxy_submission`，以及必要時的 `proxy_operator_account`；完整操作者身份改由 audit logs 追蹤。
- API 路徑維持 resource-oriented（避免 `/my/*`、`/admin/*` 命名）；受保護 API surface 以 `docs/SPEC.md` 為準。
- API key lifecycle 採 `External SoT + Encrypted Local Secret`；`applications/create`、`renew`、`extend`、`revoke` 皆先以 provider 結果為準，再同步本地資料。
- `renew` 僅允許 `revoked` key；`expired` key 僅可透過 `extend` 延長有效期限。
- `POST /main/api/v1/api-keys/{id}/reveal` 僅供 `admin` 受控 break-glass 使用，不屬一般 lifecycle 流程。
- 金鑰條件術語：
  - `budget`=額度；`max_budget`=總金額額度（USD）；`budget_duration`=重置週期（`daily|weekly|monthly`）。
  - `rate_limit`=速度；`tpm_limit`=每分鐘 Token 數限制；`rpm_limit`=每分鐘請求數限制。
- 金鑰條件套用規則：每把 API Key 需同時套用 `budget + rate_limit`，不使用二選一 `issuance_mode`。
- 不提供 pending 補發端點；前端不提供待審申請頁面入口。

## 啟動方式
1. 安裝依賴
```bash
brew install mariadb-connector-c

cd backend
uv sync
cd ../frontend
npm install
```
若環境沒有 `uv`，可改用：
```bash
brew install mariadb-connector-c

cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
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
mkdir -p /home/app/config
cp -n backend/.env.example /home/app/config/.env
export ENV_FILE=/home/app/config/.env
```
- 環境檔載入順序：`ENV_FILE`（若有設定）→ `/home/app/config/.env`（若存在）→ `backend/.env`（開發預設）
- `APP_DOMAIN`：後端對外基底網址（預設 `http://localhost:8000`，方便後續部署調整）
- `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` / `DB_NAME`：MariaDB 連線組件（程式會自動組成 `DATABASE_URL`）
- 建議命名規則：`DB_USER` 與 `DB_NAME` 使用相同名稱（例如都用 `as_api_console`），方便權限管理與維運
- `DATABASE_URL`：可選，若提供會覆蓋 `DB_*` 組合結果
- `TEST_DB_USER` / `TEST_DB_PASSWORD` / `TEST_DB_HOST` / `TEST_DB_PORT` / `TEST_DB_NAME`：僅測試（pytest）使用的資料庫連線組件（程式會自動組成 `TEST_DATABASE_URL`）
- 建議命名規則：`TEST_DB_USER` 與 `TEST_DB_NAME` 使用相同名稱（例如都用 `as_api_console_test`）
- `TEST_DATABASE_URL`：僅測試（pytest）使用；若提供會覆蓋 `TEST_DB_*` 組合結果
- `LOGIN_ALLOWED_TITLE_CODES`：可選，登入資格補充放行職稱代碼清單（逗號分隔，例如 `A01,A02,A03,A06,A11,A15,A1A,A1I,B01,B02,B03,B03,B04,B11,B12,B13,B14,B21`；解析時會做 `trim + upper`，空值略過且重複值去重）
- `PERSNL_SOAP_URL`：可選，Persnl SOAP runtime endpoint（設定時會優先作為實際呼叫位址）
- `PERSNL_SOAP_WSDL_URL`：可選，Persnl SOAP WSDL URL（設定後可使用 WSDL client）
- `PERSNL_SOAP_USER` / `PERSNL_SOAP_PASSWORD`：單位主檔同步（`sync_institutes.py`）使用的 SOAP 帳密
- `PERSNL_SOAP_TIMEOUT_SECONDS`：可選，SOAP 呼叫 timeout 秒數（預設 `3.0`）
- `API_KEY_ENCRYPTION_SECRET`：必填（正式環境），用於 API key 密文加解密的主密鑰來源
- `API_KEY_KEK_VERSION`：可選，金鑰版本標記（預設 `v1`）
- `PROVIDER_BASE_URL`：可選，外部 key provider base URL（例如 `https://provider.internal`）；系統會用於 `POST /key/generate`、`/key/update`、`/key/regenerate`、`/key/block`
- `PROVIDER_MASTER_KEY`：可選，provider Bearer token 值；系統會送出 `Authorization: Bearer ${PROVIDER_MASTER_KEY}`
- `PROVIDER_TIMEOUT_SECONDS`：可選，provider timeout 秒數（預設 `3.0`）
- `PROVIDER_DEBUG_LOGGING`：可選，啟用 provider outbound debug log；僅記錄 path、status code、payload keys、request_id / operation_id 等非敏感摘要，不記錄 Bearer token 或 key/token 明文
  - provider `generate/regenerate` 成功時，後端會自 provider response `key` 讀取新明文 key，再轉成對外 API 的一次性 `api_key_plaintext`
- `SESSION_SECRET_KEY`：必填（正式環境），FastAPI session 簽章密鑰
- `ALLOW_HEADER_AUTH`：可選；僅供 `dev/test` 使用的 header auth bootstrap，正式環境應為 `false`
- `ALLOWED_HOSTS`：可選；允許的 Host 清單（逗號分隔）。部署 `api.ascs.sinica.edu.tw` 時建議設為 `api.ascs.sinica.edu.tw,localhost,127.0.0.1`
- `SESSION_MAX_AGE_SECONDS`：可選；session 有效秒數
- `OAUTH_PROVIDER`：可選，OAuth provider 名稱（寫入 auth audit）
- `OAUTH_AUTH_URI` / `OAUTH_TOKEN_URI` / `OAUTH_BASIC_URI`：OAuth auth/token/basic 端點
- `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` / `OAUTH_REDIRECT_URI`：OAuth client 設定
- `OAUTH_SCOPE`：可選，OAuth scope（預設 `basic`）
- `DEV_LOGIN_ACCOUNT` / `DEV_LOGIN_NAME` / `DEV_LOGIN_EMAIL` / `DEV_LOGIN_DEPARTMENT` / `DEV_LOGIN_SYSID`：`APP_ENV=dev/test` 使用 `/main/login` bypass 時建立 session 身分所需欄位
- `DEV_LOGIN_ROLE`：可選，`APP_ENV=dev/test` bypass 身分角色（僅允許 `user` 或 `admin`，預設 `user`）
- `SCHEDULER_LOG_ROOT`：可選，排程腳本日誌根目錄（預設 `/home/app/log`，實際會寫入子目錄如 `sync_expired_api_keys/`、`send_expiration_reminders/`）
- `MAIL_ENABLED`：可選，是否啟用 Email 發送（預設 `false`）
- `MAIL_SERVER` / `MAIL_PORT`：可選，SMTP 主機與連接埠
- `MAIL_USERNAME` / `MAIL_PASSWORD`：可選，SMTP 認證資訊
- `MAIL_FROM` / `MAIL_FROM_NAME`：可選，寄件者地址與顯示名稱
- `MAIL_STARTTLS` / `MAIL_SSL_TLS` / `MAIL_VALIDATE_CERTS`：可選，SMTP 傳輸安全參數

4. 啟動後端（同時提供 API + 前端頁面）
```bash
cd backend
export ENV_FILE=/home/app/config/.env
uv run uvicorn app.main:app --reload
```
若環境沒有 `uv`：
```bash
cd backend
export ENV_FILE=/home/app/config/.env
. .venv/bin/activate
python -m uvicorn app.main:app --reload
```

5. 開啟系統
- 前端頁面：`http://127.0.0.1:8000/main/`
- API 文件：`http://127.0.0.1:8000/main/docs`
- OAuth 登入入口：`http://127.0.0.1:8000/main/login`

## 前端更新流程
- 修改前端後重新執行：
```bash
cd frontend
npm run build
```
- 回到瀏覽器重新整理 `http://127.0.0.1:8000/main/` 即可看到更新。

## 開發備註
- 後端登入入口：
  - `APP_ENV=prod`：`GET /main/login` 走 OAuth，callback `GET /main/auth/callback` 於必要 claims 驗證後，依序檢查 `active whitelist(sysid)`、`active admins(id=sysid)`、`LOGIN_ALLOWED_TITLE_CODES`；通過才建立 session，否則導向 `/main/login-denied?error=LOGIN_NOT_ELIGIBLE`。
  - `APP_ENV=dev/test`：`GET /main/login` 直接 bypass OAuth，使用 `DEV_LOGIN_*` 建立 session auth context（`role` 由 `DEV_LOGIN_ROLE` 控制，僅 `user|admin`）。
- 前端公開拒絕頁：`/main/login-denied` 為不符登入資格時的公開頁，不需 session 即可顯示，並提供返回 `/main/login` 重新登入。
- 前端啟動時會呼叫 `GET /main/api/v1/users/me` 取得目前 session 使用者資訊與 `csrf_token`。
- `POST/PATCH` API 會以 `X-CSRF-Token` 搭配 session 驗證；正式環境不得以前端自送 header 當作正式認證來源。
- 若在 `dev/test` 啟用 `ALLOW_HEADER_AUTH=true`，前端可用開發身分 bootstrap session（需包含 `account`、`name`、`email`、`department`、`sysid`、`role`）：
  - `window.__AS_AUTH_CONTEXT__ = { ... }`，或
  - `sessionStorage["as-api-console-auth-context"] = JSON.stringify({ ... })`
- Vite dev server 已設定 `/main/api` proxy 到 `http://127.0.0.1:8000`（若需 `npm run dev` 分離開發可直接使用）。
- 前端預設使用 real API（HTTP provider）；建議搭配本機 DB seed 資料進行整合開發。

## 測試資料生成（本機 DB）
1. 一鍵初始化本機開發 DB（migration + seed）：
```bash
cd backend
uv run python scripts/setup_dev_db.py
```
若環境沒有 `uv`：
```bash
. .venv/bin/activate
python scripts/setup_dev_db.py
```
2. 只重建小型測試資料集（預設會先清除既有 seed 範圍再重建）：
```bash
uv run python scripts/seed_test_data.py
```
若環境沒有 `uv`：
```bash
. .venv/bin/activate
python scripts/seed_test_data.py
```
3. 保留既有 seed 資料並追加：
```bash
uv run python scripts/seed_test_data.py --no-reset
```
若環境沒有 `uv`：
```bash
. .venv/bin/activate
python scripts/seed_test_data.py --no-reset
```
- 成功輸出範例：
```text
Seed completed: admins=2, whitelists=8, applications=20, api_keys=20, reset=True
```
- `reset=True` 代表本次先清除既有 seed 範圍再重建；`reset=False` 代表追加模式（`--no-reset`）。
- 詳細驗證與常見錯誤處理請見 `docs/runbook-db.md` 的「測試資料（seed）操作」章節。

## API Key Expired 回填排程
- 狀態策略採混合模式：
  - API 查詢端以 effective status 即時計算（`active` 且 `expires_at` 已過，對外視為 `expired`）。
  - 背景排程將符合條件資料回填落地為 `expired`（條件：`api_keys.status=active` 且 `expires_at` 已過，不要求 application 狀態），提升資料一致性與查詢效率。
- 內建腳本：
```bash
cd backend
ENV_FILE=/home/app/config/.env ./scripts/run_expire_sync.sh
```
- 參數範例：
```bash
cd backend
ENV_FILE=/home/app/config/.env ./scripts/run_expire_sync.sh --batch-size 2000
ENV_FILE=/home/app/config/.env ./scripts/run_expire_sync.sh --dry-run
```
- 執行日誌：
  - 會寫入專案根目錄 `log/sync_expired_api_keys/`。
  - 依 `Asia/Taipei` 日期切日，每日一檔：`YYYY-MM-DD.log`。
  - 會保留既有終端輸出，並同步寫入檔案。
- 預設建議頻率：每日 `00:10`。
- 正式部署排程設定請見 `docs/deploy-ubuntu-nginx.md`（systemd timer 與 cron 兩種方案）。
- 部署端排程指令與驗證步驟以 `docs/deploy-ubuntu-nginx.md` 第 16 節為準。

## API Key 到期前 30 天提醒排程
- 目的：針對即將於 30 天後到期的 `active` API Key 寄送提醒信給申請者本人，提醒到期時間與可展延。
- 內建腳本：
```bash
cd backend
ENV_FILE=/home/app/config/.env ./scripts/run_expiration_reminder.sh
```
- 參數範例：
```bash
cd backend
ENV_FILE=/home/app/config/.env ./scripts/run_expiration_reminder.sh --batch-size 2000
ENV_FILE=/home/app/config/.env ./scripts/run_expiration_reminder.sh --dry-run
```
- 執行日誌：
  - 會寫入專案根目錄 `log/send_expiration_reminders/`。
  - 依 `Asia/Taipei` 日期切日，每日一檔：`YYYY-MM-DD.log`。
- 預設建議頻率：每日 `00:30`（與其他排程錯峰）。

## 單位主檔同步排程
- 單位主檔同步來源為 `Persnl.getInstitutes`，使用背景排程執行差異同步（新增/更新/停用）。
- 內建腳本：
```bash
cd backend
ENV_FILE=/home/app/config/.env python scripts/sync_institutes.py
```
- dry-run 驗證：
```bash
cd backend
ENV_FILE=/home/app/config/.env python scripts/sync_institutes.py --dry-run
```
- 預設建議頻率：每日 `00:20`（與 expired 回填 `00:10` 錯峰）。
- 前置條件：需先設定 `PERSNL_SOAP_*`；未設定時 `sync_institutes.py` 會以 `persnl soap is not configured` 失敗退出。
- 正式部署排程設定請見 `docs/deploy-ubuntu-nginx.md`（systemd timer 與 cron 兩種方案）。
- 部署端排程指令與驗證步驟以 `docs/deploy-ubuntu-nginx.md` 第 17 節為準。

## Persnl 連線測試（正式環境）
- 目的：快速驗證正式環境是否可連線並查詢 Persnl SOAP（登入、存在/不存在人員、單位清單）。
- 必要環境變數：`PERSNL_SOAP_URL`、`PERSNL_SOAP_USER`、`PERSNL_SOAP_PASSWORD`（可選：`PERSNL_SOAP_TIMEOUT_SECONDS`）。
- 腳本會自動依序嘗試載入：`ENV_FILE`（若已設定且存在）→ `/home/app/config/.env` → `backend/.env`。
- Python 執行器優先順序：`backend/.venv/bin/python` → `uv run python` → `python3`。
- 根目錄直接執行：
```bash
./scripts/test_persnl_connectivity.sh
```
- 回傳碼：`0` 代表全部檢查通過；非 `0` 代表至少一項失敗。

## 測試
Backend：
```bash
cd backend
uv run pytest
```
若環境沒有 `uv`：
```bash
cd backend
. .venv/bin/activate
python -m pytest
```

Frontend：
```bash
cd frontend
npm run test
```

Security validation：
- CI `security-scan` workflow now includes:
  - baseline scanners: `Bandit`, `pip-audit`, `npm audit`, `gitleaks`, `Trivy`
  - extended SAST: `Semgrep`
  - API dynamic validation: `Schemathesis` + custom API DAST smoke
- Test-only session bootstrap endpoint `POST /main/test/session-login` is available only when `APP_ENV=test`; it is intended for CI / automated API security validation, not for production use.

## 規格文件
- 產品與功能規格：`docs/SPEC.md`
- DB 操作與 migration runbook：`docs/runbook-db.md`
  - `alembic current` 的 head 判讀請以 runbook 內「最新 head revision」為準，不使用固定舊 revision 範例
- Mail 設定與測試速查：`docs/mail.md`
- Ubuntu + Nginx 部署指南：`docs/deploy-ubuntu-nginx.md`
- 一鍵部署腳本（預設來源 `/root/AS-API-Console`，可用 `--source-dir` 覆蓋；此路徑為 root 下 `git clone` 來源目錄；搬遷到 `/home/app/AS-API-Console`（可用 `--app-dir` 覆蓋）；若目標已存在會先備份到 `APP_DIR` 父目錄下的 `AS-API-Console_YYYYMMDD_HHMMSS.tar.gz`（每次部署會帶時間戳產生新備份）；完成安裝與設定後才清理 clone 來源目錄；安裝 backend 套件 + frontend `npm install`/`npm run build` + migration + crontab 補齊；`ENV_FILE` 可用 `--env-file` 指定，預設 `/home/app/config/.env`，缺檔時 fallback 到 `backend/.env`）：`scripts/deploy_full.sh`

# AS API Console - API Key 申請系統 MVP Specification

## 產品目標
本 MVP 目標是建立一套可用且安全的 API Key 申請系統，支援 API Key 的核心生命週期：
- 申請
- 特殊人員名單驗證
- 自動核發
- 查詢管理
- 使用者自助查詢與停用
- 撤銷
- 到期失效

重點是先提供最小可用流程，並保留後續審核流程與安全等級擴充能力。

## 資料儲存策略
- MVP 階段採用 MariaDB 作為主要資料庫。
- ORM 與 migration 層維持 SQLAlchemy + Alembic，確保後續可平滑擴充至 PostgreSQL。
- DB schema/migration 操作與驗證流程請見 `docs/runbook-db.md`。
- 開發/測試可使用 `backend/scripts/seed_test_data.py` 產生本機測試資料；此腳本僅供開發驗證，不屬正式 API contract。
- 測試資料流程不得新增一般查詢端點回傳明文 API Key 的能力；明文 key 預設僅允許在建立當下回傳一次。

## 使用者流程
1. 使用者透過 SSO/OAuth 登入時，系統先檢查進入資格：優先查外部研究人員名單（以職稱代碼判斷），未命中再檢查本系統特殊人員名單（原白名單，僅 `active` 可通過）。
2. 通過進入資格後進入申請頁，系統自動帶入 `account`、`name`、`email`、`department`、`sysid`（對應 OAuth claims：`cn`、`chName`、`email`、`instCode`、`sysId`）。
3. 一般使用者填寫申請日期、用途與 API 生效時長；管理者可選擇代他人送出申請，僅需填寫目標 `account`，其餘身份欄位由系統查詢補齊。
4. 送出申請前再次檢查資格：優先查外部研究人員名單（職稱代碼），未命中再檢查特殊人員名單（`active`）。
5. 資格檢查通過後系統立即核發 API Key 並回傳一次性明文；不需經過常態管理者審核。
5-1. 若 provider timeout/5xx 導致無法即時核發，系統需直接回傳 `503 PROVIDER_UNAVAILABLE`，不得建立 pending 申請。
6. 系統只顯示一次明文 API Key，使用者需立即保存。
7. 一般使用者可在「我的 API Key 紀錄」查看本人歷史紀錄（`active|revoked|expired`），Key 僅顯示遮罩（`AS-...` + 後 4 碼）；若舊 key 已被 renew，該舊 key 對一般使用者隱藏。
8. 一般使用者可自行停用本人已生效（`active`）的 Key。
9. 使用者可於列表/詳情查看狀態、到期時間與遮罩 key（`AS-...XXXX`）。

## 頁面規格
### 1) Apply Page（申請頁）
- 欄位：
  - `account`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `name`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `email`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `department`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `sysid`（必填，唯讀，自 SSO/OAuth 登入帶入；純數字）
  - `application_date`（必填，使用者可選）
  - `duration_months`（必填，選單：`1|6|12`）
  - `purpose`（必填）
  - `target_identity`（選填；僅 `admin` 可傳，欄位：`account`）
- 驗證：
  - `email` 格式檢查
  - `sysid` 必須為純數字（整數語意）
  - 申請資格需通過：研究人員名單職稱代碼命中，或特殊人員名單為 `active`
  - `application_date` 格式為 `YYYY-MM-DD` 且不得晚於申請當日
  - `duration_months` 僅允許 `1|6|12`
  - `admin` 代申請時，`target_identity.account` 必填；`name`、`email`、`department`、`sysid` 由後端目錄查詢補齊
  - 限制策略由管理者透過模板資源維護；一般使用者申請時不可提交策略細節
- 成功送出後顯示一次性 key，並提供複製操作；複製成功需有明確視覺回饋（check icon 後恢復）。
- 複製流程以 Clipboard API 為唯一可驗證複製路徑；若不可用或複製失敗，需提示使用者手動複製。
- 透過複製 icon 觸發時不得要求使用者先反白金鑰文字，系統需直接完成複製。

### 2) My API Keys Page（一般使用者我的紀錄頁）
- 顯示範圍：僅本人帳號歷史紀錄（`active|revoked|expired`）；若舊 key 已被 renew，對一般使用者隱藏。
- 顯示欄位：申請日期、生效時長、狀態、到期時間、遮罩 key（`AS-...` + 後 4 碼）。
- 管理者在同頁可額外查看申請人識別欄位（`owner_account`、`owner_name`）。
- 管理者在同頁可查看並編輯 `key_alias`；若資料未設定，預設顯示 `for_{owner_account}`。
- 操作：
  - 對 `active` key 顯示「停用」按鈕。
  - 對 `revoked|expired` key 顯示「續發（renew）」按鈕（icon + 文字）。
  - renew 會建立新 key，沿用原 `duration_months` 與原 `purpose`。

### 3) API Key Detail Dialog（詳情視窗）
- 顯示完整申請資訊與狀態。
- 顯示欄位至少包含：申請日期、生效時長、用途（`purpose`）、單位（`department`）、建立時間、到期時間、遮罩 key。
- 一般使用者僅可查本人資料。
- 一般使用者可停用本人 `active` key。
- 一般查詢/詳情不可再次顯示 key 明文（僅受控 reveal 流程可回取）。
- 管理者可於詳情視窗編輯 `key_alias`。

### 4) Whitelist Admin Page（特殊人員名單管理頁）
- 可用 `account`、`name` 查詢使用者後加入特殊人員名單。
- 可查詢特殊人員名單與狀態。
- 可停用/啟用特殊人員名單條目。

### 5) Admin List Page（管理者名單頁）
- 僅 `admin` 可使用。
- 列表僅顯示目前已啟用管理權限（`role=admin`）的人員。
- 列表需顯示管理者狀態（`active`/`inactive`），停用後不得自動從名單移除。
- 可用 `account`、`name` 查詢使用者。
- 可啟用一般使用者的管理者權限（對應 `enable`）。
- 可停用其他管理者的管理者權限（對應 `disable`）。
- 前端需阻擋管理者對自己執行管理者停用（避免誤鎖管理權限）。

### 6) Admin Dashboard Page（管理者統計頁）
- 僅 `admin` 可使用。
- 以 Data Table 呈現每位申請人的統計資料，欄位至少包含：`account`、`name`、`email`、`total_applications`、`active_count`、`revoked_count`、`expired_count`、`last_applied_at`。
- 提供「圖表 / 表格」視圖切換；圖表以長條圖呈現。
- 圖表支援 X 軸切換：`account|department`，Y 軸切換：`total_applications|active_count|revoked_count|expired_count`，與 Top N（`5|10|20`）切換。
- 圖表 X 軸分類文字需直接顯示在圖下方，不可僅依賴滑鼠 hover tooltip 才能辨識帳號/單位。
- X 軸刻度文字在圖表視圖中不得被自動省略為僅部分可見（需可直接辨識每個可見柱狀分類）。
- 支援口徑切換 `scope`：`all|active|revoked|expired`（預設 `all`）。
- 支援日期區間篩選：`from`、`to`（`YYYY-MM-DD`），統計基準為 `application_date`。
- 支援 `q`（`account`、`name`、`email`）查詢、分頁與排序。
- 預設排序為 `total_applications desc`。
- 圖表口徑需與目前篩選條件一致（`scope`、`from`、`to`、`q`、`sort`）。
- 表格中的 `total_applications` 與 `active_count` 需可點擊，並以 Dialog 顯示該申請人的 API Key 明細（僅遮罩 key，不得回傳明文）。
- Dialog 明細預設欄位為 `key_alias`、`masked_key`、`status`；且需跟隨目前統計頁日期篩選（`from`、`to`）。

### 8) Key Condition Page（金鑰條件管理頁）
- 僅 `admin` 可使用。
- 以獨立頁面管理金鑰條件模板（查詢、新增、編輯）。
- 模板型別僅允許：
  - `budget`（額度；必填：`max_budget`、`budget_duration`）
  - `rate_limit`（速度；必填：`tpm_limit`、`rpm_limit`）
- 欄位語意：
  - `max_budget`：總金額額度（USD）。
  - `budget_duration`：重置週期（僅允許 `daily|weekly|monthly`）。
  - `tpm_limit`：每分鐘 Token 數限制。
  - `rpm_limit`：每分鐘請求數限制。
- `budget_duration` 前端顯示需使用單選，展示文案映射：
  - `daily` => `1天`
  - `weekly` => `7天`
  - `monthly` => `30天`
- 可調整模板狀態 `active|inactive`。
- 一般使用者不可查看或修改金鑰條件模板。

### 7) 狀態頁/元件
- Loading
- Empty
- Error（含重試）
- 列表資料以 Data Table 呈現（支援排序與分頁）；僅「操作」欄位不可排序與不可 filter。

## 功能需求
### Must Have（MVP）
- 權限模型僅區分 `user` 與 `admin`
- 提供 OAuth/SSO 登入入口（`GET /login`、`GET /auth/callback`）並建立 session auth context
- 正式環境僅允許以 session auth context 驗證；header auth 僅限 `dev/test`
- 所有會變更資料的 API 皆需通過 CSRF 驗證
- 僅符合資格的人員可進入系統與申請 API Key（研究人員名單職稱代碼命中，或特殊人員名單 `active` 命中）
- 特殊人員名單管理能力（新增、查詢、停用/啟用）
- 研究人員名單由外部服務提供並以職稱代碼判斷
- 本系統不同步維護本地研究人員名單；申請時以外部服務即時查詢為準
- 外部研究人員服務失敗（timeout/5xx）時：允許進入系統，但阻擋申請
- 申請成功時立即核發 API Key；provider timeout/5xx 時直接回傳 `503 PROVIDER_UNAVAILABLE`
- API 生效時長固定月數選單（`1|6|12`）
- API Key 格式固定為 `AS-` + 30 碼隨機字元（總長 33）
- API Key 明文只顯示一次
- 系統儲存 `key_hash` 與加密密文（`key_ciphertext`），不直接儲存明文
- 一般使用者可查看本人全部申請紀錄
- 一般使用者查詢時 API Key 必須遮罩顯示
- 一般使用者可自行停用本人已生效 key（軟停用）
- 支援撤銷與狀態管理（`active|revoked|expired`）
- 管理者可查看全部 API Key 與申請紀錄
- 管理者可查看每位申請人的 API Key 申請統計（含狀態分佈）
- 管理者可啟用/停用其他使用者的管理者身分

### Nice to Have（後續）
- 多安全等級與長度策略（隨機段長度 24-30 碼可配置）
- 使用量監控與配額管理

## 資料模型草案
### Entity: `users`（已移除）
- `users` table 已自本階段移除。
- 管理者資料來源為 `admins`。

### Entity: `admins`（管理者名單來源）
- `id` (string/uuid)
- `account` (string, required, unique)
- `email` (string, required, unique, lowercase)
- `name` (string, required)
- `department` (string, nullable)
- `sysid` (integer, required)
- `status` (enum: `active` | `inactive`)
- `created_by` (string)
- `updated_by` (string)
- `created_at` (datetime)
- `updated_at` (datetime)

### Entity: `api_key_whitelist`
- `id` (string/uuid)
- `sysid` (integer, required, unique)
- `email` (string, nullable, lowercase；僅供顯示，不作放行比對)
- `status` (enum: `active` | `inactive`)
- `note` (string, nullable)
- `created_by` (string)
- `updated_by` (string)
- `created_at` (datetime)
- `updated_at` (datetime)

### Entity: `api_key_applications`
- `id` (string/uuid)
- `account` (string, required)
- `user_id` (integer, required；存 auth `sysid`，不再綁定 `users` FK)
- `name` (string, required)
- `email` (string, required)
- `department` (string, required)
- `application_date` (date, required)
- `duration_months` (int, required, allowed: `1|6|12`)
- `purpose` (string, required)
- `issuance_status` (enum: `issued`)
- `pending_issued_at` (datetime, nullable)
- `status` (enum: `active` | `revoked` | `expired`)
- `issued_at` (datetime)
- `expires_at` (datetime)
- `revoked_at` (datetime, nullable)
- `sysid` (integer, required, SSO/OAuth 主體唯一識別碼)
- `is_proxy_submission` (bool, required；是否為管理者代申請)
- `operator_account` (string, required；實際操作者帳號)
- `operator_name` (string, required；實際操作者姓名)
- `operator_email` (string, required；實際操作者 email)
- `operator_department` (string, required；實際操作者單位)
- `operator_sysid` (integer, required；實際操作者 sysid)
- `created_at` (datetime)
- `updated_at` (datetime)

### Entity: `api_keys`
- `id` (string/uuid)
- `application_id` (fk -> api_key_applications.id)
- `key_hash` (string, required)
- `masked_key` (string, 遮罩格式固定為 `AS-...` + 後 4 碼；response only)
- `key_alias` (string, nullable；顯示預設值 `for_{owner_account}`，可由 admin 更新)
- `key_ciphertext` (string, encrypted at rest, nullable for legacy rows)
- `key_kek_version` (string, key-encryption-key version tag)
- `length` (int, MVP 固定 30，表示隨機段長度，不含 `AS-` 前綴)
- `security_level` (enum, MVP 固定 `high`)
- `status` (enum: `active` | `revoked` | `expired`)
- `created_at` (datetime)

### Entity: `auth_audit_logs`
- `id` (string/uuid)
- `provider` (string, required)
- `request_id` (string, required)
- `result` (enum: `success` | `failure`)
- `error_code` (string, nullable)
- `account` (string, nullable)
- `name` (string, nullable)
- `email` (string, nullable)
- `department` (string, nullable)
- `sysid` (integer, nullable)
- `role` (string, nullable；本期固定 `user`)
- `detail` (string, nullable)
- `created_at` (datetime)
- 不得記錄 access token、refresh token、password、client secret 等敏感憑證

### Entity: `operation_audit_logs`
- `id` (string/uuid)
- `event_type` (string, required)
- `action` (string, required)
- `result` (enum: `success` | `failure`)
- `error_code` (string, nullable)
- `actor_sysid` (integer, nullable)
- `actor_account` (string, nullable)
- `actor_role` (string, nullable)
- `target_type` (string, required)
- `target_id` (string, nullable)
- `request_id` (string, required)
- `source_ip` (string, nullable)
- `user_agent` (string, nullable)
- `metadata_json` (string, nullable；僅允許白名單欄位，不得包含敏感值)
- `created_at` (datetime)
- 目的：記錄關鍵操作稽核（v1），成功與失敗事件皆需落地。
- 不得記錄 API key 明文、token、password、client secret 等敏感憑證。

## 權限規則（MVP）
- `user`：可使用 `GET /api/v1/api-keys`、`GET /api/v1/api-keys/{id}`、`POST /api/v1/api-keys/{id}/revoke`、`POST /api/v1/api-keys/{id}/renew`，僅可操作本人 key。
- `user`：不可更新 `key_alias`。
- `admin`：可查詢全部 API Key 與申請紀錄，可管理特殊人員名單（沿用受保護路徑 `/api/v1/whitelists*`），可啟用/停用其他使用者管理者身分（沿用受保護路徑 `/api/v1/admins/{id}/enable|disable`）。
- `admin`：可使用 `PATCH /api/v1/api-keys/{id}` 更新 `key_alias`。
- 金鑰對外狀態判斷採 effective status：
  - 若 `api_keys.status='active'` 且 `expires_at < now(UTC)`，則對外一律視為 `expired`。
  - 其餘狀態沿用 `api_keys.status`（`active|revoked|expired`）。
  - 背景回填作業需定期將上述 effective `expired` 同步落地到 `api_keys.status`（與 `api_key_applications.status`）。

## API 草案
Base path：`/api/v1`

### OWASP API Security Baseline
- 正式環境僅接受 session 作為瀏覽器認證來源；不得信任前端自行送出的身分欄位。
- `dev/test` 可透過 `ALLOW_HEADER_AUTH=true` 啟用 header auth 供開發與測試使用。
- 所有 `POST`、`PATCH` 端點需驗證 `X-CSRF-Token` 與 session 內 token 一致；header auth 模式除外。
- 所有清單查詢 `page_size` 上限為 `100`。
- 稽核與統計查詢的 `from/to` 視窗上限為 `31` 天。
- `GET /api/v1/users?q=...` 查詢字串上限為 `100` 字元。
- `POST /api/v1/api-keys/{id}/reveal` 回應需帶 `Cache-Control: no-store`。
- 非 `dev/test` 環境之外部整合 URL 必須為 `https`，且不得解析到 loopback / private / link-local 位址。

### Auth Login Entry
- `GET /login`
  - 用途：導向 OAuth provider auth endpoint。
  - 規則：建立 request_id（state）並寫入 session，用於 callback 對帳。
  - Response：
    - 成功回 `302` redirect 至 OAuth provider
    - 若 OAuth 設定缺失或不合法，回 `500 INTERNAL_ERROR`
- `GET /auth/callback`
  - 用途：接收 provider callback，交換 access token，取得 basic identity claims，建立本機 session auth context。
  - 規則：
    - OAuth claims 來源：`sysId`、`cn`、`chName`、`email`、`instCode`、`tCode`
    - 映射：`account<-cn`、`name<-chName`、`department<-instCode`、`sysid<-sysId`
    - 成功時寫入 session `auth_context`（`account`、`name`、`email`、`department`、`sysid`、`role=user`）並 redirect `/`
    - state 僅可使用一次；callback 完成後需自 session 清除
    - 若缺少必要欄位（任一 `sysId`、`cn`、`chName`、`email`、`instCode`、`tCode`）需拒絕登入
    - 登入放行規則：`tCode` 以 `B` 開頭可直接放行；否則需命中 `active` 白名單（`sysid`）或 `active` 管理者名單（`admins.sysid`）
    - 成功與失敗皆須寫入 `auth_audit_logs`
    - 嚴禁落地 token/secret 類敏感資訊
  - Response：
    - 成功回 `302` redirect `/`
    - `401`：`OAUTH_STATE_MISSING`、`OAUTH_STATE_MISMATCH`
    - `403`：`LOGIN_NOT_ELIGIBLE`
    - `422`：`OAUTH_CODE_MISSING`、`OAUTH_IDENTITY_INVALID`
- `GET /api/v1/users/me`
  - 用途：回傳目前 session 使用者資訊與 CSRF token。
  - 規則：
    - 回傳欄位：`account`、`name`、`email`、`department`、`sysid`、`role`、`csrf_token`
    - 若目前帳號命中 `active admins`，`role` 需回傳 `admin`
    - 可在 `dev/test` 透過 header auth bootstrap session

### 1) 申請並核發 API Key
- `POST /api/v1/api-keys/applications`
- 前置條件：
  - 請求必須為已登入使用者（`account`、`name`、`email`、`department`、`sysid` 由 auth context 提供，並以 auth context 為準）
  - `sysid` 必須為純數字；若為非數字，回傳 `VALIDATION_ERROR`。
  - `user` 僅能以 auth context 申請本人；`admin` 可選擇代他人申請（透過 `target_identity`）
  - 申請資格必須通過：研究人員名單職稱代碼命中，或特殊人員名單 `active` 命中
  - `admin` 代申請時，後端需先依 `target_identity.account` 查人員目錄取得唯一身份，再以該身份的 `email/sysid` 檢查申請資格
  - 若研究人員名單服務失敗（timeout/5xx），本 API 回傳拒絕，不得建立申請資料
- Request：
```json
{
  "application_date": "2026-05-04",
  "duration_months": 6,
  "purpose": "integration for internal service",
  "target_identity": {
    "account": "target.user"
  }
}
```
- Response（201）：
```json
{
  "application": {
    "id": "...",
    "account": "jane.doe",
    "status": "active",
    "issued_at": "...",
    "expires_at": "..."
  },
  "issuance_status": "issued",
  "api_key_plaintext": "AS-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```
- Response（503，provider timeout/5xx）：
```json
{
  "error": {
    "code": "PROVIDER_UNAVAILABLE",
    "message": "provider unavailable"
  }
}
```

### 1-1) 全域金鑰條件設定（Admin only）
- `GET /api/v1/limit-strategy-config`
- `PATCH /api/v1/limit-strategy-config`
- 全域固定單一金鑰條件組合（皆可編輯）：
  - `budget`（額度）：`max_budget`、`budget_duration`
  - `rate_limit`（速度）：`tpm_limit`、`rpm_limit`
- 欄位語意同金鑰條件模板：
  - `max_budget`：總金額額度（USD）。
  - `budget_duration`：重置週期（`daily|weekly|monthly`）。
  - `tpm_limit`：每分鐘 Token 數限制。
  - `rpm_limit`：每分鐘請求數限制。
- 每把 API Key 需同時套用 `budget` 與 `rate_limit` 兩種限制；不提供二選一模式。
- 一般使用者不可查看或修改金鑰條件設定。
- `PATCH /api/v1/limit-strategy-config` 在 session auth 模式下，若 `X-CSRF-Token` 缺失或不正確需回 `403 FORBIDDEN`。

### 2) 查詢 API Key 清單
- `GET /api/v1/api-keys`
- 規則：`user` 僅回傳 auth 使用者本人的資料；`admin` 可查全部資料。
- 到期口徑：`expires_at` 早於查詢當下（UTC）且原始狀態為 `active` 時，API 對外狀態需視為 `expired`（即使 DB 原始欄位尚未同步更新）。
- Query（草案）：`page`, `page_size`, `status`, `owner_account`, `from`, `to`
  - `page_size` 定義為每頁顯示筆數（非全量上限）。
  - `owner_account` 僅 `admin` 可用於指定申請人篩選；`user` 不得跨人查詢
  - `from`、`to` 格式為 `YYYY-MM-DD`，基準欄位為 `application_date`
  - 前端清單需採伺服器分頁，透過 `page/page_size` 可翻頁讀取完整資料集（不限於首 20 筆）。
- Response（200）：
```json
{
  "items": [
    {
      "id": "...",
      "status": "active",
      "masked_key": "AS-...wxyz",
      "key_alias": "for_jane.doe",
      "owner_account": "jane.doe",
      "owner_name": "Jane Doe",
      "expires_at": "..."
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```
- `total` 定義為符合目前篩選條件的總筆數（非當頁 `items` 長度）。

### 2-1) 查詢每位使用者 API Key 申請統計（Admin Dashboard）
- `GET /api/v1/api-keys/statistics/users`
- 規則：僅 `admin` 可使用；回傳為申請人維度聚合結果，不得包含明文 key。
- 統計口徑：`active/revoked/expired` 與 `scope` 篩選需採相同到期口徑（`expires_at` 已過且原始 `active` 視為 `expired`）。
- Query（草案）：`page`, `page_size`, `q`, `scope`, `from`, `to`, `sort_by`, `sort_dir`
  - `scope` allowed: `all|active|revoked|expired`（預設 `all`）
  - `from`、`to` 格式為 `YYYY-MM-DD`，基準欄位為 `application_date`
  - `sort_by` 預設 `total_applications`；`sort_dir` 預設 `desc`
- Response（200）：
```json
{
  "items": [
    {
      "owner_account": "jane.doe",
      "owner_name": "Jane Doe",
      "owner_email": "jane.doe@example.com",
      "owner_department": "R&D",
      "total_applications": 12,
      "active_count": 3,
      "revoked_count": 7,
      "expired_count": 2,
      "last_applied_at": "2026-05-04"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

### 3) 查詢單筆 API Key 紀錄
- `GET /api/v1/api-keys/{id}`
- 規則：`user` 僅可查本人資料；`admin` 可查任意資料；不可回傳明文 key。
- 到期口徑：`expires_at` 早於查詢當下（UTC）且原始狀態為 `active` 時，API 對外狀態需視為 `expired`。
- 回傳 `key_alias`；若資料未設定則回傳預設值 `for_{owner_account}`。
- 回傳可包含申請人識別欄位 `owner_account`、`owner_name`（供管理者辨識申請來源）。
- 回傳應包含 `purpose` 供詳情頁顯示；若歷史資料未留存用途，前端顯示 `-`。
- 回傳應包含 `department` 供詳情頁顯示；若歷史資料未留存單位，前端顯示 `-`。
- 錯誤回應：
  - `403 FORBIDDEN` / `KEY_NOT_OWNED_BY_USER`：使用者不可查他人 key
  - `404 VALIDATION_ERROR`：key 不存在

### 3-1) 背景同步（Expired 狀態回填）
- 目的：將 `api_keys.status='active'` 且 `expires_at < now(UTC)` 的資料，批次回填為 `expired`。
- 條件：以 `api_keys.status` 與 `expires_at` 為準，不要求 `api_key_applications.status='active'`，用於修復歷史 key/app 狀態不一致資料。
- 同步範圍：需同步 `api_keys.status` 與 `api_key_applications.status`，避免跨表狀態不一致。
- 執行方式：由排程觸發腳本（如 systemd timer 或 cron）；預設每日 `00:10` 執行。
- 失敗容錯：排程失敗不得影響查詢/統計/renew 的到期口徑正確性（仍以 effective status 判斷）。
- 稽核與維運：排程需輸出執行時間、更新筆數、錯誤訊息，供維運追蹤。

### 4) 停用 API Key
- `POST /api/v1/api-keys/{id}/revoke`
- 規則：`user` 僅可停用本人 `active` key；`admin` 可停用任意 `active` key；停用為軟停用（`status=revoked`）。

### 4-2) 續發（Renew）API Key
- `POST /api/v1/api-keys/{id}/renew`
- 規則：
  - `user` 僅可續發本人 `revoked|expired` key；`admin` 可續發任意 `revoked|expired` key。
  - 續發判定口徑需與查詢一致：`expires_at` 已過且原始狀態為 `active` 時，需視為 `expired` 可續發。
  - renew 會建立新 key（`status=active`），不是把舊 key 改回 `active`。
  - 新 key 的 `duration_months` 與 `purpose` 需沿用來源 key 的原資料。
- renew 即時成功（`issuance_status=issued`）時，回傳一次性 `api_key_plaintext`。
  - renew 成功後需寄送 Email 通知申請者「已更新金鑰」；通知信不得包含明文 key。
  - 續發成功後，來源 key 對 `user` 列表需隱藏；`admin` 列表仍需可見完整歷史。

### 4-0) 更新 API Key Alias
- `PATCH /api/v1/api-keys/{id}`
- Request：
```json
{
  "key_alias": "service_internal_batch"
}
```
- 規則：僅 `admin` 可使用；`key_alias` 不可為空字串；成功後回傳更新後單筆資料。

### 4-1) 受控回取 API Key 明文（Reveal）
- `POST /api/v1/api-keys/{id}/reveal`
- 規則：僅 `admin` 可使用；此端點為受控流程，不屬一般列表/詳情查詢。
- 規則：回應需帶 `Cache-Control: no-store`。
- Response（200）：
```json
{
  "id": "...",
  "api_key_plaintext": "AS-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "key_kek_version": "v1"
}
```

### 5) 特殊人員名單管理 API（沿用受保護路徑）
- `POST /api/v1/whitelists`：新增特殊人員名單 sysid
- `GET /api/v1/whitelists`：查詢特殊人員名單列表
- `PATCH /api/v1/whitelists/{id}`：更新狀態（`active/inactive`）與備註
- 規則：僅 `admin` 可使用。
- `POST /api/v1/whitelists`、`PATCH /api/v1/whitelists/{id}` 在 session auth 模式下，若 `X-CSRF-Token` 缺失或不正確需回 `403 FORBIDDEN`。
- `POST /api/v1/whitelists` 若 `sysid` 重複需回 `409 WHITELIST_SYSID_DUPLICATED`。

### 5-1) 特殊人員名單新增前使用者查詢 API
- `GET /api/v1/users?q={keyword}`
- 用途：供管理者透過 Persnl SOAP 查詢候選人資料（供新增管理者/特殊人員前使用）。
- 規則：僅 `admin` 可使用；`q` 僅用於 `account`、`name` 查詢；回傳欄位至少包含 `id`、`sysid`、`account`、`name`、`email`、`department`（對應單位代碼 `instCode`）、`status`。
- 單位主檔同步：`Persnl.getInstitutes` 僅供背景同步作業使用（首次入庫 + 後續排程差異同步），不得放在此 API 請求路徑中每次即時呼叫。
- 錯誤回應：
  - `403 FORBIDDEN`：非 `admin`
  - `422 VALIDATION_ERROR`：`q` 不合法
  - `503 SOAP_SERVICE_UNAVAILABLE`：Persnl SOAP timeout/5xx

### 5-2) 目前使用者語言偏好 API
- `GET /api/v1/users/preferences/locale`
  - 回傳格式：`{ "preferred_locale": "zh-TW" | "en" | null }`
- `PATCH /api/v1/users/preferences/locale`
  - Request body：`{ "preferred_locale": "zh-TW" | "en" }`
  - 僅允許 `zh-TW|en`，其餘值回傳 `422 VALIDATION_ERROR`

### 前端語言規則（MVP）
- 僅支援 `zh-TW`、`en`。
- 啟動語言優先序：
  - 若 DB 已有偏好（`preferred_locale`），直接套用 DB。
  - 若 DB 無偏好（`null`），依系統語言規則判定，並立即寫回 DB 作為初始值。
- 系統語言判定規則：
  - `navigator.language` / `navigator.languages` 命中 `zh*` -> `zh-TW`
  - 命中 `en*` -> `en`
  - 其他語系 -> `en`
- 手動切換語言後，需更新 UI 文案並寫回 `preferred_locale`。
- DataGrid locale 文案需跟隨語言切換。

### 5-3) 單位主檔查詢 API
- `GET /api/v1/institutes`
- 用途：提供前端依 `department` 代碼轉換顯示文字（中/英文）。
- 規則：
  - `department` 在系統內資料儲存以代碼為主。
  - 前端顯示時依語系使用單位主檔欄位轉換（`zh-TW` 顯示 `inst_name`，`en` 顯示 `einst_name`，缺值可 fallback）。
  - 單位主檔來源為背景同步資料（`Persnl.getInstitutes`），本 API 僅回傳本地 `active` 主檔資料。
- Response（200）：
```json
{
  "items": [
    {
      "inst_code": "01",
      "inst_name": "院本部",
      "abb_inst_name": "院本部",
      "einst_name": "Headquarters",
      "division": "1"
    }
  ],
  "total": 1
}
```

### 6) 管理者啟用/停用 API
- `POST /api/v1/admins/{id}/enable`：啟用指定使用者管理者身分
- `POST /api/v1/admins/{id}/disable`：停用指定使用者管理者身分
- 規則：僅 `admin` 可使用，且需記錄操作稽核資訊（操作者、時間）。

### 6-1) 關鍵操作稽核 log（v1）
- 儲存方式：寫入 `operation_audit_logs`（DB 落地）。
- 範圍（v1）：
  - `POST /api/v1/api-keys/applications`
  - `POST /api/v1/api-keys/{id}/revoke`
  - `POST /api/v1/whitelists`
  - `PATCH /api/v1/whitelists/{id}`
  - `POST /api/v1/admins/{id}/enable`
  - `POST /api/v1/admins/{id}/disable`
  - `PATCH /api/v1/limit-strategy-config`
- 稽核欄位至少需可辨識：事件類型、動作、成功/失敗、操作者（`sysid/account/role`）、目標資源類型與 ID、`request_id`、時間、來源 IP、user-agent。
- 成功與失敗都需記錄（含權限不足、驗證失敗、資源不存在等）。
- metadata 採白名單策略，僅記錄必要且非敏感欄位。
- 若 audit 寫入失敗，不得改變原本 API 成功/失敗語意（主流程優先）。

### 6-2) 操作稽核熱資料查詢（v1）
- `GET /api/v1/operation-audit-logs`
- 規則：僅 `admin` 可使用。
- 查詢參數：`page`、`page_size`、`from`、`to`、`event_type`、`result(success|failure)`。
- 預設熱資料窗：若未提供 `from/to`，回傳最近 7 天資料。
- 排序：`created_at desc`（最新優先）。
- 回傳欄位（精簡）：`created_at`、`event_type`、`action`、`result`、`actor_account`、`target_type`、`target_id`、`error_code`。

### 6-3) 登入稽核熱資料查詢（v1）
- `GET /api/v1/auth-audit-logs`
- 規則：僅 `admin` 可使用。
- 查詢參數：`page`、`page_size`、`from`、`to`、`provider`、`result(success|failure)`。
- 預設熱資料窗：若未提供 `from/to`，回傳最近 7 天資料。
- 排序：`created_at desc`（最新優先）。
- 回傳欄位（精簡）：`created_at`、`provider`、`result`、`account`、`sysid`、`role`、`error_code`、`request_id`。
- `created_at` 格式需為 UTC `date-time`（RFC 3339，例如 `2026-05-21T08:28:20Z`）。
- 回傳不得包含敏感憑證資訊（access token、refresh token、password、client secret）。

### 7) 研究資格與目錄查詢服務（Persnl SOAP）
- 用途：供「進入系統」與「送出申請」時檢查是否命中研究人員資格。
- 資格判斷：以 Persnl SOAP 回傳之 `tCode` 判斷研究資格。
- 放行規則：`tCode` 以 `B*` 開頭者直接通過；非 `B*` 可由可配置職稱代碼清單補充放行。
- 本系統僅維護可通過之補充職稱代碼規則，不同步儲存研究人員名單明細資料。
- 回應結果：
  - 命中：可直接通過資格檢查（不需再檢查特殊人員名單）。
  - 未命中：需再檢查特殊人員名單是否為 `active`。
  - timeout/5xx：允許進入系統，但阻擋申請 API（`503 SOAP_SERVICE_UNAVAILABLE`）。

### 錯誤回應格式（建議）
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "..."
  }
}
```

建議錯誤碼：
- `VALIDATION_ERROR`
- `INVALID_APPLICATION_DATE`
- `INVALID_DURATION_MONTHS`
- `LIMIT_STRATEGY_REQUIRED`
- `LIMIT_STRATEGY_CONFLICT`
- `MISSING_BUDGET_FIELDS`
- `MISSING_RATE_LIMIT_FIELDS`
- `APPLICANT_NOT_ELIGIBLE`
- `SOAP_SERVICE_UNAVAILABLE`
- `WHITELIST_SYSID_DUPLICATED`
- `LOGIN_NOT_ELIGIBLE`
- `USER_NOT_FOUND`
- `KEY_NOT_OWNED_BY_USER`
- `KEY_NOT_ACTIVE`
- `RATE_LIMITED`
- `INTERNAL_ERROR`
- `ISSUANCE_CONFIG_INCOMPLETE`
- `APPLICATION_ALREADY_ISSUED`
- `KEY_NOT_RENEWABLE`
- `KEY_ALREADY_RENEWED`

## 驗收標準
1. 研究人員名單職稱代碼命中者可成功核發 API Key，格式為 `AS-` + 30 碼隨機字元（總長 33）。
2. 研究名單未命中但特殊人員名單 `active` 命中者可成功核發 API Key。
3. 研究名單未命中且特殊人員名單未命中者，系統不得允許進入，且申請 API 回傳 `403` 與 `APPLICANT_NOT_ELIGIBLE`。
4. Persnl SOAP 服務失敗（timeout/5xx）時，允許進入系統，但申請 API 回傳 `503` 與 `SOAP_SERVICE_UNAVAILABLE`。
5. `duration_months` 非 `1|6|12` 時，API 回傳 `INVALID_DURATION_MONTHS`。
6. `application_date` 非法或晚於申請當日，API 回傳 `INVALID_APPLICATION_DATE`。
7. 明文 key 預設僅於建立成功當下回傳一次；一般查詢端點不得回傳明文。
8. 資料庫不得存 API Key 明文；需存 `key_hash`，並可存加密密文欄位供受控 reveal 流程使用。
9. 一般使用者登入後只能看到自己的全部歷史紀錄。
10. 一般使用者查詢 API Key 時僅能看到 `masked_key`（格式 `AS-...XXXX`），不得看到明文。
10-1. `POST /api/v1/api-keys/{id}/reveal` 僅 `admin` 可使用，且可回傳明文 key。
11. 一般使用者可停用本人 `active` key，停用後狀態轉為 `revoked`。
12. 一般使用者停用非本人 key 時，API 回傳 `KEY_NOT_OWNED_BY_USER`。
13. 一般使用者停用非 `active` key 時，API 回傳 `KEY_NOT_ACTIVE`。
13-1. 一般使用者可續發本人 `revoked|expired` key；續發 `active` key 時，API 回傳 `KEY_NOT_RENEWABLE`。
13-2. 同一把舊 key 不可重複續發；重複續發時 API 回傳 `KEY_ALREADY_RENEWED`。
14. 未通過資格檢查或驗證失敗請求不得建立 `api_key_applications` 或 `api_keys` 紀錄。
15. `user` 呼叫 `GET /api/v1/api-keys` 時僅可看到本人資料；若舊 key 已被 renew，來源舊 key 對 `user` 不可見；`admin` 可看到全域完整資料。
16. `user` 查詢或停用非本人 key 時，API 回傳 `403`（或既有錯誤碼）。
17. 非 `admin` 使用特殊人員名單管理 API（`/api/v1/whitelists*`）時，回傳 `403`。
17-1. 特殊人員名單比對主鍵為 `sysid`，新增重複 `sysid` 時需回傳 `409` 與 `WHITELIST_SYSID_DUPLICATED`。
18. 管理者可成功啟用/停用其他使用者的管理者身分（`/api/v1/admins/{id}/enable|disable`）。
18-1. 管理者名單需顯示狀態欄位；停用後該管理者仍保留於名單，狀態改為 `inactive`。
19. 使用者透過 SSO/OAuth 登入後，申請頁需自動帶入 `account`、`name`、`email`、`department`、`sysid`。
20. 若 auth context 缺少 `sysid`，申請 API 回傳 `VALIDATION_ERROR` 且不得建立申請紀錄。
21. 管理者不可在前端停用自己的管理者權限（不可將自己的角色由 `admin` 降為 `user`）。
22. `admin` 呼叫 `GET /api/v1/api-keys` 時，每筆資料需可辨識申請人（至少包含 `owner_account`、`owner_name`）。
23. 調整申請人識別欄位後，既有受保護 API 路徑與角色模型（`user|admin`）不得改動。
23-1. 管理者名單與特殊人員名單新增人員查詢（`GET /api/v1/users`）僅可用 `account`、`name` 查詢，不得以 `sysid` 或 `email` 作為查詢條件。
24. API Keys 清單頁不得顯示建立時間；建立時間僅顯示於單筆詳情視窗。
25. API Key 詳情視窗需顯示用途（`purpose`）；若無資料則顯示 `-`。
26. API Key 詳情視窗需顯示單位（`department`）；若無資料則顯示 `-`。
27. 申請成功彈窗需提供明文 key 複製功能，點擊後 icon 應由複製狀態切換為成功 check，並可自動恢復。
28. `admin` 可呼叫 `GET /api/v1/api-keys/statistics/users` 取得每位申請人的統計資料，且預設依 `total_applications desc` 排序。
29. `scope=all|active|revoked|expired` 切換時，統計結果需符合對應狀態口徑。
30. 統計 API `from`、`to` 應以 `application_date` 篩選，且日期格式需為 `YYYY-MM-DD`。
31. 非 `admin` 呼叫 `GET /api/v1/api-keys/statistics/users` 時，API 回傳 `403`。
32. 統計 API 回傳不得包含 `api_key_plaintext`，且不得改變既有受保護 API 路徑與角色模型。
33. 統計 API 每筆資料需包含 `owner_department`（可為空值），供管理者統計圖表 X 軸切換使用。
34. 系統語言 `zh-TW` 首次進站時（DB 無偏好）需顯示中文。
35. 系統語言 `en-US` 首次進站時（DB 無偏好）需顯示英文。
36. 系統語言非 `zh*|en*`（例如 `ja-JP`）首次進站時（DB 無偏好）需 fallback 顯示英文。
37. 手動切換語言後，重新登入需沿用 DB 偏好。
38. `GET /api/v1/users/preferences/locale` 需回傳目前偏好（`zh-TW|en|null`）；`PATCH` 成功後可立即由 `GET` 讀回。
39. `PATCH /api/v1/users/preferences/locale` 僅允許 `zh-TW|en`；非法值（如 `ja-JP`）需回傳 `422` 與 `VALIDATION_ERROR`。
40. 首次登入 DB 無偏好時，前端需依系統語言規則決定語系並觸發一次寫回。
41. 手動切換語言後，重新登入需沿用 DB 偏好。
42. 導覽列、各頁標題與按鈕、錯誤/提示訊息、DataGrid locale 文案需隨語言切換更新。
43. `GET /api/v1/api-keys` 與 `GET /api/v1/api-keys/{id}` 回傳需包含 `key_alias`；未設定時回傳 `for_{owner_account}`。
44. `admin` 可透過 `PATCH /api/v1/api-keys/{id}` 更新 `key_alias`，`user` 呼叫同端點需回傳 `403`。
45. 管理者統計表格中 `total_applications` 與 `active_count` 可點擊，並以 Dialog 顯示對應 API Key 明細（僅 `key_alias`、`masked_key`、`status`）。
46. 管理者統計明細 Dialog 查詢口徑需跟隨當前 `from`、`to` 篩選；點擊 `active_count` 時僅顯示 `status=active`。
47. 限制策略設定僅 `admin` 可讀取與更新（`/api/v1/limit-strategy-config`）；`user` 呼叫需回 `403`。
48. 申請策略綁定僅 `admin` 可查改；`user` 呼叫需回 `403`。
49. Provider timeout/5xx 時，`POST /api/v1/api-keys/applications` 需回 `503 PROVIDER_UNAVAILABLE`，且不得建立 pending 申請。
50. `budget_duration` 僅允許 `daily|weekly|monthly`；管理端顯示映射需為 `1天|7天|30天`。
50-1. 每把 API Key 的限制策略需同時包含 `budget` 與 `rate_limit`；不得提供二選一 `issuance_mode`。
50-2. 不提供 pending 補發端點；前端不得提供待審申請頁面入口。
52. `POST /api/v1/api-keys/applications` 成功即時配發（`issuance_status=issued`）後，需寄送 Email 給申請者本人（不需寄送給管理者）。
53. 第 52 項通知信內容需中英並列（中文在前、英文在後）。
54. 第 52 項若寄信失敗，`POST /api/v1/api-keys/applications` 仍需回 `201`，且不回滾申請資料。
54-1. `POST /api/v1/api-keys/applications` 若 provider timeout/5xx，需回 `503 PROVIDER_UNAVAILABLE`。
57. 當配發模式為 `local` 時，申請與 renew 需可在不連線外部 provider 的情況下成功 `issued`。
64. `GET /login` 需可導向 OAuth provider，並附帶 state/request_id。
65. `GET /auth/callback` 成功時需建立 session auth context 並 redirect `/`。
66. `GET /auth/callback` 失敗（含 token/basic 取得失敗、必要欄位缺失、state mismatch）需回錯，且寫入 failure audit。
66-1. 正式環境不得接受 header auth 作為正式認證來源；僅 `dev/test` 可啟用。
67. OAuth 成功登入寫入的角色需固定為 `user`，不得由 OAuth payload 直接升權為 `admin`。
68. `auth_audit_logs` 不得包含 access token/refresh token/password/client secret。
69. OAuth callback 需以 claims `sysId/cn/chName/email/instCode/tCode` 建立身份；任一缺漏需拒絕登入。
70. `tCode` 以 `B` 開頭者可登入；非 `B*` 者需命中 `active` 白名單（`sysid`）或 `active` 管理者名單（`admins.sysid`），否則回 `403 LOGIN_NOT_ELIGIBLE`。
71. `admin` 可於 `POST /api/v1/api-keys/applications` 透過 `target_identity.account` 代他人送出申請；資格檢查需以目標使用者身份執行。
72. 代申請時若目錄服務查無帳號或帳號不唯一，API 回傳 `422 VALIDATION_ERROR`；若 Persnl SOAP timeout/5xx，API 回傳 `503 SOAP_SERVICE_UNAVAILABLE`。
73. `POST /api/v1/api-keys/applications`、`POST /api/v1/api-keys/{id}/revoke`、`POST /api/v1/api-keys/{id}/renew`、`POST /api/v1/whitelists`、`PATCH /api/v1/whitelists/{id}`、`POST /api/v1/admins/{id}/enable`、`POST /api/v1/admins/{id}/disable`、`PATCH /api/v1/limit-strategy-config` 成功時皆需寫入 `operation_audit_logs`。
74. 第 73 項 8 個 API 失敗時（含 `403/404/409/422`）皆需寫入 failure audit，且需可辨識 `error_code`。
75. `operation_audit_logs` 不得包含 API key 明文或其他敏感憑證（token/password/client secret）。
76. `operation_audit_logs.metadata_json` 僅允許白名單欄位（例如 `application_id`、`key_id`、`whitelist_id`、`target_admin_id`、`status`、`duration_months`），不得落地原始敏感 payload。
77. 關鍵操作稽核功能不得改動既有受保護 API 路徑與角色模型（`user|admin`）。
78. `GET /api/v1/operation-audit-logs` 僅 `admin` 可呼叫，`user` 呼叫需回 `403`。
79. 操作稽核查詢在未提供 `from/to` 時，需預設回傳最近 7 天熱資料。
80. 操作稽核查詢結果需依 `created_at desc` 排序，並支援 `page/page_size` 分頁。
81. 操作稽核查詢需支援 `event_type` 與 `result` 篩選，且回傳不得包含敏感憑證資訊。
82. `GET /api/v1/auth-audit-logs` 僅 `admin` 可呼叫，`user` 呼叫需回 `403`。
83. 登入稽核查詢在未提供 `from/to` 時，需預設回傳最近 7 天熱資料。
84. 登入稽核查詢結果需依 `created_at desc` 排序，並支援 `page/page_size` 分頁。
85. 登入稽核查詢需支援 `provider` 與 `result` 篩選，且回傳不得包含敏感憑證資訊。
86. `GET /api/v1/api-keys` 與 `GET /api/v1/api-keys/{id}` 回傳狀態需以 `expires_at` 即時計算到期口徑；已過期者對外顯示為 `expired`。
87. `POST /api/v1/api-keys/{id}/renew` 判定需採與查詢一致的到期口徑；已過期且未續發過之 key 可續發。
88. `GET /api/v1/api-keys/statistics/users` 的 `scope` 與 `active/revoked/expired` 計數需採同一到期口徑，避免已過期 key 被算入 `active`。
89. 即使 expired 回填排程停用或失敗，`GET /api/v1/api-keys`、`GET /api/v1/api-keys/{id}`、`GET /api/v1/api-keys/statistics/users` 仍需依 effective status 正確呈現 expired。
90. expired 回填排程成功後，符合條件的 `api_keys.status` 與 `api_key_applications.status` 需落地更新為 `expired`，且不得誤改 `revoked` 資料。
91. `GET /api/v1/users/me` 需回傳目前使用者資料與 `csrf_token`。
92. 所有 `POST/PATCH` 端點在 session auth 模式下，缺少或錯誤 `X-CSRF-Token` 需回 `403 FORBIDDEN`。
93. `GET /api/v1/api-keys/statistics/users`、`GET /api/v1/operation-audit-logs`、`GET /api/v1/auth-audit-logs` 的 `from/to` 查詢區間不得超過 `31` 天。
94. `GET /api/v1/users?q=...` 的 `q` 長度不得超過 `100` 字元。
95. `POST /api/v1/api-keys/{id}/reveal` 回應需包含 `Cache-Control: no-store`。

## Roadmap
### Phase 1：Foundation
- 建立後端專案骨架與資料表 migration
- 實作 `api_key_whitelist`、`api_key_applications`、`api_keys` 基礎模型
- 建立基本錯誤處理與日誌

### Phase 2：MVP API
- 完成特殊人員名單管理 API（沿用 `/api/v1/whitelists*` 路徑；新增、查詢、停用/啟用）
- 完成申請核發、本人清單查詢、本人單筆查詢、本人停用 API
- 完成管理端查詢/撤銷 API
- 完成研究人員名單職稱代碼檢查、特殊人員名單檢查、申請欄位驗證、生效時長（月）驗證與一次性明文回傳邏輯
- 補齊 API 測試（成功、驗證失敗、安全性、權限）

### Phase 3：MVP Console UI
- 完成 Apply/My API Keys/API Key Detail Dialog/Whitelist Admin 頁面
- 串接 API 與錯誤提示
- 完成端到端流程驗收

### Phase 4：Expansion
- 串接 OAuth/SSO（完善 `sysid` 與外部身分系統整合）
- 增加多安全等級策略與可配置 key 長度
- 規劃審核流程與配額管理

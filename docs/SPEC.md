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
5. 資格檢查通過後系統建立 pending 申請，待管理者審理選擇核發模式後立即補發 API Key。
5-1. 建立 pending 申請後，系統需寄送 Email 給所有 `active` 管理者（通知有新申請待審）與申請者本人（通知已收到申請、請等待配發）。
6. 系統只顯示一次明文 API Key，使用者需立即保存。
7. 一般使用者可在「我的 API Key 紀錄」查看本人全部歷史紀錄（`active|revoked|expired`），Key 僅顯示遮罩（`AS-...` + 後 4 碼）。
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
- 顯示範圍：僅本人帳號的全部歷史紀錄（`active|revoked|expired`）。
- 顯示欄位：申請日期、生效時長、狀態、到期時間、遮罩 key（`AS-...` + 後 4 碼）。
- 管理者在同頁可額外查看申請人識別欄位（`owner_account`、`owner_name`）。
- 管理者在同頁可查看並編輯 `key_alias`；若資料未設定，預設顯示 `for_{owner_account}`。
- 操作：僅對本人 `active` key 顯示「停用」按鈕。

### 3) API Key Detail Dialog（詳情視窗）
- 顯示完整申請資訊與狀態。
- 顯示欄位至少包含：申請日期、生效時長、用途（`purpose`）、單位（`department`）、建立時間、到期時間、遮罩 key。
- 一般使用者僅可查本人資料。
- 一般使用者可停用本人 `active` key。
- 一般查詢/詳情不可再次顯示 key 明文（僅受控 reveal 流程可回取）。
- 管理者可於詳情視窗編輯 `key_alias`。

### 4) Whitelist Admin Page（特殊人員名單管理頁）
- 可用 `sysid`、`account`、`name`、`email` 查詢使用者後加入特殊人員名單。
- 可查詢特殊人員名單與狀態。
- 可停用/啟用特殊人員名單條目。

### 5) Admin List Page（管理者名單頁）
- 僅 `admin` 可使用。
- 列表僅顯示目前已啟用管理權限（`role=admin`）的人員。
- 列表需顯示管理者狀態（`active`/`inactive`），停用後不得自動從名單移除。
- 可用 `sysid`、`account`、`name`、`email` 查詢使用者。
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
- 僅符合資格的人員可進入系統與申請 API Key（研究人員名單職稱代碼命中，或特殊人員名單 `active` 命中）
- 特殊人員名單管理能力（新增、查詢、停用/啟用）
- 研究人員名單由外部服務提供並以職稱代碼判斷
- 本系統不同步維護本地研究人員名單；申請時以外部服務即時查詢為準
- 外部研究人員服務失敗（timeout/5xx）時：允許進入系統，但阻擋申請
- 申請後進入 pending 佇列，由管理者逐筆選模式後立即補發 API Key
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
- `issuance_status` (enum: `issued` | `pending`)
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

### Entity: `notifications`
- `id` (string/uuid)
- `sysid` (integer, required；通知收件者，對應 auth context 的 `sysid`)
- `type` (string, required)
- `title` (string, required)
- `message` (string, required)
- `is_read` (bool, required)
- `metadata_json` (string, nullable)
- `email_delivery_status` (string, nullable)
- `email_error` (string, nullable)
- `created_at` (datetime)
- `read_at` (datetime, nullable)

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

## 權限規則（MVP）
- `user`：可使用 `GET /api/v1/api-keys`、`GET /api/v1/api-keys/{id}`、`POST /api/v1/api-keys/{id}/revoke`，但僅可查詢/停用本人 `active` key。
- `user`：不可更新 `key_alias`。
- `admin`：可查詢全部 API Key 與申請紀錄，可管理特殊人員名單（沿用受保護路徑 `/api/v1/whitelists*`），可啟用/停用其他使用者管理者身分（沿用受保護路徑 `/api/v1/admins/{id}/enable|disable`）。
- `admin`：可使用 `PATCH /api/v1/api-keys/{id}` 更新 `key_alias`。
- 金鑰啟用狀態以 `api_keys.status` 為唯一判斷來源：`active`=啟用，`revoked|expired`=不可用。

## API 草案
Base path：`/api/v1`

### Auth Login Entry
- `GET /login`
  - 用途：導向 OAuth provider auth endpoint。
  - 規則：建立 request_id（state）並寫入 session，用於 callback 對帳。
- `GET /auth/callback`
  - 用途：接收 provider callback，交換 access token，取得 basic identity claims，建立本機 session auth context。
  - 規則：
    - OAuth claims 來源：`sysId`、`cn`、`chName`、`email`、`instCode`、`tCode`
    - 映射：`account<-cn`、`name<-chName`、`department<-instCode`、`sysid<-sysId`
    - 成功時寫入 session `auth_context`（`account`、`name`、`email`、`department`、`sysid`、`role=user`）並 redirect `/`
    - 若缺少必要欄位（任一 `sysId`、`cn`、`chName`、`email`、`instCode`、`tCode`）需拒絕登入
    - 登入放行規則：`tCode` 以 `B` 開頭可直接放行；否則需命中 `active` 白名單（`sysid`）或 `active` 管理者名單（`admins.sysid`）
    - 成功與失敗皆須寫入 `auth_audit_logs`
    - 嚴禁落地 token/secret 類敏感資訊

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
  "api_key_plaintext": "AS-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "pending_reason": null
}
```
- Response（201，provider timeout/5xx）：
```json
{
  "application": {
    "id": "...",
    "account": "jane.doe",
    "status": "active",
    "issued_at": "...",
    "expires_at": "..."
  },
  "issuance_status": "pending",
  "api_key_plaintext": null,
  "pending_reason": "awaiting_admin_mode_selection"
}
```

### 1-1) 全域金鑰條件設定（Admin only）
- `GET /api/v1/limit-strategy-config`
- `PATCH /api/v1/limit-strategy-config`
- 全域固定兩種模式設定（皆可編輯）：
  - `budget`（額度）：`max_budget`、`budget_duration`
  - `rate_limit`（速度）：`tpm_limit`、`rpm_limit`
- 欄位語意同金鑰條件模板：
  - `max_budget`：總金額額度（USD）。
  - `budget_duration`：重置週期（`daily|weekly|monthly`）。
  - `tpm_limit`：每分鐘 Token 數限制。
  - `rpm_limit`：每分鐘請求數限制。
- 全域設定提供兩種模式的參數來源；pending 審理時由 admin 逐筆選擇 `budget|rate_limit` 後立即補發。
- 一般使用者不可查看或修改金鑰條件設定。

### 1-2) Pending 申請審理（Admin only）
- `GET /api/v1/api-keys/applications/pending`
- `PATCH /api/v1/api-keys/applications/{id}/issuance-mode`
- `POST /api/v1/api-keys/applications/{id}/issue`
- 規則：
  - pending 申請可由 admin 設定 `issuance_mode`（`budget|rate_limit`）。
  - admin 觸發 `issue` 後，系統讀取該筆 mode 與全域設定參數執行補發。
  - 配發來源支援 `external|local`；`local` 模式需強制使用系統內建產 key 流程，不呼叫外部 provider。
  - 成功時 `issuance_status=issued`；失敗時維持 `pending`。
  - `issue` 成功後需寄送「已配發」Email 給申請者本人。
  - 「已配發」Email 內容需中英並列（中文在前、英文在後）。
  - 「已配發」Email 不得包含 `Application ID`。
  - 若「已配發」Email 發送失敗，不可影響 `issued` 結果；API 仍回 `200`，並於 response 回傳 `email_warning` 提示。
  - 本階段語言偏好功能停用（見 5-2）。
  - 申請建立後的 Email 通知採中英並列內容（中文在前、英文在後）。
  - 申請建立後若 Email 發送失敗，不可影響申請建立結果；API 仍回 `201`，並以後端 log 記錄失敗。

### 1-3) 通知中心
- `GET /api/v1/notifications`
- `PATCH /api/v1/notifications/{id}/read`
- 規則：
  - 僅可查詢與操作本人 `sysid` 的通知資料。
  - `PATCH /notifications/{id}/read` 僅可標記本人通知；管理者不得代替他人標記已讀。
  - 通知文案需支援 `zh-TW|en` 切換，並由前端依通知 `type` 與 `metadata` 產生對應語系顯示。
  - `PATCH /notifications/{id}/read` 於 `api_key_issued` 通知首次由本人標記已讀時，可回傳一次性 `api_key_plaintext`；後續重複已讀不得再次回傳明文。
  - 通知中心 Dialog 保存提醒文案由前端 i18n 顯示單一語言（`zh-TW` 或 `en`），不得中英並列。

### 2) 查詢 API Key 清單
- `GET /api/v1/api-keys`
- 規則：`user` 僅回傳 auth 使用者本人的資料；`admin` 可查全部資料。
- Query（草案）：`page`, `page_size`, `status`, `owner_account`, `from`, `to`
  - `owner_account` 僅 `admin` 可用於指定申請人篩選；`user` 不得跨人查詢
  - `from`、`to` 格式為 `YYYY-MM-DD`，基準欄位為 `application_date`
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

### 2-1) 查詢每位使用者 API Key 申請統計（Admin Dashboard）
- `GET /api/v1/api-keys/statistics/users`
- 規則：僅 `admin` 可使用；回傳為申請人維度聚合結果，不得包含明文 key。
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
- 回傳 `key_alias`；若資料未設定則回傳預設值 `for_{owner_account}`。
- 回傳可包含申請人識別欄位 `owner_account`、`owner_name`（供管理者辨識申請來源）。
- 回傳應包含 `purpose` 供詳情頁顯示；若歷史資料未留存用途，前端顯示 `-`。
- 回傳應包含 `department` 供詳情頁顯示；若歷史資料未留存單位，前端顯示 `-`。

### 4) 停用 API Key
- `POST /api/v1/api-keys/{id}/revoke`
- 規則：`user` 僅可停用本人 `active` key；`admin` 可停用任意 `active` key；停用為軟停用（`status=revoked`）。

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

### 5-1) 特殊人員名單新增前使用者查詢 API
- `GET /api/v1/users?q={keyword}`
- 用途：供管理者查詢既有管理者名單（`admins`）資料。
- 規則：僅 `admin` 可使用；回傳欄位至少包含 `id`、`sysid`、`account`、`name`、`email`、`status`。

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

### 6) 管理者啟用/停用 API
- `POST /api/v1/admins/{id}/enable`：啟用指定使用者管理者身分
- `POST /api/v1/admins/{id}/disable`：停用指定使用者管理者身分
- 規則：僅 `admin` 可使用，且需記錄操作稽核資訊（操作者、時間）。

### 7) 外部研究人員名單服務（整合介面）
- 用途：供「進入系統」與「送出申請」時檢查是否命中研究人員資格。
- 資格判斷：以外部服務回傳之職稱代碼判斷是否符合研究人員資格。
- 本系統僅維護可通過之職稱代碼規則，不同步儲存研究人員名單明細資料。
- 回應結果：
  - 命中：可直接通過資格檢查（不需再檢查特殊人員名單）。
  - 未命中：需再檢查特殊人員名單是否為 `active`。
  - timeout/5xx：允許進入系統，但阻擋申請 API。

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
- `RESEARCH_LIST_SERVICE_UNAVAILABLE`
- `WHITELIST_SYSID_DUPLICATED`
- `LOGIN_NOT_ELIGIBLE`
- `USER_NOT_FOUND`
- `KEY_NOT_OWNED_BY_USER`
- `KEY_NOT_ACTIVE`
- `RATE_LIMITED`
- `INTERNAL_ERROR`
- `APPLICATION_NOT_PENDING`
- `ISSUANCE_MODE_REQUIRED`
- `ISSUANCE_MODE_INVALID`
- `ISSUANCE_CONFIG_INCOMPLETE`
- `APPLICATION_ALREADY_ISSUED`

## 驗收標準
1. 研究人員名單職稱代碼命中者可成功核發 API Key，格式為 `AS-` + 30 碼隨機字元（總長 33）。
2. 研究名單未命中但特殊人員名單 `active` 命中者可成功核發 API Key。
3. 研究名單未命中且特殊人員名單未命中者，系統不得允許進入，且申請 API 回傳 `403` 與 `APPLICANT_NOT_ELIGIBLE`。
4. 研究人員名單服務失敗（timeout/5xx）時，允許進入系統，但申請 API 回傳 `503` 與 `RESEARCH_LIST_SERVICE_UNAVAILABLE`。
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
14. 未通過資格檢查或驗證失敗請求不得建立 `api_key_applications` 或 `api_keys` 紀錄。
15. `user` 呼叫 `GET /api/v1/api-keys` 時僅可看到本人資料；`admin` 可看到全域資料。
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
49. Provider timeout/5xx 或金鑰條件設定不完整時，系統需建立 application 並回 `201` + `issuance_status=pending`，且 `api_key_plaintext` 為 `null`。
50. `budget_duration` 僅允許 `daily|weekly|monthly`；管理端顯示映射需為 `1天|7天|30天`。
51. `GET/PATCH /api/v1/notifications*` 需可用，且僅可查詢/操作本人 `sysid` 的通知資料。
52. `POST /api/v1/api-keys/applications` 成功建立 pending 後，需寄送 Email 給所有 `active` 管理者與申請者本人。
53. 第 52 項通知信內容需中英並列（中文在前、英文在後）。
54. 第 52 項若寄信失敗，`POST /api/v1/api-keys/applications` 仍需回 `201`，且不回滾申請資料。
55. `POST /api/v1/api-keys/applications/{id}/issue` 成功配發後，需寄送「已配發」Email 給申請者本人。
56. 第 55 項若寄信失敗，`issue` 仍需維持 `issued` 且回傳 `email_warning`。
57. 當配發模式為 `local` 時，`issue` 需可在不連線外部 provider 的情況下成功 `issued`。
58. 第 55 項通知信內容需中英並列（中文在前、英文在後）。
59. 第 55 項通知信不得包含 `Application ID`。
60. `PATCH /api/v1/notifications/{id}/read` 僅通知本人可操作；即使為 `admin` 也不得代替他人已讀。
61. `api_key_issued` 通知首次由本人標記已讀時，API 可回傳一次性 `api_key_plaintext`；後續重複已讀不得再次回傳明文。
62. 通知中心文案需支援 `zh-TW|en` 切換，且僅單筆 `PATCH /api/v1/notifications/{id}/read` 可用於已讀操作。
63. 通知中心金鑰 Dialog 提示文案需依目前語系顯示單一語言，不得中英並列。
64. `GET /login` 需可導向 OAuth provider，並附帶 state/request_id。
65. `GET /auth/callback` 成功時需建立 session auth context 並 redirect `/`。
66. `GET /auth/callback` 失敗（含 token/basic 取得失敗、必要欄位缺失、state mismatch）需回錯，且寫入 failure audit。
67. OAuth 成功登入寫入的角色需固定為 `user`，不得由 OAuth payload 直接升權為 `admin`。
68. `auth_audit_logs` 不得包含 access token/refresh token/password/client secret。
69. OAuth callback 需以 claims `sysId/cn/chName/email/instCode/tCode` 建立身份；任一缺漏需拒絕登入。
70. `tCode` 以 `B` 開頭者可登入；非 `B*` 者需命中 `active` 白名單（`sysid`）或 `active` 管理者名單（`admins.sysid`），否則回 `403 LOGIN_NOT_ELIGIBLE`。
71. `admin` 可於 `POST /api/v1/api-keys/applications` 透過 `target_identity.account` 代他人送出申請；資格檢查需以目標使用者身份執行。
72. 代申請時若目錄服務查無帳號或帳號不唯一，API 回傳 `422 VALIDATION_ERROR`；若目錄服務 timeout/5xx，API 回傳 `503 DIRECTORY_SERVICE_UNAVAILABLE`。

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

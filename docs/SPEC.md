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
1. 使用者透過 SSO/OAuth 登入時，系統先檢查進入資格：優先查本系統特殊人員名單（`sysid` 且 `active`），再查管理者名單（`admins.id=sysid` 且 `active`），兩者都未命中才檢查 `tCode` 是否命中 `LOGIN_ALLOWED_TITLE_CODES`。
2. 通過進入資格後進入申請頁，系統自動帶入 `account`、`name`、`email`、`department`、`sysid`（對應 OAuth claims：`cn`、`chName`、`email`、`instCode`、`sysId`）。
3. 一般使用者填寫申請日期、用途與 API 生效時長；管理者可選擇代他人送出申請，僅需填寫目標 `account`，其餘身份欄位由系統查詢補齊。
4. 送出申請時依 `POST /main/api/v1/api-keys/applications` 契約再次檢查資格與 request/auth 驗證。
5. 資格檢查通過後系統立即核發 API Key 並回傳一次性明文；不需經過常態管理者審核。成功回應不得等待成功通知信送達後才返回。若 provider timeout/5xx，系統直接回傳 `503 PROVIDER_UNAVAILABLE`，且不得建立 pending 申請。
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
  - `application_date` 格式為 `YYYY-MM-DD` 且不得晚於申請當日
  - `duration_months` 僅允許 `1|6|12`
  - 送出申請時的 auth context 驗證、資格檢查、錯誤碼與 provider/SOAP 錯誤語意，以 `POST /main/api/v1/api-keys/applications` 契約為準
  - `admin` 代申請時，`target_identity.account` 必填；目標 `name`、`email`、`department`、`sysid` 由後端目錄查詢補齊
  - `admin` 代申請時，前端於 `target_identity.account` 欄位 `blur` 後需呼叫 `GET /main/api/v1/users?q=...` 查詢目標身份資料並帶入唯讀欄位
  - 若查詢結果多筆，前端需顯示候選清單供 `admin` 明確選擇；未完成選擇前不得送出申請
  - `admin` 代申請時，若帳號查無需顯示「查無帳號」；若查詢服務異常需顯示 `soap service unavailable`，兩者皆以獨立 `error` alert 顯示於上述 info 提示之後
  - 限制策略由管理者透過模板資源維護；一般使用者申請時不可提交策略細節
- 成功送出後顯示一次性 key，並提供複製操作；複製成功需有明確視覺回饋（check icon 後恢復）。
- 複製流程以 Clipboard API 為唯一可驗證複製路徑；若不可用或複製失敗，需提示使用者手動複製。
- 透過複製 icon 觸發時不得要求使用者先反白金鑰文字，系統需直接完成複製。

### 2) My API Keys Page（一般使用者我的紀錄頁）
- 顯示範圍：僅本人帳號歷史紀錄（`active|revoked|expired`）；若舊 key 已被 renew，對一般使用者隱藏。
- 顯示欄位：申請日期、生效時長、狀態、到期時間、遮罩 key（`AS-...` + 後 4 碼）。
- 管理者在同頁可額外查看申請人識別欄位（`owner_account`、`owner_name`）。
- 管理者在同頁可查看並編輯 `key_alias`；若資料未設定，預設顯示系統產生 alias（初始為 `for_{owner_account}`，若 provider 回報衝突則自動改為 `for_{owner_account}_vN`）。
- 操作：
  - 對 `active` key 顯示「停用」與「展延（extend）」按鈕。
  - 對 `expired` key 顯示「展延（extend）」按鈕（icon + 文字）。
  - 對 `revoked` key 顯示「續發（renew）」按鈕（icon + 文字）。
  - `user` 的 `active` key 僅在已寄送到期提醒（`expiration_notice_sent_at` 非空）時顯示展延按鈕；`expired` key 一律顯示展延按鈕；`admin` 不受此限制。
  - extend 需以 Dialog 讓使用者選擇 `duration_months=1|6|12` 後送出。
  - renew 會建立新 key，來源 key 對 `user` 列表需隱藏。
  - extend 會沿用原 key，只延長有效期限。

### 3) API Key Detail Dialog（詳情視窗）
- 顯示完整申請資訊與狀態。
- 顯示欄位至少包含：申請日期、生效時長、用途（`purpose`）、單位（`department`）、建立時間、到期時間、遮罩 key。
- 一般使用者僅可查本人資料。
- 一般使用者可停用本人 `active` key。
- 一般查詢/詳情不可再次顯示 key 明文（僅受控 reveal 流程可回取）。
- 管理者可於詳情視窗編輯 `key_alias`。

### 4) Whitelist Admin Page（特殊人員名單管理頁）
- 可用 `account`、`name` 查詢使用者後加入特殊人員名單。
- 可查詢特殊人員名單與狀態，列表需顯示 `account`、`name`、`email`。
- 可停用/啟用特殊人員名單條目。
- 可刪除特殊人員名單條目（實體刪除）。

### 5) Admin List Page（管理者名單頁）
- 僅 `admin` 可使用。
- 列表僅顯示目前已啟用管理權限（`role=admin`）的人員。
- 列表需顯示管理者狀態（`active`/`inactive`），停用後不得自動從名單移除。
- 可用 `account`、`name` 查詢使用者。
- 可啟用一般使用者的管理者權限（對應 `enable`）。
- 可停用其他管理者的管理者權限（對應 `disable`）。
- 可新增管理者（對應 `PUT /main/api/v1/admins/{id}`，建立後狀態為 `active`）。
- 可刪除停用中的管理者（對應 `DELETE /main/api/v1/admins/{id}`，僅允許 `inactive`）。
- 前端需阻擋管理者對自己執行管理者停用（避免誤鎖管理權限）。
- 前端在「新增管理者」查詢結果中，對已存在於管理者名單（`active` 或 `inactive`）的人員，不得顯示新增按鈕。

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

### 6-1) Institute View Page（單位代碼資料檢視頁）
- 僅 `admin` 可使用。
- 目的：供管理者確認 DB `institutes` 資料是否已寫入。
- 資料來源僅 `GET /main/api/v1/institutes`（僅顯示 `active` institutes）。
- 頁面需顯示 `total` 與列表資料，欄位至少包含：`inst_code`、`inst_name`、`abb_inst_name`、`einst_name`、`division`。
- 需提供 Loading、Empty、Error（含重試）狀態。

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
- Login denied（公開頁）：當 OAuth callback 判定 `LOGIN_NOT_ELIGIBLE` 時，前端需停留於 `/main/login-denied?error=LOGIN_NOT_ELIGIBLE` 顯示「沒有登入權限」訊息，且不得要求已有 session 才能顯示。
- 前端所有使用者可見 datetime（如 `created_at`、`updated_at`、`issued_at`、`expires_at` 與稽核 log 時間）需固定顯示為 `Asia/Taipei`；後端 API payload 與業務判定口徑仍維持 UTC。

## 功能需求
### Must Have（MVP）
- 權限模型僅區分 `user` 與 `admin`
- 提供 OAuth/SSO 登入入口（`GET /main/login`、`GET /main/auth/callback`）並建立 session auth context
- 正式環境僅允許以 session auth context 驗證；header auth 僅限 `dev/test`
- 環境設定檔載入需支援 `ENV_FILE`（正式部署建議 `/home/app/config/.env`）；未設定時可回退 `backend/.env`
- 所有會變更資料的 API 皆需通過 CSRF 驗證
- 僅符合資格的人員可進入系統與申請 API Key（研究人員名單職稱代碼命中，或特殊人員名單 `active` 命中）
- 特殊人員名單管理能力（新增、查詢、停用/啟用）
- 研究人員名單由外部服務提供並以職稱代碼判斷
- 本系統不同步維護本地研究人員名單；申請時以外部服務即時查詢為準
- 外部研究人員服務失敗（timeout/5xx）時：允許進入系統，但阻擋申請
- 申請成功時立即核發 API Key，且成功通知信不得延遲成功回應；provider timeout/5xx 時直接回傳 `503 PROVIDER_UNAVAILABLE`
- 需提供 API Key 到期前 `30|14|7|3|1` 天多段式提醒信機制，通知申請者本人可進行展延
- API 生效時長固定月數選單（`1|6|12`）
- API Key 格式固定為 `AS-` + 30 碼隨機字元（總長 33）
- API Key 明文只顯示一次
- 系統儲存 `key_hash` 與加密密文（`key_ciphertext`），不直接儲存明文
- API Key lifecycle 採 `External SoT + Encrypted Local Secret`：`applications/create`、`renew`、`extend`、`revoke` 皆以 provider 結果為主，本地僅於 provider 成功後同步狀態
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

### API Key Lifecycle Authority
- provider 為 API key lifecycle 的 source of truth：建立、續發（renew）、展延（extend）、停用（revoke）都需先完成 provider 操作，才可同步本地 `api_keys` 與 `api_key_applications`。
- 本地僅保存驗證與受控回取所需資料：`key_hash`、`key_ciphertext`、`key_kek_version`；不得額外落地明文 key。
- 當 provider 操作需要舊明文 key 時，後端必須從 `key_ciphertext` 解密，僅可在服務記憶體中短暫使用，直接 server-to-server 呼叫 provider。
- 舊明文 key 與新明文 key 不得出現在 DB 欄位、request/response log、audit log、exception message、暫存檔、持久化 job payload。
- `POST /main/api/v1/api-keys/{id}/reveal` 僅為 break-glass 流程；不得作為一般 `renew`、`extend`、`revoke` 的前置步驟或人工 workaround。
- 若目標 key 缺少 `key_ciphertext` 或 `key_kek_version`，或解密失敗，`renew`、`extend`、`revoke` 必須立即失敗，不得呼叫 provider，也不得變更本地狀態。
- provider timeout / 5xx / 明確拒絕時，本地不得先行更新狀態；若 provider 已成功但本地同步失敗，需保留可追蹤資訊並支援 retry / reconciliation。
- `renew`、`extend`、`revoke` 需具備 idempotency 設計；若 provider 無原生 idempotency，需以本地 request fingerprint 或 operation record 補強去重。

## 資料模型草案
### Entity: `users`（已移除）
- `users` table 已自本階段移除。
- 管理者資料來源為 `admins`。

### Entity: `admins`（管理者名單來源）
- `id` (integer/bigint, required；對應 auth `sysid`)
- `account` (string, required, unique)
- `email` (string, required, unique, lowercase)
- `name` (string, required)
- `department` (string, nullable)
- `status` (enum: `active` | `inactive`)
- `created_by` (string)
- `updated_by` (string)
- `created_at` (datetime)
- `updated_at` (datetime)
- 部署遷移規則：可透過 migration 將既有環境中的管理者資料一次性回填/校正到 `admins`，且該 migration 必須可重跑（idempotent）。

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
- `name` (string, required)
- `email` (string, required)
- `department` (string, required)
- `application_date` (date, required)
- `duration_months` (int, required, allowed: `1|6|12`)
- `purpose` (string, required)
- `status` (enum: `active` | `revoked` | `expired`)
- `issued_at` (datetime)
- `expires_at` (datetime)
- `revoked_at` (datetime, nullable)
- `sysid` (integer, required, SSO/OAuth 主體唯一識別碼)
- `is_proxy_submission` (bool, required；是否為管理者代申請)
- `proxy_operator_account` (string, nullable；僅代申請時記錄實際代送的 admin account)
- `created_at` (datetime)
- `updated_at` (datetime)
- 欄位語意：
  - application ownership 以申請人快照欄位（`account`、`name`、`email`、`department`、`sysid`）為準
  - `is_proxy_submission = false` 時，`proxy_operator_account = NULL`
  - `is_proxy_submission = true` 時，`proxy_operator_account` 需記錄實際代送的 `admin account`
  - 完整操作者身份應透過 `operation_audit_logs` 取得，不重複存放於 application row

### Entity: `api_keys`
- `id` (string/uuid)
- `application_id` (fk -> api_key_applications.id)
- `key_hash` (string, required)
- `masked_key` (string, 遮罩格式固定為 `AS-...` + 後 4 碼；response only)
- `key_alias` (string, nullable；顯示預設值為系統產生 alias，初始為 `for_{owner_account}`，必要時自動補 `_vN`，可由 admin 更新)
- `key_ciphertext` (string, encrypted at rest, nullable for legacy rows)
- `key_kek_version` (string, key-encryption-key version tag)
- `length` (int, MVP 固定 30，表示隨機段長度，不含 `AS-` 前綴)
- `security_level` (enum, MVP 固定 `high`)
- `status` (enum: `active` | `revoked` | `expired`)
- `expiration_notice_sent_at` (datetime, nullable；本輪首次成功寄出任一到期提醒後填值)
- `created_at` (datetime)

### Entity: `api_key_expiration_notices`
- `id` (string/uuid)
- `key_id` (fk -> api_keys.id)
- `application_id` (fk -> api_key_applications.id)
- `expires_at_snapshot` (datetime, required；記錄本輪提醒對應的到期時間快照)
- `notice_days_before` (int, required；允許值 `30|14|7|3|1`)
- `status` (enum: `sent` | `failed`)
- `sent_at` (datetime, nullable；成功寄送時間)
- `error_message` (string, nullable；失敗原因摘要)
- `created_at` (datetime)
- 唯一性語意：
  - 同一把 key、同一個 `expires_at_snapshot`、同一個 `notice_days_before`，最多只能有一筆成功提醒紀錄。
  - 同一把 key 若 extend 後 `expires_at` 改變，需允許建立新一輪提醒紀錄。
  - 失敗紀錄不得阻止後續重試；只要同提醒時段尚未成功，後續排程仍可再次嘗試。

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
- `user`：可使用 `GET /main/api/v1/api-keys`、`GET /main/api/v1/api-keys/{id}`、`POST /main/api/v1/api-keys/{id}/revoke`、`POST /main/api/v1/api-keys/{id}/renew`、`POST /main/api/v1/api-keys/{id}/extend`，僅可操作本人 key。
- `user`：不可更新 `key_alias`。
- `admin`：可查詢全部 API Key 與申請紀錄，可管理特殊人員名單（沿用受保護路徑 `/main/api/v1/whitelists*`），可啟用/停用其他使用者管理者身分（沿用受保護路徑 `/main/api/v1/admins/{id}/enable|disable`）。
- `admin`：可使用 `PATCH /main/api/v1/api-keys/{id}` 更新 `key_alias`。
- 金鑰對外狀態判斷採 effective status：
  - 若 `api_keys.status='active'` 且 `expires_at < now(UTC)`，則對外一律視為 `expired`。
  - 其餘狀態沿用 `api_keys.status`（`active|revoked|expired`）。
  - 背景回填作業需定期將上述 effective `expired` 同步落地到 `api_keys.status`（與 `api_key_applications.status`）。

## API 草案
Base path：`/main/api/v1`

### OWASP API Security Baseline
- 正式環境僅接受 session 作為瀏覽器認證來源；不得信任前端自行送出的身分欄位。
- `dev/test` 可透過 `ALLOW_HEADER_AUTH=true` 啟用 header auth 供開發與測試使用。
- 所有 `POST`、`PATCH` 端點需驗證 `X-CSRF-Token` 與 session 內 token 一致；header auth 模式除外。
- 所有清單查詢 `page_size` 上限為 `100`。
- 稽核與統計查詢的 `from/to` 視窗上限為 `31` 天。
- `GET /main/api/v1/users?q=...` 查詢字串上限為 `100` 字元。
- `POST /main/api/v1/api-keys/{id}/reveal` 回應需帶 `Cache-Control: no-store`。
- 非 `dev/test` 環境之外部整合 URL 必須為 `https`，且不得解析到 loopback / private / link-local 位址。

### Auth Login Entry
- `GET /main/login`
  - 用途：
    - `prod`：導向 OAuth provider auth endpoint
    - `dev/test`：直接建立 session auth context（OAuth bypass）
  - 規則：
    - `dev/test`：以 `DEV_LOGIN_ACCOUNT`、`DEV_LOGIN_NAME`、`DEV_LOGIN_EMAIL`、`DEV_LOGIN_DEPARTMENT`、`DEV_LOGIN_SYSID`、`DEV_LOGIN_ROLE` 建立 `auth_context`；`DEV_LOGIN_ROLE` 僅允許 `user|admin`
    - `prod`：導向 OAuth provider 時不傳送 `state` 參數
  - Response：
    - 成功回 `302`
      - `prod`：redirect 至 OAuth provider
      - `dev/test`：redirect `/main/`
    - `prod` 若 OAuth 設定缺失或不合法，回 `500 INTERNAL_ERROR`
    - `dev/test` 若 bypass 設定缺失或不合法，回 `500 INTERNAL_ERROR`
- `GET /main/auth/callback`
  - 用途：接收 provider callback，交換 access token，取得 basic identity claims，建立本機 session auth context。
  - 規則：
    - callback 僅以 `code` 驅動 token/identity 流程；不做 `state` 比對
    - OAuth claims 來源：`sysId`、`cn`、`chName`、`email`、`instCode`、`tCode`
    - 映射：`account<-cn`、`name<-chName`、`department<-instCode`、`sysid<-sysId`
    - 登入資格檢查順序：`active whitelist(sysid)` -> `active admins(id=sysid)` -> `tCode` 命中 `LOGIN_ALLOWED_TITLE_CODES`
    - `LOGIN_ALLOWED_TITLE_CODES` 以逗號分隔字串表示（例如 `A01,A02,...`），解析需 `split(',')` 後做 `trim + upper`，空值略過且重複值去重；`tCode` 比對時同樣 `trim + upper`
    - 成功時寫入 session `auth_context`（`account`、`name`、`email`、`department`、`sysid`、`role=user`）並 redirect `/`
    - 若未通過登入資格檢查，回 `302` redirect `/main/login-denied?error=LOGIN_NOT_ELIGIBLE` 且不得建立 session
    - 前端在 `/main/login-denied` 需可直接顯示公開拒絕頁，不得發生自動導回 `/main/login` 的重導循環
    - 若缺少必要欄位（任一 `sysId`、`cn`、`chName`、`email`、`instCode`、`tCode`）需拒絕登入
    - 成功與失敗皆需寫入 `auth_audit_logs`
  - Response：
    - 成功回 `302` redirect `/`
    - `401`：`OAUTH_TOKEN_EXCHANGE_FAILED`、`OAUTH_BASIC_FETCH_FAILED`
    - `422`：`OAUTH_CODE_MISSING`、`OAUTH_IDENTITY_INVALID`
- `GET /main/api/v1/users/me`
  - 用途：回傳目前 session 使用者資訊與 CSRF token。
  - 規則：
    - 回傳欄位：`account`、`name`、`email`、`department`、`sysid`、`role`、`csrf_token`
    - 若目前帳號命中 `active admins`，`role` 需回傳 `admin`
    - 可在 `dev/test` 透過 header auth bootstrap session

### 1) 申請並核發 API Key
- `POST /main/api/v1/api-keys/applications`
- 前置條件：
  - 請求必須為已登入使用者（`account`、`name`、`email`、`department`、`sysid` 由 auth context 提供，並以 auth context 為準）
  - auth context 缺少任一必要欄位（`account`、`name`、`email`、`department`、`sysid`）時，回傳 `422 VALIDATION_ERROR`，且錯誤訊息需指出缺少欄位
  - `sysid` 必須為純數字且為正整數；若不合法，回傳 `422 VALIDATION_ERROR`，且錯誤訊息需指出格式問題
  - `user` 僅能以 auth context 申請本人；`admin` 可選擇代他人申請（透過 `target_identity`）
  - 申請資格必須通過：依序命中 `active whitelist(sysid)`、`active admins(id=sysid)`，或 `tCode` 命中 `LOGIN_ALLOWED_TITLE_CODES`
  - `admin` 代申請時，後端需先依 `target_identity.account` 查人員目錄取得唯一身份，再以該身份的 `account(cn)` 查詢 `tCode` 檢查申請資格
  - 若需查詢 `tCode` 且 Persnl SOAP 服務連線逾時或 5xx，本 API 回傳 `503 SOAP_SERVICE_UNAVAILABLE`，不得建立申請資料
  - `purpose` 經 `trim()` 後不得為空字串；若為空字串或全空白，回傳 `422 VALIDATION_ERROR`
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
- Outbound（系統呼叫 provider `POST {PROVIDER_BASE_URL}/key/generate`）：
```json
{
  "rpm_limit": 500,
  "tpm_limit": 10000,
  "max_budget": 1000.0,
  "budget_duration": "30d",
  "duration": "180d",
  "key_alias": "for_jane.doe",
  "key_type": "llm_api"
}
```
  - auth header 固定為 `Authorization: Bearer {PROVIDER_MASTER_KEY}`；沿用既有 `PROVIDER_MASTER_KEY` 作為 Bearer token 值
  - `budget_duration` 由系統設定映射：`daily->1d`、`weekly->7d`、`monthly->30d`
  - `duration` 由 `duration_months` 映射：`1->30d`、`6->180d`、`12->360d`
  - 若全域設定中的 `tpm_limit` 或 `rpm_limit` 為 `0`，送往 provider 時需轉為 `null`，表示不限制
  - `key_alias` 預設先送 `for_{owner_account}`；若 provider 回 `400`，系統需自動依序重試 `for_{owner_account}_v2`、`_v3` ...，成功後將最終 alias 寫回本地 `api_keys.key_alias`
  - 目前不送 `budget_limits`
  - 僅送上述新欄位；不再送舊欄位（例如 `account`、`application_id`、`duration_months`、`purpose`、`limit_strategy`）
  - provider 成功回應需自 `response.key` 讀取新明文 secret；不得假設回傳欄位為 `api_key_plaintext`

### 1-1) 全域金鑰條件設定（Admin only）
- `GET /main/api/v1/limit-strategy-config`
- `PATCH /main/api/v1/limit-strategy-config`
- 全域固定單一金鑰條件組合（皆可編輯）：
  - `budget`（額度）：`max_budget`、`budget_duration`
  - `rate_limit`（速度）：`tpm_limit`、`rpm_limit`
- 欄位語意同金鑰條件模板：
  - `max_budget`：總金額額度（USD）。
  - `budget_duration`：重置週期（`daily|weekly|monthly`）。
  - `tpm_limit`：每分鐘 Token 數限制；允許 `0`，表示送往 provider 時轉為 `null`（不限制）。
  - `rpm_limit`：每分鐘請求數限制；允許 `0`，表示送往 provider 時轉為 `null`（不限制）。
- 每把 API Key 需同時套用 `budget` 與 `rate_limit` 兩種限制；不提供二選一模式。
- 一般使用者不可查看或修改金鑰條件設定。
- 系統需透過 migration 預先補齊 `global-limit-strategy-config` 預設資料列（`1000/monthly/10000/500`）。
- `GET /main/api/v1/limit-strategy-config` 在資料缺漏時仍需回傳相同預設值，作為相容性保險。
- `PATCH /main/api/v1/limit-strategy-config` 需採 upsert：若設定不存在則建立，存在則更新。
- `PATCH /main/api/v1/limit-strategy-config` 在 session auth 模式下，若 `X-CSRF-Token` 缺失或不正確需回 `403 FORBIDDEN`。

### 2) 查詢 API Key 清單
- `GET /main/api/v1/api-keys`
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
      "key_alias": "for_jane.doe_v2",
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
- `GET /main/api/v1/api-keys/statistics/users`
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
- `GET /main/api/v1/api-keys/{id}`
- 規則：`user` 僅可查本人資料；`admin` 可查任意資料；不可回傳明文 key。
- 到期口徑：`expires_at` 早於查詢當下（UTC）且原始狀態為 `active` 時，API 對外狀態需視為 `expired`。
- 回傳 `key_alias`；若資料未設定則回傳系統產生 alias（初始為 `for_{owner_account}`，若 provider 衝突則可能為 `for_{owner_account}_vN`）。
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
- `POST /main/api/v1/api-keys/{id}/revoke`
- 規則：
  - `user` 僅可停用本人 `active` key；`admin` 可停用任意 `active` key。
  - revoke 對應 provider `block`；前端不得提供舊明文 key，後端需從 `key_ciphertext` 解密後直接呼叫 provider。
  - 呼叫 provider `block` 時，request body 需以 `key` 欄位傳送舊明文 key。
  - provider `block` 成功後，才可將本地 `api_keys.status` 與對應 `api_key_applications.status` 同步為 `revoked`。
  - provider timeout / 5xx / 明確拒絕、缺少密文、或解密失敗時，本地不得先標記為 `revoked`。

### 4-2) 續發（Renew）API Key
- `POST /main/api/v1/api-keys/{id}/renew`
- 規則：
  - `user` 僅可續發本人 `revoked` key；`admin` 可續發任意 `revoked` key。
  - renew 對應 provider `regenerate`；前端不得提供舊明文 key，後端需從 `key_ciphertext` 解密後直接呼叫 provider。
  - 呼叫 provider `regenerate` 時，request body 需以 `key` 欄位傳送舊明文 key，其餘限制欄位沿用 `generate` wire format。
  - renew 送往 provider 的 `key_alias` 需優先沿用目前 key alias；若 provider 回 `400`，系統需自動補 `_vN` 後重試，成功後將最終 alias 寫入新 key。
  - renew 會在 provider 成功後建立新 key（`status=active`），不是把舊 key 改回 `active`。
  - 新 key 的 `duration_months` 與 `purpose` 需沿用來源 key 的原資料。
  - provider 成功但本地同步失敗時，需保留可追蹤資訊並支援 retry / reconciliation，避免 provider 與本地資料不一致。
- renew 成功時，回傳一次性 `api_key_plaintext`。
  - renew 的新明文需自 provider response `key` 讀取。
  - renew 成功後需寄送 Email 通知申請者「已更新金鑰」；通知信不得包含明文 key。
  - 續發成功後，來源 key 對 `user` 列表需隱藏；`admin` 列表仍需可見完整歷史。

### 4-3) 展延（Extend）API Key
- `POST /main/api/v1/api-keys/{id}/extend`
- Request：
```json
{
  "duration_months": 1
}
```
- 規則：
  - `user` 僅可展延本人 `active|expired` key；`admin` 可展延任意 `active|expired` key。
  - `user` 展延 `active` key 時，若尚未寄送本輪任一到期提醒（`expiration_notice_sent_at` 為空）不得展延，回傳 `409 KEY_EXTENSION_NOTICE_REQUIRED`；`expired` key 不受此限制。
  - `duration_months` 僅允許 `1|6|12`。
  - 展延判定口徑需與查詢一致：`expires_at` 已過且原始狀態為 `active` 時，需視為 `expired` 可展延。
  - extend 對應 provider `update`；前端不得提供舊明文 key，後端需從 `key_ciphertext` 解密後直接呼叫 provider。
  - 呼叫 provider `update` 時，request body 需以 `key` 欄位傳送舊明文 key，其餘限制欄位沿用 `generate` wire format。
  - extend 送往 provider 的 `key_alias` 需優先沿用目前 key alias；若 provider 回 `400`，系統需自動補 `_vN` 後重試，成功後將最終 alias 寫回原 key。
  - extend 會在 provider 成功後沿用原 key，更新同一筆 key 的有效期限與狀態（必要時轉為 `active`）。
  - extend 成功後，後續到期提醒需以新的 `expires_at` 重新啟動完整 `30|14|7|3|1` 通知週期。
  - provider timeout / 5xx / 明確拒絕、缺少密文、或解密失敗時，本地不得先更新有效期限或狀態。
  - extend 不會回傳 `api_key_plaintext`。

### 4-0) 更新 API Key Alias
- `PATCH /main/api/v1/api-keys/{id}`
- Request：
```json
{
  "key_alias": "service_internal_batch"
}
```
- 規則：僅 `admin` 可使用；`key_alias` 不可為空字串；若與其他 key alias 重複需回傳 `409 KEY_ALIAS_DUPLICATE`；成功後回傳更新後單筆資料。

### 4-1) 受控回取 API Key 明文（Reveal）
- `POST /main/api/v1/api-keys/{id}/reveal`
- 規則：僅 `admin` 可使用；此端點為受控 break-glass 流程，不屬一般列表/詳情查詢。
- 規則：不得作為一般 `renew`、`extend`、`revoke` 流程依賴。
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
- `POST /main/api/v1/whitelists`：新增特殊人員名單（需帶 `sysid`、`account`、`name`、`email`）
- `GET /main/api/v1/whitelists`：查詢特殊人員名單列表
- `PATCH /main/api/v1/whitelists/{id}`：更新狀態（`active/inactive`）與備註
- `DELETE /main/api/v1/whitelists/{id}`：刪除特殊人員名單條目（實體刪除）
- 規則：僅 `admin` 可使用。
- `POST /main/api/v1/whitelists`、`PATCH /main/api/v1/whitelists/{id}`、`DELETE /main/api/v1/whitelists/{id}` 在 session auth 模式下，若 `X-CSRF-Token` 缺失或不正確需回 `403 FORBIDDEN`。
- `POST /main/api/v1/whitelists` 若 `sysid` 重複需回 `409 WHITELIST_SYSID_DUPLICATED`。
- 回傳欄位至少包含：`id`、`sysid`、`account`、`name`、`email`、`status`、`note`、`created_at`、`updated_at`。

### 5-1) 特殊人員名單新增前使用者查詢 API
- `GET /main/api/v1/users?q={keyword}`
- 用途：供管理者透過 Persnl SOAP 查詢候選人資料（供新增管理者/特殊人員前使用）。
- 規則：
  - 僅 `admin` 可使用。
  - `q` 為必填，且僅用於 `account`、`name` 查詢。
  - `q` 未提供、空字串或空白字串時，回傳 `422 VALIDATION_ERROR`。
  - 不論 `q` 值內容為何，資料來源皆為 Persnl SOAP（`PERSNL_SOAP_URL`）。
  - 回傳欄位至少包含 `id`、`sysid`、`account`、`name`、`email`、`department`（對應單位代碼 `instCode`）、`status`。
- 單位主檔同步：`Persnl.getInstitutes` 僅供背景同步作業使用（首次入庫 + 後續排程差異同步），不得放在此 API 請求路徑中每次即時呼叫。
- 錯誤回應：
  - `403 FORBIDDEN`：非 `admin`
  - `422 VALIDATION_ERROR`：`q` 不合法
  - `503 SOAP_SERVICE_UNAVAILABLE`：Persnl SOAP timeout/5xx

### 5-4) 管理者名單查詢 API
- `GET /main/api/v1/admins`
- 用途：供管理者查看管理者名單（來源 `admins`）。
- 規則：
  - 僅 `admin` 可使用。
  - 資料來源為本地 DB `admins`（含 `active`、`inactive`）。
  - 不得在此 API 路徑呼叫 Persnl SOAP。
- 回傳欄位至少包含 `id`、`sysid`、`account`、`name`、`email`、`department`、`status`。

### 5-2) 目前使用者語言偏好 API
- `GET /main/api/v1/users/preferences/locale`
  - 回傳格式：`{ "preferred_locale": "zh-TW" | "en" | null }`
- `PATCH /main/api/v1/users/preferences/locale`
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
- `GET /main/api/v1/institutes`
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

### 5-3-1) 單位主檔手動同步 API
- `POST /main/api/v1/institutes/sync`
- 用途：供管理者在「單位代碼資料檢視」頁手動觸發單位主檔同步（後端呼叫 `Persnl.getInstitutes` 並同步本地 DB）。
- 規則：
  - 僅 `admin` 可使用。
  - 需通過 CSRF 驗證與 admin mutation rate limit。
  - 成功時需回傳同步統計：`fetched_count`、`inserted_count`、`updated_count`、`unchanged_count`、`deactivated_count`。
  - Persnl SOAP timeout/5xx 時回傳 `503 SOAP_SERVICE_UNAVAILABLE`。

### 6) 管理者啟用/停用 API
- `PUT /main/api/v1/admins/{id}`：新增指定使用者管理者身分（建立後狀態為 `active`）
- `POST /main/api/v1/admins/{id}/enable`：啟用指定使用者管理者身分
- `POST /main/api/v1/admins/{id}/disable`：停用指定使用者管理者身分
- `DELETE /main/api/v1/admins/{id}`：刪除指定停用中的管理者身分
- 規則：僅 `admin` 可使用，且需記錄操作稽核資訊（操作者、時間）。
- 規則補充：
  - `PUT /main/api/v1/admins/{id}` 若 `admins.id` 已存在，回傳 `409 ADMIN_ALREADY_EXISTS`。
  - `DELETE /main/api/v1/admins/{id}` 僅允許刪除 `inactive`；若目標為 `active`，回傳 `422 VALIDATION_ERROR`。

### 6-1) 關鍵操作稽核 log（v1）
- 儲存方式：寫入 `operation_audit_logs`（DB 落地）。
- 範圍（v1）：
  - `POST /main/api/v1/api-keys/applications`
  - `POST /main/api/v1/api-keys/{id}/revoke`
  - `POST /main/api/v1/whitelists`
  - `PATCH /main/api/v1/whitelists/{id}`
  - `DELETE /main/api/v1/whitelists/{id}`
  - `POST /main/api/v1/admins/{id}/enable`
  - `POST /main/api/v1/admins/{id}/disable`
  - `PUT /main/api/v1/admins/{id}`
  - `DELETE /main/api/v1/admins/{id}`
  - `PATCH /main/api/v1/limit-strategy-config`
  - `POST /main/api/v1/institutes/sync`
- 稽核欄位至少需可辨識：事件類型、動作、成功/失敗、操作者（`sysid/account/role`）、目標資源類型與 ID、`request_id`、時間、來源 IP、user-agent。
- 成功與失敗都需記錄（含權限不足、驗證失敗、資源不存在等）。
- metadata 採白名單策略，僅記錄必要且非敏感欄位；若 provider 提供 request id / operation id，可納入白名單欄位。
- 若 audit 寫入失敗，不得改變原本 API 成功/失敗語意（主流程優先）。

### 6-2) 操作稽核熱資料查詢（v1）
- `GET /main/api/v1/operation-audit-logs`
- 規則：僅 `admin` 可使用。
- 查詢參數：`page`、`page_size`、`from`、`to`、`event_type`、`result(success|failure)`。
- 預設熱資料窗：若未提供 `from/to`，回傳最近 7 天資料。
- 排序：`created_at desc`（最新優先）。
- 回傳欄位（精簡）：`created_at`、`event_type`、`action`、`result`、`actor_account`、`target_type`、`target_id`、`error_code`。

### 6-3) 登入稽核熱資料查詢（v1）
- `GET /main/api/v1/auth-audit-logs`
- 規則：僅 `admin` 可使用。
- 查詢參數：`page`、`page_size`、`from`、`to`、`provider`、`result(success|failure)`。
- 預設熱資料窗：若未提供 `from/to`，回傳最近 7 天資料。
- 排序：`created_at desc`（最新優先）。
- 回傳欄位（精簡）：`created_at`、`provider`、`result`、`account`、`sysid`、`role`、`error_code`、`request_id`。
- `created_at` 格式需為 UTC `date-time`（RFC 3339，例如 `2026-05-21T08:28:20Z`）。
- 回傳不得包含敏感憑證資訊（access token、refresh token、password、client secret）。

### 6-4) 時間欄位輸出規則
- 所有對外 API response 的 datetime 欄位（如 `created_at`、`updated_at`、`issued_at`、`expires_at`、`expiration_notice_sent_at`）都需輸出為 UTC `date-time`（RFC 3339，例如 `2026-05-21T08:28:20Z`）。
- 若內部資料來源為無時區 datetime，序列化時仍需以 UTC 語意輸出，不得回傳省略時區的 datetime 字串。

### 7) 研究資格與目錄查詢服務（Persnl SOAP）
- 用途：供「進入系統」與「送出申請」時檢查是否命中研究人員資格。
- 資格判斷：以 Persnl SOAP 回傳之 `tCode` 判斷研究資格。
- 放行規則：登入流程與申請資格流程一致，皆先看 `active whitelist(sysid)` 與 `active admins(id=sysid)`，兩者都未命中才看 `LOGIN_ALLOWED_TITLE_CODES`。
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
- `KEY_EXTENSION_NOTICE_REQUIRED`
- 前端對 `VALIDATION_ERROR` 不得僅顯示通用錯誤；需優先顯示後端回傳的具體 `message`，讓使用者可判斷缺少或格式錯誤的欄位

## 驗收標準
### 申請與資格
1. 研究人員名單職稱代碼命中者，或研究名單未命中但特殊人員名單 `active` 命中者，可成功核發 API Key；兩者皆未命中時不得允許進入系統，且申請 API 回傳 `403 APPLICANT_NOT_ELIGIBLE`。
2. 當資格判斷需查詢 `tCode` 且 Persnl SOAP 服務 timeout/5xx 時，登入流程可放行，但申請 API 必須回傳 `503 SOAP_SERVICE_UNAVAILABLE`。
3. 使用者透過 SSO/OAuth 登入後，申請頁需自動帶入 `account`、`name`、`email`、`department`、`sysid`；若 auth context 缺少必要欄位、`sysid` 非數字或非正整數，申請 API 需回傳 `422 VALIDATION_ERROR`，且不得建立申請或 key 紀錄。
4. `duration_months` 僅允許 `1|6|12`，`application_date` 需為合法日期且不得晚於申請當日；非法值需回傳對應驗證錯誤。
5. `admin` 可透過 `target_identity.account` 代他人送出申請；若目錄服務查無帳號、結果不唯一或 Persnl SOAP timeout/5xx，API 需回傳對應 `422 VALIDATION_ERROR` 或 `503 SOAP_SERVICE_UNAVAILABLE`。
6. 一般申請建立的 application row 需保留申請人快照欄位，`is_proxy_submission=false`、`proxy_operator_account=NULL`；代申請需保留目標申請人快照，`is_proxy_submission=true`，且 `proxy_operator_account` 為實際代送的 admin account。

### Key 核發、保存與受控回取
7. 核發成功的 API Key 格式需為 `AS-` + 30 碼隨機字元（總長 33）；明文 key 預設僅於建立成功當下回傳一次，一般查詢端點不得再次回傳明文。
8. 資料庫不得儲存 API Key 明文；需保存 `key_hash`，並可保存 `key_ciphertext` / `key_kek_version` 供受控 reveal 與 lifecycle 操作使用。
9. `POST /main/api/v1/api-keys/{id}/reveal` 僅 `admin` 可使用，回應需包含 `Cache-Control: no-store`；此端點僅供 break-glass，不得成為一般 `renew`、`extend`、`revoke` 流程的依賴。
10. 申請成功彈窗需提供明文 key 複製功能，點擊後 icon 需切換為成功狀態並可自動恢復。

### Provider 與 Lifecycle
11. API key lifecycle 採 external provider 為主權威；`applications`、`renew`、`extend`、`revoke` 均需先完成 provider 操作，再同步本地資料。
12. `renew`、`extend`、`revoke` 若需舊明文 key，後端必須從 `key_ciphertext` 解密，且明文只可在服務記憶體中短暫使用；不得出現在 DB、log、audit log、exception message。
13. 若 provider timeout/5xx、明確拒絕、缺少密文材料、解密失敗或回應不完整，本地不得先改動狀態或有效期限，並需回傳對應錯誤。
14. 若部署使用 local provider adapter 作為開發/測試替身，仍需經由同一 provider abstraction 執行，不得繞過 provider-first 時序直接改本地資料。
15. 外部 provider `POST /key/generate` payload 僅允許 `rpm_limit`、`tpm_limit`、`max_budget`、`budget_duration`、`duration`、`key_alias`、`key_type`；`key_type` 固定 `"llm_api"`，`duration_months(1|6|12)` 需映射為 `30d|180d|360d`，本地設定值為 `0` 的 `rpm_limit` / `tpm_limit` 需送 `null`，且不得送 `models` 或 `budget_limits`。
16. 外部 provider 驗證 header 需使用 `Authorization: Bearer {PROVIDER_MASTER_KEY}`；`update`、`regenerate`、`block` 若需舊明文 key，request body 一律以 `key` 欄位傳送；`generate` / `regenerate` 成功時一律自 response `key` 讀取新明文 secret。
17. 外部 provider 回傳 `422` 且 body 為 `detail[]` 時，系統需映射為本地 `422 VALIDATION_ERROR`；timeout、5xx、連線錯誤與無法解析必要回應時仍需回 `503 PROVIDER_UNAVAILABLE`。

### Key 查詢、狀態與 Lifecycle 權限
18. `user` 登入後只能看到自己的全部歷史紀錄；若舊 key 已被 renew，來源舊 key 對 `user` 不可見；`admin` 可看到全域完整資料，且每筆至少需能辨識 `owner_account`、`owner_name`。
19. 一般查詢僅能看到 `masked_key`（格式 `AS-...XXXX`），不得看到明文；清單頁不得顯示建立時間，建立時間僅顯示於單筆詳情視窗。
20. 單筆詳情需顯示 `purpose`、`department`；若無資料需顯示 `-`。
21. `GET /main/api/v1/api-keys` 與 `GET /main/api/v1/api-keys/{id}` 的到期口徑需以 `expires_at` 即時計算；原始狀態為 `active` 且已過期者，對外需顯示為 `expired`。
22. 即使 expired 回填排程停用或失敗，清單、詳情與統計 API 仍需依 effective status 正確呈現 `expired`；回填排程成功後，符合條件的 `api_keys.status` 與 `api_key_applications.status` 需落地更新為 `expired`，且不得誤改 `revoked`。
23. 一般使用者可停用本人 `active` key；停用非本人 key 時需回傳 `KEY_NOT_OWNED_BY_USER` / `403`，停用非 `active` key 時需回傳 `KEY_NOT_ACTIVE`。
24. 一般使用者僅可續發本人 `revoked` key；續發 `active|expired` key 時需回傳 `KEY_NOT_RENEWABLE`，且同一把舊 key 不得重複續發，重複續發需回傳 `KEY_ALREADY_RENEWED`。
25. 一般使用者可展延本人 `active|expired` key；展延 `revoked` key 時需回傳 `KEY_NOT_EXTENDABLE`。`user` 展延 `active` key 前需已寄送本輪任一到期提醒（`expiration_notice_sent_at` 非空），未達條件時需回傳 `KEY_EXTENSION_NOTICE_REQUIRED`；`expired` key 不受此限制。
26. `renew`、`extend`、`revoke` 的本地同步不得改變既有受保護 API 路徑、角色模型或現有對外 response shape。

### 到期提醒與通知信
27. 系統需提供背景排程寄送 API Key 到期提醒信；單一排程入口需在同次執行中處理 `30|14|7|3|1` 天全部提醒時段。
28. 提醒判定條件需以 UTC 日期窗口為準：當 `api_keys.status='active'` 且 `expires_at` 落在 `now(UTC)+N days` 的當日區間時，觸發對應 `N` 天提醒；`N` 僅允許 `30|14|7|3|1`。
29. 同一把 key 在同一輪 `expires_at`、同一提醒時段最多成功寄送一次，但不同提醒時段可在不同日期成功寄送；若 `extend` 後 `expires_at` 改變，新的到期日需重新啟動完整提醒週期。
30. 某提醒時段寄送失敗時，不得影響其他 key 或其他提醒時段；只要該時段尚未成功，後續重跑需可再次嘗試。
31. 本輪首次成功寄出任一提醒後，`api_keys.expiration_notice_sent_at` 需填值；寄送失敗不得填值；後續提醒時段不得覆蓋其既有語意。
32. `POST /main/api/v1/api-keys/applications` 成功後需以非阻塞方式寄送申請成功通知信給申請者本人；寄信失敗時 API 仍需回 `201`，且不得回滾申請資料或延遲一次性明文 key 回應。
33. `POST /main/api/v1/api-keys/{id}/renew` 成功後需寄送 renew 成功通知信給申請者本人，且通知信不得包含明文 key。
34. `applications`、`renew`、`extend`、`revoke` 若遇 provider timeout/5xx（`PROVIDER_UNAVAILABLE`），需寄送通知信給所有 `active` 管理者；若管理者通知信寄送失敗，不得改變原 API 錯誤回應。
35. 所有業務通知信內容需中英並列（中文在前、英文在後）；到期提醒信僅寄送申請者本人，需包含正確剩餘天數、到期時間與可展延提示，且信內顯示的到期時間需轉為 `Asia/Taipei`，但提醒判定與資料儲存仍維持 UTC。
36. 通知信模板屬正式契約；主旨、收件者、動態欄位與中英段落順序變更時，需同步更新 `docs/mail.md`。詳細主旨與完整模板內容以 `docs/mail.md` 為準。

### 管理功能與後台查詢
37. 非 `admin` 呼叫特殊人員名單、管理者名單、限制策略、統計、稽核與單位同步相關管理 API 時，均需回傳 `403`。
38. 特殊人員名單比對主鍵為 `sysid`；新增重複 `sysid` 時需回傳 `409 WHITELIST_SYSID_DUPLICATED`，且管理者可刪除條目，刪除後不得再出現在列表。
39. 特殊人員名單新增前使用者查詢（`GET /main/api/v1/users`）僅可使用 `account`、`name` 查詢；不得以 `sysid` 或 `email` 作為查詢條件。管理者名單查詢（`GET /main/api/v1/admins`）需直接讀取 `admins`，不得依賴 Persnl SOAP。
40. 管理者可新增、啟用、停用與刪除管理者；新增後狀態為 `active`，停用後仍保留於名單且狀態改為 `inactive`。`PUT /main/api/v1/admins/{id}` 若已存在需回 `409 ADMIN_ALREADY_EXISTS`；`DELETE` 僅允許刪除 `inactive` 管理者。
41. 前端需阻擋管理者停用自己的管理者權限；管理者新增查詢結果中，對已存在於 `admins` 的人員（包含 `active`、`inactive`）不得顯示新增按鈕。
42. `GET /main/api/v1/api-keys/statistics/users` 僅 `admin` 可用，預設依 `total_applications desc` 排序；`sort_by` 僅允許既定欄位，`scope`、`from`、`to` 與 `application_date` 篩選需生效，且統計結果不得包含 `api_key_plaintext`。
43. 統計 API 每筆資料需包含 `owner_department`；管理者統計表格中的 `total_applications` 與 `active_count` 需可點擊開啟 API Key 明細 Dialog，且明細查詢口徑需跟隨當前 `from`、`to` 篩選；點擊 `active_count` 時僅顯示 `status=active`。
44. `GET /main/api/v1/api-keys` 與 `GET /main/api/v1/api-keys/{id}` 回傳需包含 `key_alias`；未設定時回傳系統產生 alias。`admin` 可透過 `PATCH /main/api/v1/api-keys/{id}` 更新 alias，`user` 呼叫需回傳 `403`，重複 alias 需回傳 `409 KEY_ALIAS_DUPLICATE`。
45. 限制策略設定僅 `admin` 可讀取與更新；`budget_duration` 僅允許 `daily|weekly|monthly`，管理端顯示映射需為 `1天|7天|30天`，且每把 API Key 的限制策略需同時包含 `budget` 與 `rate_limit`，不得提供 pending 補發端點或 `issuance_mode` 二選一模式。
46. `admin` 可於 `/institute-view` 查看 `active` institutes 清單與 `total`，並可手動觸發同步；若 Persnl SOAP 不可用，`POST /main/api/v1/institutes/sync` 需回傳 `503 SOAP_SERVICE_UNAVAILABLE`。

### OAuth、Session 與語系
47. `GET /main/login` 在 `prod` 需導向 OAuth provider；在 `dev/test` 需可直接建立 session auth context 並 redirect `/main/`。`GET /main/auth/callback` 成功時需建立 session 並 redirect `/main/`，失敗時需回錯且寫入 failure audit。
48. 正式環境不得接受 header auth 作為正式認證來源；僅 `dev/test` 可啟用。OAuth 成功登入寫入的角色需固定為 `user`，且流程不得落地 access token、refresh token、password 或 client secret。
49. OAuth callback 需以 claims `sysId/cn/chName/email/instCode/tCode` 建立身份；任一缺漏需拒絕登入。登入資格判斷需遵循 `active whitelist(sysid)` 或 `active admins(id=sysid)`，否則才比對 `LOGIN_ALLOWED_TITLE_CODES`。
50. `/main/login-denied` 必須是公開頁；登入失敗導向 `/main/login-denied?error=LOGIN_NOT_ELIGIBLE` 時，使用者需可直接看到拒絕說明與返回登入操作，且不依賴 `GET /main/api/v1/users/me` 成功。
51. `GET /main/api/v1/users/me` 需回傳目前使用者資料與 `csrf_token`；所有 `POST/PATCH` 端點在 session auth 模式下，缺少或錯誤 `X-CSRF-Token` 時需回傳 `403 FORBIDDEN`。
52. 系統語言僅支援 `zh-TW`、`en`；DB 無偏好時，系統語言命中 `zh*` 顯示中文、命中 `en*` 顯示英文，其他語系 fallback 為英文，並需立即寫回 DB 作為初始偏好。
53. `GET /main/api/v1/users/preferences/locale` 需回傳目前偏好（`zh-TW|en|null`）；`PATCH` 僅允許 `zh-TW|en`，成功後可立即由 `GET` 讀回。手動切換語言後，重新登入需沿用 DB 偏好，且導覽列、頁標題、按鈕、錯誤/提示訊息與 DataGrid locale 文案需隨語言切換更新。

### 稽核、查詢限制與安全邊界
54. `POST /main/api/v1/api-keys/applications`、`revoke`、`renew`、`extend`、`whitelists`、`admins`、`limit-strategy-config`、`institutes/sync` 等關鍵異動 API 成功與失敗都需寫入 `operation_audit_logs`，且需可辨識 `error_code`。
55. `operation_audit_logs` 不得包含 API key 明文或其他敏感憑證；`metadata_json` 僅允許白名單欄位。若 audit 寫入失敗，不得改變主流程成功或失敗語意。
56. `GET /main/api/v1/operation-audit-logs` 與 `GET /main/api/v1/auth-audit-logs` 僅 `admin` 可使用；未提供 `from/to` 時預設回傳最近 7 天熱資料，結果依 `created_at desc` 排序，並支援分頁與既定篩選條件。
57. `GET /main/api/v1/api-keys/statistics/users`、`GET /main/api/v1/operation-audit-logs`、`GET /main/api/v1/auth-audit-logs` 的 `from/to` 查詢區間不得超過 `31` 天；`GET /main/api/v1/users?q=...` 的 `q` 長度不得超過 `100` 字元。
58. 關鍵操作稽核功能、申請人識別欄位調整、統計與 lifecycle 擴充，均不得改動既有受保護 API 路徑、角色模型（`user|admin`）與既有對外 response shape。

## Roadmap
### Phase 1：Foundation
- 建立後端專案骨架與資料表 migration
- 實作 `api_key_whitelist`、`api_key_applications`、`api_keys` 基礎模型
- 建立基本錯誤處理與日誌

### Phase 2：MVP API
- 完成特殊人員名單管理 API（沿用 `/main/api/v1/whitelists*` 路徑；新增、查詢、停用/啟用）
- 完成特殊人員名單管理 API（沿用 `/main/api/v1/whitelists*` 路徑；新增、查詢、停用/啟用、刪除）
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

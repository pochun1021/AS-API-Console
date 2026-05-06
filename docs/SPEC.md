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

重點是先提供最小可用流程，並保留後續 SSO/OAuth、審核流程與安全等級擴充能力。

## 資料儲存策略
- MVP 階段採用 MariaDB 作為主要資料庫。
- ORM 與 migration 層維持 SQLAlchemy + Alembic，確保後續可平滑擴充至 PostgreSQL。
- DB schema/migration 操作與驗證流程請見 `docs/runbook-db.md`。

## 使用者流程
1. 使用者透過 SSO/OAuth 登入時，系統先檢查進入資格：優先查外部研究人員名單（以職稱代碼判斷），未命中再檢查本系統特殊人員名單（原白名單，僅 `active` 可通過）。
2. 通過進入資格後進入申請頁，系統自動帶入 `account`、`name`、`email`、`department`、`sysid`。
3. 使用者填寫姓名、Email、單位、申請日期、用途與 API 生效時長。
4. 送出申請前再次檢查資格：優先查外部研究人員名單（職稱代碼），未命中再檢查特殊人員名單（`active`）。
5. 資格檢查通過後系統立即核發 API Key。
6. 系統只顯示一次明文 API Key，使用者需立即保存。
7. 一般使用者可在「我的 API Key 紀錄」查看本人全部歷史紀錄（`active|revoked|expired`），Key 僅顯示遮罩。
8. 一般使用者可自行停用本人已生效（`active`）的 Key。
9. 使用者可於列表/詳情查看狀態、到期時間與 key 前綴。

## 頁面規格
### 1) Apply Page（申請頁）
- 欄位：
  - `account`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `name`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `email`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `department`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `sysid`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `application_date`（必填，使用者可選）
  - `duration_months`（必填，選單：`1|6|12`）
  - `purpose`（必填）
- 驗證：
  - `email` 格式檢查
  - 申請資格需通過：研究人員名單職稱代碼命中，或特殊人員名單為 `active`
  - `application_date` 格式為 `YYYY-MM-DD` 且不得晚於申請當日
  - `duration_months` 僅允許 `1|6|12`
- 成功送出後顯示一次性 key，並提供複製操作；複製成功需有明確視覺回饋（check icon 後恢復）。
- 複製流程以 Clipboard API 為唯一可驗證複製路徑；若不可用或複製失敗，需提示使用者手動複製。
- 透過複製 icon 觸發時不得要求使用者先反白金鑰文字，系統需直接完成複製。

### 2) My API Keys Page（一般使用者我的紀錄頁）
- 顯示範圍：僅本人帳號的全部歷史紀錄（`active|revoked|expired`）。
- 顯示欄位：申請日期、生效時長、狀態、到期時間、遮罩 key（或前綴）。
- 管理者在同頁可額外查看申請人識別欄位（`owner_account`、`owner_name`）。
- 操作：僅對本人 `active` key 顯示「停用」按鈕。

### 3) API Key Detail Dialog（詳情視窗）
- 顯示完整申請資訊與狀態。
- 顯示欄位至少包含：申請日期、生效時長、用途（`purpose`）、單位（`department`）、建立時間、到期時間、遮罩 key。
- 一般使用者僅可查本人資料。
- 一般使用者可停用本人 `active` key。
- 不可再次顯示 key 明文。

### 4) Whitelist Admin Page（特殊人員名單管理頁）
- 可用 `sysid`、`account`、`name`、`email` 查詢使用者後加入特殊人員名單。
- 可查詢特殊人員名單與狀態。
- 可停用/啟用特殊人員名單條目。

### 5) Admin List Page（管理者名單頁）
- 僅 `admin` 可使用。
- 可用 `sysid`、`account`、`name`、`email` 查詢使用者。
- 可授權一般使用者為管理者（`grant-admin`）。
- 可取消其他管理者權限（`revoke-admin`）。
- 前端需阻擋管理者對自己執行 `revoke-admin`（避免誤鎖管理權限）。

### 6) Admin Dashboard Page（管理者統計頁）
- 僅 `admin` 可使用。
- 以 Data Table 呈現每位申請人的統計資料，欄位至少包含：`account`、`name`、`email`、`total_applications`、`active_count`、`revoked_count`、`expired_count`、`last_applied_at`。
- 支援口徑切換 `scope`：`all|active|revoked|expired`（預設 `all`）。
- 支援日期區間篩選：`from`、`to`（`YYYY-MM-DD`），統計基準為 `application_date`。
- 支援 `q`（`account`、`name`、`email`）查詢、分頁與排序。
- 預設排序為 `total_applications desc`。

### 7) 狀態頁/元件
- Loading
- Empty
- Error（含重試）
- 列表資料以 Data Table 呈現（支援排序與分頁）；僅「操作」欄位不可排序與不可 filter。

## 功能需求
### Must Have（MVP）
- 權限模型僅區分 `user` 與 `admin`
- 僅符合資格的人員可進入系統與申請 API Key（研究人員名單職稱代碼命中，或特殊人員名單 `active` 命中）
- 特殊人員名單管理能力（新增、查詢、停用/啟用）
- 研究人員名單由外部服務提供並以職稱代碼判斷
- 外部研究人員服務失敗（timeout/5xx）時：允許進入系統，但阻擋申請
- 申請後自動核發 API Key
- API 生效時長固定月數選單（`1|6|12`）
- API Key 格式固定為 `AS-` + 30 碼隨機字元（總長 33）
- API Key 明文只顯示一次
- 系統僅儲存 `key_hash`，不儲存明文
- 一般使用者可查看本人全部申請紀錄
- 一般使用者查詢時 API Key 必須遮罩顯示
- 一般使用者可自行停用本人已生效 key（軟停用）
- 支援撤銷與狀態管理（`active|revoked|expired`）
- 管理者可查看全部 API Key 與申請紀錄
- 管理者可查看每位申請人的 API Key 申請統計（含狀態分佈）
- 管理者可授權/取消其他使用者的管理者身分

### Nice to Have（後續）
- OAuth/SSO 串接優化（完善 `sysid` 對接與身分映射）
- 多安全等級與長度策略（隨機段長度 24-30 碼可配置）
- 申請審核流程
- 使用量監控與配額管理

## 資料模型草案
### Entity: `users`
- `id` (string/uuid)
- `account` (string, required, unique)
- `email` (string, required, unique, lowercase)
- `name` (string, required)
- `role` (enum: `user` | `admin`, default: `user`)
- `status` (enum: `active` | `inactive`)
- `created_at` (datetime)
- `updated_at` (datetime)

### Entity: `api_key_whitelist`
- `id` (string/uuid)
- `email` (string, required, unique, lowercase)
- `status` (enum: `active` | `inactive`)
- `note` (string, nullable)
- `created_by` (string)
- `updated_by` (string)
- `created_at` (datetime)
- `updated_at` (datetime)

### Entity: `api_key_applications`
- `id` (string/uuid)
- `account` (string, required)
- `user_id` (fk -> users.id, required)
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
- `sysid` (string, required, SSO/OAuth 主體唯一識別碼)
- `created_at` (datetime)
- `updated_at` (datetime)

### Entity: `api_keys`
- `id` (string/uuid)
- `application_id` (fk -> api_key_applications.id)
- `key_hash` (string, required)
- `key_prefix` (string, required, MVP 固定 `AS-`)
- `masked_key` (string, computed/response only)
- `length` (int, MVP 固定 30，表示隨機段長度，不含 `AS-` 前綴)
- `security_level` (enum, MVP 固定 `high`)
- `status` (enum: `active` | `revoked` | `expired`)
- `created_at` (datetime)

## 權限規則（MVP）
- `user`：可使用 `GET /api/v1/api-keys`、`GET /api/v1/api-keys/{id}`、`POST /api/v1/api-keys/{id}/revoke`，但僅可查詢/停用本人 `active` key。
- `admin`：可查詢全部 API Key 與申請紀錄，可管理特殊人員名單（沿用受保護路徑 `/api/v1/whitelists*`），可授權/取消其他使用者管理者身分（`/api/v1/admins/{id}/grant-admin|revoke-admin`）。
- 金鑰啟用狀態以 `api_keys.status` 為唯一判斷來源：`active`=啟用，`revoked|expired`=不可用。

## API 草案
Base path：`/api/v1`

### 1) 申請並核發 API Key
- `POST /api/v1/api-keys/applications`
- 前置條件：
  - 請求必須為已登入使用者（`account`、`name`、`email`、`department`、`sysid` 由 auth context 提供，並以 auth context 為準）
  - 申請資格必須通過：研究人員名單職稱代碼命中，或特殊人員名單 `active` 命中
  - 若研究人員名單服務失敗（timeout/5xx），本 API 回傳拒絕，不得建立申請資料
- Request：
```json
{
  "application_date": "2026-05-04",
  "duration_months": 6,
  "purpose": "integration for internal service",
  "sysid": "user_123"
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
  "api_key_plaintext": "AS-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "api_key_prefix": "AS-"
}
```

### 2) 查詢 API Key 清單
- `GET /api/v1/api-keys`
- 規則：`user` 僅回傳 auth 使用者本人的資料；`admin` 可查全部資料。
- Query（草案）：`page`, `page_size`, `status`, `q`
- Response（200）：
```json
{
  "items": [
    {
      "id": "...",
      "status": "active",
      "masked_key": "AS-****wxyz",
      "key_prefix": "AS-",
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
- 回傳可包含申請人識別欄位 `owner_account`、`owner_name`（供管理者辨識申請來源）。
- 回傳應包含 `purpose` 供詳情頁顯示；若歷史資料未留存用途，前端顯示 `-`。
- 回傳應包含 `department` 供詳情頁顯示；若歷史資料未留存單位，前端顯示 `-`。

### 4) 停用 API Key
- `POST /api/v1/api-keys/{id}/revoke`
- 規則：`user` 僅可停用本人 `active` key；`admin` 可停用任意 `active` key；停用為軟停用（`status=revoked`）。

### 5) 特殊人員名單管理 API（沿用受保護路徑）
- `POST /api/v1/whitelists`：新增特殊人員名單 email
- `GET /api/v1/whitelists`：查詢特殊人員名單列表
- `PATCH /api/v1/whitelists/{id}`：更新狀態（`active/inactive`）與備註
- 規則：僅 `admin` 可使用。

### 5-1) 特殊人員名單新增前使用者查詢 API
- `GET /api/v1/users?q={keyword}`
- 用途：供管理者以 `sysid`、`account`、`name`、`email` 查詢可加入特殊人員名單的人員。
- 規則：僅 `admin` 可使用；回傳欄位至少包含 `id`、`sysid`、`account`、`name`、`email`。

### 7) 外部研究人員名單服務（整合介面）
- 用途：供「進入系統」與「送出申請」時檢查是否命中研究人員資格。
- 資格判斷：以外部服務回傳之職稱代碼判斷是否符合研究人員資格。
- 回應結果：
  - 命中：可直接通過資格檢查（不需再檢查特殊人員名單）。
  - 未命中：需再檢查特殊人員名單是否為 `active`。
  - timeout/5xx：允許進入系統，但阻擋申請 API。

### 6) 管理者授權 API
- `POST /api/v1/admins/{id}/grant-admin`：授權指定使用者為管理者
- `POST /api/v1/admins/{id}/revoke-admin`：取消指定使用者管理者身分
- 規則：僅 `admin` 可使用，且需記錄操作稽核資訊（操作者、時間）。

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
- `APPLICANT_NOT_ELIGIBLE`
- `RESEARCH_LIST_SERVICE_UNAVAILABLE`
- `WHITELIST_EMAIL_DUPLICATED`
- `USER_NOT_FOUND`
- `KEY_NOT_OWNED_BY_USER`
- `KEY_NOT_ACTIVE`
- `RATE_LIMITED`
- `INTERNAL_ERROR`

## 驗收標準
1. 研究人員名單職稱代碼命中者可成功核發 API Key，格式為 `AS-` + 30 碼隨機字元（總長 33）。
2. 研究名單未命中但特殊人員名單 `active` 命中者可成功核發 API Key。
3. 研究名單未命中且特殊人員名單未命中者，系統不得允許進入，且申請 API 回傳 `403` 與 `APPLICANT_NOT_ELIGIBLE`。
4. 研究人員名單服務失敗（timeout/5xx）時，允許進入系統，但申請 API 回傳 `503` 與 `RESEARCH_LIST_SERVICE_UNAVAILABLE`。
5. `duration_months` 非 `1|6|12` 時，API 回傳 `INVALID_DURATION_MONTHS`。
6. `application_date` 非法或晚於申請當日，API 回傳 `INVALID_APPLICATION_DATE`。
7. 明文 key 僅於建立成功當下回傳一次；後續查詢不得回傳明文。
8. 資料庫僅存 `key_hash`，不得存 API Key 明文。
9. 一般使用者登入後只能看到自己的全部歷史紀錄。
10. 一般使用者查詢 API Key 時僅能看到 `masked_key`/`key_prefix`，不得看到明文。
11. 一般使用者可停用本人 `active` key，停用後狀態轉為 `revoked`。
12. 一般使用者停用非本人 key 時，API 回傳 `KEY_NOT_OWNED_BY_USER`。
13. 一般使用者停用非 `active` key 時，API 回傳 `KEY_NOT_ACTIVE`。
14. 未通過資格檢查或驗證失敗請求不得建立 `api_key_applications` 或 `api_keys` 紀錄。
15. `user` 呼叫 `GET /api/v1/api-keys` 時僅可看到本人資料；`admin` 可看到全域資料。
16. `user` 查詢或停用非本人 key 時，API 回傳 `403`（或既有錯誤碼）。
17. 非 `admin` 使用特殊人員名單管理 API（`/api/v1/whitelists*`）時，回傳 `403`。
18. 管理者可成功授權/取消其他使用者的管理者身分（`/api/v1/admins/{id}/grant-admin|revoke-admin`）。
19. 使用者透過 SSO/OAuth 登入後，申請頁需自動帶入 `account`、`name`、`email`、`department`、`sysid`。
20. 若 auth context 缺少 `sysid`，申請 API 回傳 `VALIDATION_ERROR` 且不得建立申請紀錄。
21. 管理者不可在前端將自己的角色由 `admin` 降為 `user`。
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

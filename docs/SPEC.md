# AS API Console - API Key 申請系統 MVP Specification

## 產品目標
本 MVP 目標是建立一套可用且安全的 API Key 申請系統，支援 API Key 的核心生命週期：
- 申請
- 白名單驗證
- 自動核發
- 查詢管理
- 使用者自助查詢與停用
- 撤銷
- 到期失效

重點是先提供最小可用流程，並保留後續 SSO/OAuth、審核流程與安全等級擴充能力。

## 資料儲存策略
- MVP 階段採用 SQLite 作為主要資料庫。
- ORM 與 migration 層維持 SQLAlchemy + Alembic，確保後續可平滑擴充至 PostgreSQL。
- DB schema/migration 操作與驗證流程請見 `docs/runbook-db.md`。

## 使用者流程
1. 使用者透過 SSO/OAuth 登入後進入申請頁，系統自動帶入 `account`、`name`、`email`、`department`、`sysid`。
2. 使用者填寫姓名、Email、單位、申請日期、用途與 API 生效時長。
3. 送出申請後，系統先以 `email` 驗證白名單（僅 `active` 可通過）。
4. 白名單通過後系統立即核發 API Key。
5. 系統只顯示一次明文 API Key，使用者需立即保存。
6. 一般使用者可在「我的 API Key 紀錄」查看本人全部歷史紀錄（`active|revoked|expired`），Key 僅顯示遮罩。
7. 一般使用者可自行停用本人已生效（`active`）的 Key。
8. 使用者可於列表/詳情查看狀態、到期時間與 key 前綴。

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
  - `email` 需存在於白名單且狀態為 `active`
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

### 4) Whitelist Admin Page（白名單管理頁）
- 可用 `sysid`、`account`、`name`、`email` 查詢使用者後加入白名單。
- 可查詢白名單與狀態。
- 可停用/啟用白名單條目。

### 5) Users Admin Page（使用者管理頁）
- 僅 `admin` 可使用。
- 可用 `sysid`、`account`、`name`、`email` 查詢使用者。
- 可授權一般使用者為管理者（`grant-admin`）。
- 可取消其他管理者權限（`revoke-admin`）。
- 前端需阻擋管理者對自己執行 `revoke-admin`（避免誤鎖管理權限）。

### 6) 狀態頁/元件
- Loading
- Empty
- Error（含重試）
- 列表資料以 Data Table 呈現（支援排序與分頁）；僅「操作」欄位不可排序與不可 filter。

## 功能需求
### Must Have（MVP）
- 權限模型僅區分 `user` 與 `admin`
- 僅白名單人員可申請 API Key（以 `email` 比對）
- 白名單管理能力（新增、查詢、停用/啟用）
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
- `admin`：可查詢全部 API Key 與申請紀錄，可管理白名單（`/api/v1/whitelists*`），可授權/取消其他使用者管理者身分（`/api/v1/users/{id}/grant-admin|revoke-admin`）。
- 金鑰啟用狀態以 `api_keys.status` 為唯一判斷來源：`active`=啟用，`revoked|expired`=不可用。

## API 草案
Base path：`/api/v1`

### 1) 申請並核發 API Key
- `POST /api/v1/api-keys/applications`
- 前置條件：
  - 請求必須為已登入使用者（`account`、`name`、`email`、`department`、`sysid` 由 auth context 提供，並以 auth context 為準）
  - `email` 必須存在於 `active` 白名單
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

### 3) 查詢單筆 API Key 紀錄
- `GET /api/v1/api-keys/{id}`
- 規則：`user` 僅可查本人資料；`admin` 可查任意資料；不可回傳明文 key。
- 回傳可包含申請人識別欄位 `owner_account`、`owner_name`（供管理者辨識申請來源）。
- 回傳應包含 `purpose` 供詳情頁顯示；若歷史資料未留存用途，前端顯示 `-`。
- 回傳應包含 `department` 供詳情頁顯示；若歷史資料未留存單位，前端顯示 `-`。

### 4) 停用 API Key
- `POST /api/v1/api-keys/{id}/revoke`
- 規則：`user` 僅可停用本人 `active` key；`admin` 可停用任意 `active` key；停用為軟停用（`status=revoked`）。

### 5) 白名單管理 API
- `POST /api/v1/whitelists`：新增白名單 email
- `GET /api/v1/whitelists`：查詢白名單列表
- `PATCH /api/v1/whitelists/{id}`：更新狀態（`active/inactive`）與備註
- 規則：僅 `admin` 可使用。

### 5-1) 白名單新增前使用者查詢 API
- `GET /api/v1/users?q={keyword}`
- 用途：供管理者以 `sysid`、`account`、`name`、`email` 查詢可加入白名單的人員。
- 規則：僅 `admin` 可使用；回傳欄位至少包含 `id`、`sysid`、`account`、`name`、`email`。

### 6) 管理者授權 API
- `POST /api/v1/users/{id}/grant-admin`：授權指定使用者為管理者
- `POST /api/v1/users/{id}/revoke-admin`：取消指定使用者管理者身分
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
- `APPLICANT_NOT_WHITELISTED`
- `WHITELIST_EMAIL_DUPLICATED`
- `USER_NOT_FOUND`
- `KEY_NOT_OWNED_BY_USER`
- `KEY_NOT_ACTIVE`
- `RATE_LIMITED`
- `INTERNAL_ERROR`

## 驗收標準
1. 白名單 `active` email 可成功核發 API Key，格式為 `AS-` + 30 碼隨機字元（總長 33）。
2. 非白名單 email 申請時，API 回傳 `403` 與 `APPLICANT_NOT_WHITELISTED`。
3. `duration_months` 非 `1|6|12` 時，API 回傳 `INVALID_DURATION_MONTHS`。
4. `application_date` 非法或晚於申請當日，API 回傳 `INVALID_APPLICATION_DATE`。
5. 明文 key 僅於建立成功當下回傳一次；後續查詢不得回傳明文。
6. 資料庫僅存 `key_hash`，不得存 API Key 明文。
7. 一般使用者登入後只能看到自己的全部歷史紀錄。
8. 一般使用者查詢 API Key 時僅能看到 `masked_key`/`key_prefix`，不得看到明文。
9. 一般使用者可停用本人 `active` key，停用後狀態轉為 `revoked`。
10. 一般使用者停用非本人 key 時，API 回傳 `KEY_NOT_OWNED_BY_USER`。
11. 一般使用者停用非 `active` key 時，API 回傳 `KEY_NOT_ACTIVE`。
12. 非白名單或驗證失敗請求不得建立 `api_key_applications` 或 `api_keys` 紀錄。
13. `user` 呼叫 `GET /api/v1/api-keys` 時僅可看到本人資料；`admin` 可看到全域資料。
14. `user` 查詢或停用非本人 key 時，API 回傳 `403`（或既有錯誤碼）。
15. 非 `admin` 使用白名單管理 API（`/api/v1/whitelists*`）時，回傳 `403`。
16. 管理者可成功授權/取消其他使用者的管理者身分（`/api/v1/users/{id}/grant-admin|revoke-admin`）。
17. 使用者透過 SSO/OAuth 登入後，申請頁需自動帶入 `account`、`name`、`email`、`department`、`sysid`。
18. 若 auth context 缺少 `sysid`，申請 API 回傳 `VALIDATION_ERROR` 且不得建立申請紀錄。
19. 管理者不可在前端將自己的角色由 `admin` 降為 `user`。
20. `admin` 呼叫 `GET /api/v1/api-keys` 時，每筆資料需可辨識申請人（至少包含 `owner_account`、`owner_name`）。
21. 調整申請人識別欄位後，既有受保護 API 路徑與角色模型（`user|admin`）不得改動。
22. API Keys 清單頁不得顯示建立時間；建立時間僅顯示於單筆詳情視窗。
23. API Key 詳情視窗需顯示用途（`purpose`）；若無資料則顯示 `-`。
24. API Key 詳情視窗需顯示單位（`department`）；若無資料則顯示 `-`。
25. 申請成功彈窗需提供明文 key 複製功能，點擊後 icon 應由複製狀態切換為成功 check，並可自動恢復。

## Roadmap
### Phase 1：Foundation
- 建立後端專案骨架與資料表 migration
- 實作 `api_key_whitelist`、`api_key_applications`、`api_keys` 基礎模型
- 建立基本錯誤處理與日誌

### Phase 2：MVP API
- 完成白名單管理 API（新增、查詢、停用/啟用）
- 完成申請核發、本人清單查詢、本人單筆查詢、本人停用 API
- 完成管理端查詢/撤銷 API
- 完成白名單檢查、申請欄位驗證、生效時長（月）驗證與一次性明文回傳邏輯
- 補齊 API 測試（成功、驗證失敗、安全性、權限）

### Phase 3：MVP Console UI
- 完成 Apply/My API Keys/API Key Detail Dialog/Whitelist Admin 頁面
- 串接 API 與錯誤提示
- 完成端到端流程驗收

### Phase 4：Expansion
- 串接 OAuth/SSO（完善 `sysid` 與外部身分系統整合）
- 增加多安全等級策略與可配置 key 長度
- 規劃審核流程與配額管理

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

## 使用者流程
1. 使用者登入系統後進入申請頁，系統自動帶入帳號資訊。
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
  - `account`（必填，唯讀，自登入系統帶入）
  - `name`（必填）
  - `email`（必填）
  - `department`（必填）
  - `application_date`（必填，使用者可選）
  - `duration_months`（必填，選單：`1|6|12`）
  - `purpose`（必填）
  - `subject_type`（選填，預留 SSO/OAuth）
  - `subject_id`（選填，預留 SSO/OAuth）
- 驗證：
  - `email` 格式檢查
  - `email` 需存在於白名單且狀態為 `active`
  - `application_date` 格式為 `YYYY-MM-DD` 且不得晚於申請當日
  - `duration_months` 僅允許 `1|6|12`
- 成功送出後顯示一次性 key。

### 2) My API Keys Page（一般使用者我的紀錄頁）
- 顯示範圍：僅本人帳號的全部歷史紀錄（`active|revoked|expired`）。
- 顯示欄位：申請日期、生效時長、狀態、建立時間、到期時間、遮罩 key（或前綴）。
- 操作：僅對本人 `active` key 顯示「停用」按鈕。

### 3) Detail Page（詳情頁）
- 顯示完整申請資訊與狀態。
- 一般使用者僅可查本人資料。
- 一般使用者可停用本人 `active` key。
- 不可再次顯示 key 明文。

### 4) Whitelist Admin Page（白名單管理頁）
- 可新增白名單 email。
- 可查詢白名單與狀態。
- 可停用/啟用白名單條目。

### 5) 狀態頁/元件
- Loading
- Empty
- Error（含重試）

## 功能需求
### Must Have（MVP）
- 僅白名單人員可申請 API Key（以 `email` 比對）
- 白名單管理能力（新增、查詢、停用/啟用）
- 申請後自動核發 API Key
- API 生效時長固定月數選單（`1|6|12`）
- API Key 長度固定 30 碼（MVP 先採最高安全等級）
- API Key 明文只顯示一次
- 系統僅儲存 `key_hash`，不儲存明文
- 一般使用者可查看本人全部申請紀錄
- 一般使用者查詢時 API Key 必須遮罩顯示
- 一般使用者可自行停用本人已生效 key（軟停用）
- 支援撤銷與狀態管理（`active|revoked|expired`）

### Nice to Have（後續）
- OAuth/SSO 串接（由 `subject_type/subject_id` 擴充）
- 多安全等級與長度策略（24-30 碼可配置）
- 申請審核流程
- 使用量監控與配額管理

## 資料模型草案
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
- `subject_type` (string, nullable)
- `subject_id` (string, nullable)
- `created_at` (datetime)
- `updated_at` (datetime)

### Entity: `api_keys`
- `id` (string/uuid)
- `application_id` (fk -> api_key_applications.id)
- `key_hash` (string, required)
- `key_prefix` (string, required)
- `masked_key` (string, computed/response only)
- `length` (int, MVP 固定 30)
- `security_level` (enum, MVP 固定 `high`)
- `status` (enum: `active` | `revoked` | `expired`)
- `created_at` (datetime)

## API 草案
Base path：`/api/v1`

### 1) 申請並核發 API Key
- `POST /api/v1/api-keys/applications`
- 前置條件：
  - 請求必須為已登入使用者（`account` 由 auth context 提供）
  - `email` 必須存在於 `active` 白名單
- Request：
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "department": "Platform Team",
  "application_date": "2026-05-04",
  "duration_months": 6,
  "purpose": "integration for internal service",
  "subject_type": "oauth_user",
  "subject_id": "user_123"
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
  "api_key_plaintext": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "api_key_prefix": "xxxxxx"
}
```

### 2) 一般使用者查詢本人 API Key 清單
- `GET /api/v1/my/api-keys`
- 規則：僅回傳 auth 使用者本人的資料。
- Query（草案）：`page`, `page_size`, `status`, `q`
- Response（200）：
```json
{
  "items": [
    {
      "id": "...",
      "status": "active",
      "masked_key": "abcd****wxyz",
      "key_prefix": "abcd12",
      "expires_at": "..."
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

### 3) 一般使用者查詢本人單筆紀錄
- `GET /api/v1/my/api-keys/{id}`
- 規則：僅可查本人資料；不可回傳明文 key。

### 4) 一般使用者停用本人已生效 Key
- `POST /api/v1/my/api-keys/{id}/revoke`
- 規則：僅可停用本人 `active` key，停用為軟停用（`status=revoked`）。

### 5) 管理端查詢 API Key（既有）
- `GET /api/v1/api-keys`

### 6) 管理端查詢單筆 API Key/申請紀錄（既有）
- `GET /api/v1/api-keys/{id}`

### 7) 管理端撤銷 API Key（既有）
- `POST /api/v1/api-keys/{id}/revoke`

### 8) 白名單管理 API（Admin）
- `POST /api/v1/admin/api-key-whitelist`：新增白名單 email
- `GET /api/v1/admin/api-key-whitelist`：查詢白名單列表
- `PATCH /api/v1/admin/api-key-whitelist/{id}`：更新狀態（`active/inactive`）與備註

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
- `KEY_NOT_OWNED_BY_USER`
- `KEY_NOT_ACTIVE`
- `RATE_LIMITED`
- `INTERNAL_ERROR`

## 驗收標準
1. 白名單 `active` email 可成功核發 API Key，且 key 長度為 30 碼。
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
- 完成 Apply/My API Keys/Detail/Whitelist Admin 頁面
- 串接 API 與錯誤提示
- 完成端到端流程驗收

### Phase 4：Expansion
- 串接 OAuth/SSO（填入 `subject_type/subject_id`）
- 增加多安全等級策略與可配置 key 長度
- 規劃審核流程與配額管理

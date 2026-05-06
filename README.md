# AS API Console

## 專案簡介
AS API Console 是一套 API Key 申請與管理系統，提供從申請、核發、查詢到停用的完整流程。MVP 聚焦在安全可控與最小可用：白名單限制申請、一次性明文顯示、一般使用者僅可查看本人紀錄，並可自行停用已生效 Key。

## 技術棧
- Backend
  - Python `>=3.12,<3.14`
  - FastAPI（API 與 OpenAPI 文件）
  - SQLAlchemy（ORM）
  - Alembic（資料庫 migration）
- Frontend
  - React
  - MUI
- Database
  - SQLite（MVP）
  - PostgreSQL（後續可擴充）
- Auth
  - MVP：一般登入驗證
  - 後續：預留 SSO/OAuth 擴充

## 架構說明
- Backend（FastAPI）
  - 負責白名單驗證、API Key 產生/遮罩、本人資料授權、停用流程與稽核欄位。
- Frontend（React + MUI）
  - 提供申請頁、我的紀錄頁、詳情頁、白名單管理頁（管理者）。
- Data Layer（SQLite + SQLAlchemy/Alembic）
  - 管理 `api_key_whitelist`、`api_key_applications`、`api_keys` 等核心資料。

## 目前功能
已完成：
- 專案規格文件建立
- API Key MVP 功能定義（見 `docs/SPEC.md`）
  - 白名單申請限制
  - 申請欄位（帳號/姓名/Email/單位/申請日期/生效時長）
  - 生效時長限制（`1/6/12` 月）
  - 一次性明文 key 顯示
  - 一般使用者僅可查看本人紀錄（key 遮罩顯示）
  - 一般使用者可自行停用已生效 key

尚未完成：
- Backend/FastAPI 專案骨架與 API 實作
- Frontend/React + MUI 頁面實作
- DB migration 與自動化測試

## 安裝與啟動方式
目前 repository 以文件規劃為主，程式碼骨架尚未建立。以下為目標啟動流程（建立實作後使用）：

1. Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

2. Frontend
```bash
cd frontend
npm install
npm run dev
```

## 專案結構
目前實際結構：

```text
AS-API-Console/
├── README.md
├── docs/
│   └── SPEC.md
└── pyproject.toml
```

目標結構（實作階段）：

```text
AS-API-Console/
├── backend/
│   ├── app/
│   ├── migrations/
│   └── tests/
├── frontend/
│   ├── src/
│   └── package.json
├── docs/
│   └── SPEC.md
└── README.md
```

## 開發指令（規劃）
Backend：
```bash
cd backend
uvicorn app.main:app --reload
pytest
```

Frontend：
```bash
cd frontend
npm run dev
npm run build
npm run test
```

## 規格文件
- 產品與功能規格：`docs/SPEC.md`
- DB 操作與 migration runbook：`docs/runbook-db.md`

## 後續規劃
1. Foundation
- 建立 backend/frontend 基礎骨架與開發環境
- 建立 DB schema 與 migration

2. MVP API
- 實作白名單管理 API
- 實作申請核發、本人紀錄查詢、本人停用 API
- 落實遮罩顯示與權限檢查

3. MVP UI
- 完成 Apply / My API Keys / Detail / Whitelist Admin 頁面
- 串接 API 與錯誤處理

4. Expansion
- 串接 SSO/OAuth
- 增加多安全等級與 key 長度策略（24-30 碼）

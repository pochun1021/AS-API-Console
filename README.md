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
  - Vite
- Database
  - SQLite（MVP）
  - PostgreSQL（後續可擴充）

## 目前狀態
已完成：
- Backend API（`/api/v1/*`）
- Frontend 頁面（Apply / API Keys / Whitelist Admin / Users Admin）
- 前後端串接（前端直連 real API）
- Backend 可直接提供 frontend build 後靜態頁

## 啟動方式
1. 安裝依賴
```bash
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

3. 啟動後端（同時提供 API + 前端頁面）
```bash
cd backend
uv run uvicorn app.main:app --reload
```

4. 開啟系統
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
- Vite dev server 已設定 `/api` proxy 到 `http://127.0.0.1:8000`（若需 `npm run dev` 分離開發可直接使用）。

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

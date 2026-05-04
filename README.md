# AS API Console

## 專案簡介
AS API Console 是一個正在初始化中的應用專案，目標是提供可維護、可擴充的 API 管理與操作介面。目前 repository 仍處於骨架階段，已完成基礎 Python 專案設定，尚未進入功能開發。

## 技術棧
- Python `>=3.14`
- `pyproject.toml`（專案設定與依賴管理入口）

> 註：目前尚未建立前端框架、後端 Web 框架與資料庫實作；相關選型列於後續規劃。

## 安裝與啟動方式
目前可執行的是「專案初始化驗證流程」。

1. 建立虛擬環境
```bash
python3 -m venv .venv
```

2. 啟用虛擬環境
```bash
source .venv/bin/activate
```

3. 安裝專案（目前無額外依賴）
```bash
pip install -e .
```

4. 基本檢查
```bash
python -V
```

## 目前功能（已完成）
- 專案 Git 倉庫初始化
- Python 專案基本 metadata 設定（`pyproject.toml`）
- README/SPEC 文件基礎規格建立

## 目前功能（尚未完成）
- `src/` 應用程式程式碼
- 使用者介面頁面與元件
- API 路由與商業邏輯
- 資料模型與持久化層
- 自動化測試

## 專案結構
目前實際結構：

```text
AS-API-Console/
├── README.md
├── docs/
│   └── SPEC.md
└── pyproject.toml
```

下一階段建議結構：

```text
AS-API-Console/
├── src/
│   └── as_api_console/
├── tests/
├── docs/
│   └── SPEC.md
├── README.md
└── pyproject.toml
```

## 開發指令
- 建立虛擬環境：
```bash
python3 -m venv .venv
```
- 啟用虛擬環境：
```bash
source .venv/bin/activate
```
- 安裝專案：
```bash
pip install -e .
```
- （規劃中）執行測試：
```bash
pytest
```
- （規劃中）啟動本機開發服務：
```bash
# 待框架與入口建立後補上
```

## 後續規劃
1. 建立應用基礎骨架（`src/`、`tests/`、設定檔）
2. 定義 MVP 核心資料模型與 CRUD 範圍
3. 建立第一版 API（List / Detail / Create / Update）
4. 建立 Console 最小頁面流程（清單、詳情、表單）
5. 補齊測試、驗收標準與 CI

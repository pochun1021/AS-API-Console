# Issue #58：SQL → HTTP API → 圖表對帳紀錄

驗證日期：2026-11-20。使用 `feature/dashboard-issue-58` 的本機程式、隔離的 SQLite 資料庫與本機 HTTP 服務；未讀寫 Production 資料。原始 SQL 見 [issue-58-reconciliation.sql](issue-58-reconciliation.sql)，實際畫面見 [issue-58-chart.png](issue-58-chart.png)。

## 固定資料與口徑

執行 `backend/scripts/issue58_reconciliation_seed.py` 建立 9 筆申請及 9 把 key，日期為 2026-05-01 至 2026-05-09：

| 申請人 | 單位 | key 狀態 | 申請日期 |
| --- | --- | --- | --- |
| alice | IT | active | 2026-05-01 |
| alice | R&D | revoked | 2026-05-02 |
| bob | IT | active | 2026-05-03 |
| bob | IT | active | 2026-05-04 |
| carol | IT | expired | 2026-05-05 |
| dave | R&D | active | 2026-05-06 |
| erin | IT | revoked | 2026-05-07 |
| frank | R&D | active | 2026-05-08 |
| grace | IT | active | 2026-05-09 |

查詢條件：`scope=all`、`from=2026-05-01`、`to=2026-05-31`、`x_axis=department`、`y_axis=total_applications`、`top_n=5`。與 `statistics/users` 相同，先以申請人分組，再以該申請人的 `MAX(department)` 歸屬單位；alice 的兩筆因此都歸 R&D。只計入有對應 key 的申請，`api_keys.application_id` 為唯一欄位。

預期值：IT = 5、R&D = 4；完整總量 = 9、Top N 小計 = 9、分組數 = 2。另以 `x_axis=account&top_n=5` 驗證截斷：完整總量 = 9、可見小計 = 7、完整分組數 = 7。狀態分布為 active = 6、revoked = 2、expired = 1，合計 9。

這四個數字各有不同意義：**申請筆數 9**、**已發 API Key 數 9**、**申請人數 7**、**帳號 Top 5 的可見柱狀小計 7**。前兩者在本 fixture 相等，是因為 `api_keys.application_id` 唯一且每筆申請恰有一把 key；它們不是同一個欄位。`total_applications` 的計數單位是「有對應 key 的申請」，四個狀態指標的計數單位也是這些申請的 key 狀態。當 `scope=all` 且狀態互斥、完整覆蓋時，`active_count + revoked_count + expired_count = total_applications`；有狀態篩選或只看 Top N 時，不應將可見小計冒充完整總數。

## 重跑步驟

從專案根目錄執行。資料庫路徑必須是新的 `.sqlite` 檔案；seed 腳本遇到既存檔案會拒絕覆寫。

```bash
mkdir -p /tmp/as-api-issue58-evidence
backend/.venv/bin/python backend/scripts/issue58_reconciliation_seed.py /tmp/as-api-issue58-evidence/fixture.sqlite
sqlite3 -header -column /tmp/as-api-issue58-evidence/fixture.sqlite < docs/issue-58-reconciliation.sql
```

在另一個終端機啟動只使用這份隔離資料的後端。此次使用 8001，因為 8000 已有其他本機服務；若 8001 也被占用，請選閒置埠並同步調整下方 URL。

```bash
cd backend
ENV_FILE=/dev/null APP_ENV=dev \
DATABASE_URL=sqlite:////tmp/as-api-issue58-evidence/fixture.sqlite \
ALLOW_HEADER_AUTH=true ISSUANCE_PROVIDER_MODE=local \
DEV_LOGIN_ACCOUNT=evidence.admin DEV_LOGIN_NAME='Evidence Admin' \
DEV_LOGIN_EMAIL=evidence.admin@example.com DEV_LOGIN_DEPARTMENT=IT \
DEV_LOGIN_SYSID=900001 DEV_LOGIN_ROLE=admin \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
```

真實 HTTP API 請求（不使用 mock provider）：

```bash
curl -sS \
  -H 'x-account: evidence.admin' -H 'x-name: Evidence Admin' \
  -H 'x-email: evidence.admin@example.com' -H 'x-department: IT' \
  -H 'x-sysid: 900001' -H 'x-role: admin' \
  'http://127.0.0.1:8001/dev/api/v1/api-keys/statistics/chart?x_axis=department&y_axis=total_applications&top_n=5&scope=all&from=2026-05-01&to=2026-05-31'
```

前端使用 `VITE_API_PROVIDER=real npm run build` 建置，由同一個後端提供 `/dev/` 靜態頁面。在隔離的 Playwright CLI 工作階段登入 `http://127.0.0.1:8001/dev/`，開啟「管理者統計 → 圖表」，設定狀態「全部」、日期 2026-05-01 至 2026-05-31、X 軸「單位」、Y 軸「總申請數」、Top N = 5；滑過兩根柱讀取 tooltip。瀏覽器網路紀錄的圖表請求 URL 與上方 curl 完全一致，狀態碼為 200。

## 實際結果

| 層次 | 實際觀測 | 對照預期 |
| --- | --- | --- |
| 原始 SQL | `IT 5`、`R&D 4`；`group_count 7`、`total_value 9`、帳號 Top 5 `displayed_value 7`；狀態 `6 / 2 / 1` | PASS |
| HTTP 單位圖表 | `{"items":[{"label":"IT","value":5},{"label":"R&D","value":4}],"total_value":9,"displayed_value":9,"group_count":2}` | PASS |
| HTTP 帳號 Top 5 | `alice 2, bob 2, carol 1, dave 1, erin 1`；`total_value=9`、`displayed_value=7`、`group_count=7` | PASS |
| HTTP 表格分頁 | `page_size=5` 僅回 5 位申請人，`total=7`；圖表仍計入全部 9 筆申請 | PASS |
| 瀏覽器圖表 | 顯示 IT、R&D 兩根柱；tooltip 分別為「總申請數 5」、「總申請數 4」；DOM 中三項摘要文字數量為 0 | PASS |

圖表 UI 不顯示「符合條件的指標總量」、「Top N 顯示小計」、「完整分組數」，但 API 仍提供這三個欄位供聚合對帳。這份紀錄只驗證上述固定資料與參數；extend、owner 篩選及其餘軸/狀態組合由 `backend/tests/test_api_key_statistics_chart.py` 和 `frontend/src/test/AdminDashboardPage.test.jsx` 的定向回歸測試涵蓋。

定向驗證：`python -m py_compile`（新增 seed 腳本、統計測試與相關後端檔案）通過；`uv run pytest tests/test_api_key_statistics_chart.py -q -x` 通過；`npm test -- --run src/test/AdminDashboardPage.test.jsx` 通過；`VITE_API_PROVIDER=real npm run build` 通過。以上測試均只針對 Issue #58 的相關檔案，未執行全套回歸或 Production API。

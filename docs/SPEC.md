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
1. 使用者透過 SSO/OAuth 登入時，系統先檢查進入資格：優先查本系統特殊人員名單（`sysid` 且 `active`），再查管理者名單（`admins.id=sysid` 且 `active`），兩者都未命中才檢查 `tCode` 是否命中 `LOGIN_ALLOWED_TITLE_CODES`。`whitelist` 僅作為 eligibility allowlist，不得作為角色來源；若同一身份同時命中 `active whitelist(sysid)` 與 `active admins(id=sysid)`，資格視為通過，最終角色仍以 `admins` 判定為 `admin`。
2. 通過進入資格後進入申請頁，系統自動帶入 `account`、`name`、`email`、`department`、`sysid`（對應 OAuth claims：`cn`、`chName`、`email`、`instCode`、`sysId`）。
3. 一般使用者填寫申請日期、用途與 API 生效時長；管理者可選擇代他人送出申請，僅需填寫目標 `account`，其餘身份欄位由系統查詢補齊。
4. 送出申請時依 `POST /main/api/v1/api-keys/applications` 契約再次檢查資格與 request/auth 驗證。
5. 資格檢查通過後系統立即核發 API Key 並回傳一次性明文；不需經過常態管理者審核。若 provider timeout/5xx，系統直接回傳 `503 PROVIDER_UNAVAILABLE`，且不得建立 pending 申請。
6. 系統只顯示一次明文 API Key，使用者需立即保存。
7. 一般使用者可在「我的 API Key 紀錄」查看本人歷史紀錄（`active|revoked|expired`），Key 僅顯示遮罩；`APP_ENV=prod` 顯示 `sk-...` + 後 4 碼，`dev/test` 顯示 `AS-...` + 後 4 碼。若舊 key 已被 renew，該舊 key 對一般使用者隱藏。
8. 一般使用者可自行停用本人已生效（`active`）的 Key。
9. 使用者可於列表/詳情查看狀態、到期時間與遮罩 key；`APP_ENV=prod` 為 `sk-...XXXX`，`dev/test` 為 `AS-...XXXX`。

## 頁面規格
### 1) Apply Page（申請頁）
- 欄位：
  - `account`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `name`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `email`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `department`（必填，唯讀，自 SSO/OAuth 登入帶入）
  - `sysid`（必填，唯讀，自 SSO/OAuth 登入帶入；純數字）
  - `application_date`（必填，使用者可選）
  - `duration_days`（必填，選單：`30|180|360`）
  - `purpose`（必填）
  - `target_identity`（選填；僅 `admin` 可傳，欄位：`account`）
- 驗證：
  - `email` 格式檢查
  - `sysid` 必須為純數字（整數語意）
  - `application_date` 格式為 `YYYY-MM-DD` 且不得晚於申請當日
  - `duration_days` 僅允許 `30|180|360`
  - 所有會寫入後端的文字欄位採共用 persisted-text 驗證：允許正常中英文、數字、空白與常見標點，但若包含明顯程式語法片段（至少包含 HTML tag、`<script...>`、`</script>`、`javascript:`、明顯 SQL injection 片段、明顯 JS `function(...)` / `=>` 語法）需阻擋送出
  - 送出申請時的 auth context 驗證、資格檢查、錯誤碼與 provider/SOAP 錯誤語意，以 `POST /main/api/v1/api-keys/applications` 契約為準
  - `admin` 代申請時，`target_identity.account` 必填；目標 `name`、`email`、`department`、`sysid` 由後端目錄查詢補齊
- `admin` 代申請時，前端於 `target_identity.account` 欄位 `blur` 後需呼叫 `GET /main/api/v1/users?q=...&lookup_context=proxy_application` 查詢目標身份資料並帶入唯讀欄位
  - 若查詢結果多筆，前端需顯示候選清單供 `admin` 明確選擇；未完成選擇前不得送出申請
  - `admin` 代申請時，若帳號查無需顯示「查無帳號」；若查詢服務異常需顯示 `soap service unavailable`，兩者皆以獨立 `error` alert 顯示於上述 info 提示之後
  - `purpose`、`target_identity.account` 違反 persisted-text 驗證時，前端需先提示並禁止送出；直接打 API 時後端需回 `422 VALIDATION_ERROR`
  - 限制策略由管理者透過模板資源維護；一般使用者申請時不可提交策略細節
- 成功送出後顯示一次性 key，並提供複製操作；複製成功需有明確視覺回饋（check icon 後恢復）。
- 一次性明文 key 彈窗僅可透過明示確認按鈕關閉；不得因 backdrop click、`Esc` 或其他一般 `onClose` 事件消失。
- 複製流程以 Clipboard API 為唯一可驗證複製路徑；若不可用或複製失敗，需提示使用者手動複製。
- 透過複製 icon 觸發時不得要求使用者先反白金鑰文字，系統需直接完成複製。

### 2) Service Usage Guide Page（服務使用說明頁）
- `user` 與 `admin` 都可使用。
- 正式路由為 `/usage-examples`。
- 正式入口使用既有主導覽列中的「服務使用說明」項目；第一版不另外要求在 Apply Page 提供快捷入口。
- 主導覽列中的「服務使用說明」入口需緊接在「系統公告」右側。
- 登入後共用主導覽列需支援 responsive 版型：
  - 桌機寬度維持頂部 horizontal navigation。
  - 較小寬度需切換為 hamburger menu + Drawer，不再把所有導覽項目硬塞在同一列。
  - desktop nav 與 Drawer nav 需共用同一組導覽項定義；`user`、`admin` 的可見項目規則不得分叉。
- responsive 主導覽列驗收規則：
  - 小螢幕下導覽標籤不得互相重疊、擠壓到不可讀，且不得造成水平 overflow。
  - active route 標示在桌機與 Drawer 內都需維持正確。
  - 語言切換與登出在較小寬度下仍需可直接操作。
  - mobile 導覽不得依賴 hover。
  - 第一版不採水平可捲動導覽列，也不以多排換行 top nav 作為主要解法。
- 頁面需同時呈現兩類資訊：
  - 服務使用說明文件（靜態內容）
  - 可用模型清單（動態資料）
- 說明文件內容以 repo 內 markdown 維護，第一版文件來源為：
  - `docs/service-usage-guide.zh-TW.md`
  - `docs/service-usage-guide.en.md`
- 前端依目前 locale 載入對應文件。
- 文件內容第一版至少需包含：
  - 這份文件用途與適用對象
  - 申請 API Key 前需要準備的資訊
  - 串接步驟摘要
  - 用量限額，至少需明示每筆 API Key 的 RPM、每日 token 額度、同時連線數與上下文視窗
  - 至少一組 Python 範例
  - 注意事項，例如明文 key 只顯示一次、應立即保存、不要把 key 寫死在前端、建議用環境變數管理
- 第一版 Python 範例內容需參考既有測試腳本 `../AI-Api-test/afs_chat_completions.py`，但畫面不得依賴 repo 外檔案；需將可顯示版本收斂並維護在 repo 內文件。
- 第一版 Python 範例需至少涵蓋：
  - 以環境變數讀取 `API_KEY`、`BASE_URL`
  - 呼叫 `POST /v1/chat/completions`
  - 使用 `Authorization: Bearer <API_KEY>`
  - payload 至少包含 `model`、`messages`
  - 由 response `choices[0].message.content` 取出回應內容
- 頁面中的模型清單區塊需沿用 `GET /main/api/v1/models`，並與服務使用說明文件顯示於同一頁。
- 第一版不新增後端 API。
- `GET /main/api/v1/models` 成功回應固定為 `{ items, total, fetched_at }`，其中 `items[*]` 僅包含 normalized `{ id, label }`。
- `APP_ENV=dev/test` 時，`GET /main/api/v1/models` 直接回系統內建測試資料：`gpt-4o`、`gpt-4o-mini`；`APP_ENV=prod` 才讀取 provider `/models`。
- 若 provider `/models` timeout、回 `5xx`、或成功但 payload 無法辨識，後端需統一回 `503 PROVIDER_UNAVAILABLE`，不得透出 provider 原始 payload/error shape。
- 頁面 mount 時需自動查詢一次模型清單。
- 頁面停留期間需每 `15` 分鐘自動刷新一次。
- 頁面需提供手動重新整理按鈕，且與自動刷新共用同一個 `load()` 流程。
- 第一版模型清單僅顯示基本資料，不顯示 metadata、access groups、team/global 切換或其他進階資訊。
- 第一版模型列表以 Data Table 呈現，僅需一欄 `Model`，顯示 `label`。
- 頁面需提供 Loading、Empty、Error（含 Retry）狀態。
- 頁面 unmount 時需清除 refresh timer，避免重複請求。

### 2-1) System Announcement Surface（系統公告區塊與管理頁）
- 登入後共用版型不顯示系統公告區塊；公告集中於獨立的 `System Announcements Page`。
- 第一版不要求使用者已讀、關閉、pin、排序權重或附件能力。
- 公告有效條件為：
  - `status=active`
  - `publish_from` 為空或 `publish_from <= now`
  - `publish_to` 為空或 `publish_to >= now`
- 公告內容格式第一版固定為：
  - `title`（必填）
  - `body`（必填；純文字）
- 公告內容需套用 persisted-text 驗證；第一版不支援 Markdown、HTML、富文字編輯器、公告內 CTA 連結或圖片。
- 「服務使用說明」連結第一版需常駐於 `System Announcements Page`：
  - `user` 與 `admin` 都可見
  - 連到既有 `/usage-examples`
  - 不可被 admin 直接刪除、停用或由一般公告內容覆蓋成其他連結/內容
- `user` 與 `admin` 登入後首頁預設都需導向獨立的 `System Announcements Page`；但 API Key 正式上線前，`user` 首次進入 `/main/` 時可先導向 `coming-soon` 提示頁。
- `System Announcements Page`：
  - `user` 與 `admin` 都可使用，且主導覽列中的「系統公告」入口需位於最左側。
  - 主導覽列中的「服務使用說明」入口需位於「系統公告」右側，作為固定相鄰入口。
  - 主導覽列在較小寬度下切換為 Drawer 時，`系統公告` 與 `服務使用說明` 仍需維持前兩個共享入口順序。
  - `user` 進入此頁時，僅可查看目前有效公告；不得看到 inactive、未上架、已下架公告，也不得看到新增、編輯、刪除等管理操作。
  - `user` 與 `admin` 的公告列表都需使用表格式呈現，且公告內文不得直接常駐於列表中。
  - `user` 與 `admin` 都可點擊公告 `title` 開啟 modal 查看完整 `body`。
  - 頁面內需固定提供「服務使用說明」入口，且不受是否有有效公告影響。
  - API Key 正式上線前，`user` 視圖需額外提供固定入口連往 `/apply/coming-soon`，供使用者查看上線時間與倒數；此入口不得取代既有公告列表或服務使用說明入口。
  - 公告列表查詢互動需比照 `My API Keys Page` 的頁面外查詢欄位模式，不使用 DataTable 內建篩選器面板。
  - `user` 視圖需提供 `title` 搜尋，以及 `publish_from`、`publish_to` 的時間區間查詢；查詢結果仍僅限目前有效公告。
  - `user` 視圖需提供 Loading、Empty、Error（含 Retry）狀態。
  - `admin` 視圖需提供公告管理能力。
  - `admin` 主表格屬於 `server-side table`。
  - `admin` 列表至少顯示：`title`、`status`、`publish_from`、`publish_to`、`updated_at`、`actions`
  - `admin` 查詢可使用 `title`、`status`、`publish_from`、`publish_to`、`updated_at` 的頁面外查詢欄位。
  - `admin` 可新增、編輯、刪除公告。
  - `admin` 表單欄位至少包含：`title`、`body`、`status`、`publish_from`、`publish_to`
  - 若 `publish_from` 與 `publish_to` 同時存在，需滿足 `publish_from <= publish_to`
  - `admin` 頁面需提供 Loading、Empty、Error（含 Retry）狀態。

### 3) My API Keys Page（一般使用者我的紀錄頁）
- 顯示範圍：僅本人帳號歷史紀錄（`active|revoked|expired`）；若舊 key 已被 renew，對一般使用者隱藏。
- 顯示欄位：申請日期、生效時長、狀態、到期時間、遮罩 key、操作（其中包含 Usage icon；`APP_ENV=prod` 為 `sk-...` + 後 4 碼；`dev/test` 為 `AS-...` + 後 4 碼）。
- `Usage` 明細入口需放在操作區，並使用中性、非 color-coded 的 icon。
- 點擊 `Usage` icon 需開啟 popover；popover 需顯示 `spend`、`max_budget`、`remaining_budget`、`budget_reset_at`、`synced_at`。`tpm_limit`、`rpm_limit`、`max_parallel_requests` 不在此 popover 顯示；其中 `max_budget` 需對齊目前金鑰管理（limit strategy config）設定值。
- `usage_summary`（含 popover 顯示內容）僅代表目前 reset 週期內的使用量；若已跨過當期 reset 邊界，不得再顯示重置前歷史累計。
- `usage_summary.budget_reset_at` 直接使用 provider `/spend/keys` 回傳或其同步鏡像值，語意固定為「下一次重置時間」；若 provider 未提供則回傳 `null`，後端不得自行推算或 rollover。
- `Usage` popover 需提供可直接導向 `/usage` 的入口，並帶出目前這把 key 作為預選目標；使用者進入 `Usage Page` 後不得還需要重新手動選同一把 key 才能查圖。
- `Usage` popover 在 `max_budget > 0` 時，需額外顯示 budget progress bar；若 `spend` 缺值則以前端 `0` 顯示，並以 `spend / max_budget` 呈現已使用比例，同步顯示已使用百分比與剩餘百分比。
- 已使用百分比需採無條件進位到小數第 2 位，且顯示時不強制補尾零；例如 `85%` 保持 `85%`、`84.001%` 顯示 `84.01%`。
- 剩餘百分比顯示需與已使用百分比互補，以上述「已使用顯示值」計算 `100 - used_percent_display`，避免兩者相加不為 `100%` 的視覺落差。
- progress bar 的已使用文案需在百分比後追加 `({total_tokens} tokens)`；若當前 `usage_summary.total_tokens` 缺值則省略括號段落，不得顯示 `unknown`。
- 當 `Usage` popover 已顯示 budget progress bar 時，不需再重複顯示獨立的 `spend`、`max_budget`、`remaining_budget` 三行文字；`Unlimited` 或其他未顯示 progress bar 的情況才保留這三行文字摘要。
- 當剩餘額度比例 `<= 20%` 時，budget progress bar 需改用警示樣式並顯示明確警示文案；此提示僅屬視覺警示，不得阻擋任何操作。
- 列表不得額外展開成 `spend / budget / TPM / RPM` 多個 raw numeric 欄位，避免表格過度擁擠。
- 若某筆資料缺少 usage snapshot，該列仍需顯示可點擊的 `Usage` icon；popover 內各欄位顯示 `Unknown` 或 `-`。
- 當 `max_budget=0` 時，前端需視為 unlimited，顯示 `Unlimited`，不得顯示為 `0` 的有限額度。
- `Unlimited`（`max_budget=0`）在 `Usage` popover 內不得渲染百分比 progress bar，需改以純文字狀態呈現；若 `max_budget > 0` 但缺少 usage snapshot 或 `spend`，仍需顯示 progress bar，並以前端 `0%` / `0 / budget` 呈現。
- 清單查詢模式屬於 `server-side table`：分頁、排序、欄位篩選皆需由後端處理；前端不得以當前頁 rows 執行 local filter。
- 狀態篩選欄位初始值需為 `active`（啟用中）；首次進頁時預設僅顯示啟用中 keys。使用者可再切換成 `revoked`、`expired` 或清空為全部狀態。
- 「清除篩選」按鈕需將預設 `active` 視為已套用的篩選條件，因此首次進頁時按鈕應為可點擊；點擊後需清空狀態篩選並回到全部狀態與第一頁。
- 時間欄位語意：
  - 成功申請或 extend 後：`application_date` 為最近一次申請或成功展延後的起算日；`duration_days` 為目前這一輪有效期時長；`expires_at` 為目前有效到期時間。
  - `expires_at` 一律採 fixed-day 規則計算：生效時長固定僅允許 `30|180|360` 天。初次核發與後續每次 extend 都以當次起算日重新計算 `expires_at = application_date + effective_duration_days`；`duration_days` 不做累加。
  - 前端在 API Key 清單與詳情顯示 `expires_at` 時，僅顯示 `YYYY-MM-DD` 日期，不顯示時分秒。
- 管理者在同頁可額外查看申請人識別欄位（`owner_account`、`owner_name`）。
- 日期區間篩選 UI 需使用 Date Range Picker，並以雙月曆（開始/結束）呈現 `application_date` 與 `expires_at` 的區間選擇。
- 管理者在同頁可查看並編輯 `key_alias`；若資料未設定，預設顯示系統產生 alias（初始為 `for_{owner_account}`，若 provider 回報衝突則自動改為 `for_{owner_account}_vN`）。管理者手動輸入時僅允許中英文、數字、`_`、`-`、`、`，不得包含空白或其他符號。
- 操作：
  - 對 `active` key 顯示「停用」與「展延（extend）」按鈕。
  - 對 `expired` key 顯示「續發（renew）」按鈕（icon + 文字）。
  - 對 `revoked` key 顯示「續發（renew）」按鈕（icon + 文字）。
  - `active` key 一律顯示展延按鈕；前端不得再以「距離到期 30 天內」作為顯示或送出限制。
  - extend 需以確認 Dialog 送出，不再提供 `duration_days` 選單；每次 extend 一律沿用該 key 的 `original_duration_days` 作為本次展延基數。
  - renew 會建立新 key，來源 key 對 `user` 列表需隱藏。
  - extend 會沿用原 key，只延長有效期限。

### 3-1) Usage Page（API Key 使用量頁）
- 正式路由為 `/usage`。
- `user` 與 `admin` 都可使用。
- 進頁後若未選擇 API Key，頁面預設顯示「全部可見 API Keys」的歷史累計使用量摘要，不限時間區段。
- 「全部可見 API Keys」權限口徑：
  - `user`：僅聚合本人全部 keys 的歷史 usage
  - `admin`：可聚合系統內全部可見 keys 的歷史 usage
- 未選 key 的全部模式不顯示每日圖表；改以 summary card 顯示至少 `total_tokens`，並同步顯示 `prompt_tokens`、`completion_tokens`。
- `user` 僅可從自己的 keys 中選擇；`admin` 可選擇任意 key。
- API Key 下拉選單需顯示全部可見 API Keys，不限制核發時間或狀態；權限口徑同全部模式，`user` 僅可選本人 keys，`admin` 可選系統內全部可見 keys，且需包含 `active|revoked|expired`。
- 選定單一 API Key 後，頁面切換為日期區間歷史查詢模式。
- 單 key 模式需提供可自訂的日期區間查詢，查詢口徑以 `Asia/Taipei` 的日曆日為準。
- 進入 `/usage` 頁時，單 key 模式的日期區間預設為以 `Asia/Taipei` 計算的最近 `7` 個日曆日（含當日），日期欄位不得顯示為空。
- 單 key 模式的日期區間 picker 需提供快捷選日按鈕：`最近 7 日`、`最近 14 日`、`最近一個月`，點擊後需立即套用對應區間。
- 第一版單 key 圖表僅支援 `day` 粒度，不提供小時圖或其他 bucket 粒度切換。
- 單 key 模式主圖表指標固定為 `total_tokens` 的每日趨勢。
- 單 key 模式圖表 X 軸需對齊查詢日期區間的完整日曆日；前端可將缺資料日期補為 `null` bucket 以維持日期連續性，但不得補成 `0` 形成假用量。
- 當單 key 查詢區間超過 `31` 個日曆日時，主圖預設僅顯示自 `from` 起算的前 `31` 天視窗，並提供底部日期區間 slider；slider 視窗最大為 `31` 天、最小為 `1` 天，使用者可縮小顯示區間，且縮小後仍可整段左右平移瀏覽整個查詢範圍。
- 單 key 模式 slider 互動需區分：拖曳 `start/end` thumb 用於調整開始/結束日期；拖曳中間已選取區塊（track）則以目前區間長度整段平移。
- 單 key 模式 slider 兩端的開始/結束日期 label 需完整可見，不得被卡片或畫面邊界裁切。
- 單 key 模式每個資料點的 tooltip 至少需顯示：`prompt_tokens`、`completion_tokens`、`total_tokens`。
- 頁面需提供 Loading、Empty、Error（含 Retry）狀態。
- 單 key 模式若查詢區間內無資料，需顯示空狀態，不得以 `0` 補滿整段日期區間形成假資料。
- 前端查圖與全部模式總量資料皆需使用既有後端 API，不新增前端自行聚合 provider logs 的流程。
- 單 key 模式 `/usage` 圖表屬於日期區間歷史查詢，不因 `usage_summary` 的 reset 週期口徑而自動裁切或隱藏重置前日 bucket。

### 4) API Key Detail Dialog（詳情視窗）
- 顯示完整申請資訊與狀態。
- 顯示欄位至少包含：申請日期、生效時長、用途（`purpose`）、單位（`department`）、建立時間、到期時間、遮罩 key。
- 詳情視窗需沿用 API 時間欄位語意，不得把曾展延 key 的 `application_date`、`duration_days`、`expires_at` 顯示成彼此矛盾的資訊：
  - extend 後需顯示更新後的 `application_date`（即最近一次成功展延當日）與本輪 `duration_days`（即 `original_duration_days`）。
- 一般使用者僅可查本人資料。
- 一般使用者可停用本人 `active` key。
- 一般查詢/詳情不可再次顯示 key 明文（僅受控 reveal 流程可回取）。
- 管理者可於詳情視窗編輯 `key_alias`。

### 5) Whitelist Admin Page（特殊人員名單管理頁）
- 可用 `account`、`name` 查詢使用者後加入特殊人員名單。
- 名單表格屬於 `server-side table`：分頁、排序、欄位篩選皆需由後端處理；前端不得以當前頁 rows 執行 local filter。
- 查詢候選表格屬於 `local-full-dataset table`：目前可保留前端 local sorting/filter/pagination。
- 可查詢特殊人員名單與狀態，列表需顯示 `account`、`name`、`email`。
- 名單表格支援 `status`、`sysid`、`account`、`name`、`email`、`created_at`、`updated_at` 的 server-side 篩選；其中 `status`、`sysid` 為 exact match，`account`、`name`、`email` 為 case-insensitive `contains`，時間欄位為區間查詢。
- `created_at`、`updated_at` 的日期區間篩選 UI 需使用 Date Range Picker，並以雙月曆（開始/結束）呈現。
- 名單表格預設排序為 `created_at desc`；`note` 與 `actions` 欄位不得提供誤導使用者的前端 filter/sort UI。
- 可停用/啟用特殊人員名單條目。
- 可刪除特殊人員名單條目（實體刪除）。
- `note` / 備註欄位需支援中英文、數字、空白、`_`、`-`、`、`，且不得因前端驗證破壞中文輸入法組字。
- `note` 違反 persisted-text 驗證時，前端需在儲存前提示並阻止送出；直接打 API 時後端需回 `422 VALIDATION_ERROR`。

### 6) Admin List Page（管理者名單頁）
- 僅 `admin` 可使用。
- 名單表格屬於 `server-side table`：分頁、排序、欄位篩選皆需由後端處理；前端不得以當前頁 rows 執行 local filter。
- 查詢候選表格屬於 `local-full-dataset table`：目前可保留前端 local sorting/filter/pagination。
- 列表需顯示全部管理者名單（來源 `admins`，含 `active`、`inactive`），不得只顯示啟用中資料。
- 列表需顯示管理者狀態（`active`/`inactive`），停用後不得自動從名單移除。
- 名單表格支援 `status`、`sysid`、`account`、`name`、`email`、`created_at`、`updated_at` 的 server-side 篩選；其中 `status`、`sysid` 為 exact match，`account`、`name`、`email` 為 case-insensitive `contains`，時間欄位為區間查詢。
- `created_at`、`updated_at` 的日期區間篩選 UI 需使用 Date Range Picker，並以雙月曆（開始/結束）呈現。
- 名單表格預設排序為 `created_at desc`；`actions` 欄位不得提供誤導使用者的前端 filter/sort UI。
- 可用 `account`、`name` 查詢使用者。
- 可啟用一般使用者的管理者權限（對應 `enable`）。
- 可停用其他管理者的管理者權限（對應 `disable`）。
- 可新增管理者（對應 `PUT /main/api/v1/admins/{id}`，建立後狀態為 `active`）。
- 可刪除停用中的管理者（對應 `DELETE /main/api/v1/admins/{id}`，僅允許 `inactive`）。
- 前端需阻擋管理者對自己執行管理者停用（避免誤鎖管理權限）。
- 前端在「新增管理者」查詢結果中，對已存在於管理者名單（`active` 或 `inactive`）的人員，不得顯示新增按鈕。

### 7) Admin Dashboard Page（管理者統計頁）
- 僅 `admin` 可使用。
- 以 Data Table 呈現每位申請人的統計資料，欄位至少包含：`account`、`name`、`email`、`total_applications`、`active_count`、`revoked_count`、`expired_count`、`last_applied_at`。
- 表格查詢模式屬於 `server-side table`：分頁、排序、欄位篩選皆需由後端處理；欄位 filter 不得退化成單純前端本頁比對。
- 提供「圖表 / 表格」視圖切換；圖表以長條圖呈現。
- 篩選欄位（`scope`、日期區間、欄位篩選）僅於表格視圖顯示；切換到圖表視圖時不顯示篩選列，但圖表仍沿用目前查詢口徑。
- 圖表支援 X 軸切換：`account|department`，Y 軸切換：`total_applications|active_count|revoked_count|expired_count`，與 Top N（`5|10|20`）切換。
- 圖表 X 軸分類文字需直接顯示在圖下方，不可僅依賴滑鼠 hover tooltip 才能辨識帳號/單位。
- X 軸刻度文字在圖表視圖中不得被自動省略為僅部分可見（需可直接辨識每個可見柱狀分類）。
- 支援口徑切換 `scope`：`all|active|revoked|expired`（預設 `all`）。
- 支援日期區間篩選：`from`、`to`（`YYYY-MM-DD`），統計基準為 `application_date`。
- 日期區間篩選 UI 需比照 API Keys 頁使用 Date Range Picker，並以雙月曆（開始/結束）呈現。
- 支援 `owner_account`、`owner_name`、`owner_email`、`owner_department` 欄位查詢、分頁與排序。
- `owner_department` 篩選 UI 需使用下拉選單；選項值以單位代碼送出，顯示文字需為「單位代碼 + 單位名稱」。
- 表格視圖的篩選列需提供「清除篩選」按鈕，可一次重置目前所有篩選欄位並回到第一頁。
- 預設排序為 `total_applications desc`。
- 圖表口徑需與目前篩選條件一致（`scope`、`from`、`to`、欄位篩選、`sort`）。
- 表格中的 `total_applications` 與 `active_count` 需可點擊，並以 Dialog 顯示該申請人的 API Key 明細（僅遮罩 key，不得回傳明文）。
- Dialog 明細預設欄位為 `key_alias`、`masked_key`、`status`；且需跟隨目前統計頁日期篩選（`from`、`to`）。

### 7-1) Institute View Page（單位代碼資料檢視頁）
- 僅 `admin` 可使用。
- 目的：供管理者確認 DB `institutes` 資料是否已寫入。
- 資料來源僅 `GET /main/api/v1/institutes`（僅顯示 `active` institutes）。
- 清單查詢模式屬於 `local-full-dataset table`：頁面一次載入完整資料後，可保留前端 local sorting/filter/pagination。
- 頁面需顯示 `total` 與列表資料，欄位至少包含：`inst_code`、`inst_name`、`abb_inst_name`、`einst_name`、`division`。
- 需提供 Loading、Empty、Error（含重試）狀態。
- 頁面需提供手動同步操作，觸發 `POST /main/api/v1/institutes/sync`。
- 前端需保留既有頁內 `syncing` 防重送保護；若 API 回 `429 INSTITUTE_SYNC_IN_PROGRESS`，需明確提示同步已在進行中。
- 若 API 回 `429 INSTITUTE_SYNC_COOLDOWN`，前端需使用 API 回傳的 `retry_after_seconds` 啟動倒數，顯示剩餘冷卻時間，並於倒數期間停用同步按鈕。
- 冷卻倒數顯示格式需支援 `X 分 Y 秒`；剩餘不足 1 分鐘時可僅顯示秒數。
- 因 `429 INSTITUTE_SYNC_IN_PROGRESS` 或 `429 INSTITUTE_SYNC_COOLDOWN` 被拒絕時，前端不得重新載入 institute 列表。

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
  - `max_parallel_requests`：最大平行請求數限制；預設 `0`，表示不限制。
- 所有會寫入後端的 number 類型欄位僅允許 ASCII `0-9`；不可接受 `-`、`.`、`+`、`e/E`、空白、全形數字或混合字串。
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
- 前端所有使用者可見 datetime（如 `created_at`、`updated_at`、`issued_at` 與稽核 log 時間）需固定顯示為 `Asia/Taipei`；其中 API Key 清單與詳情中的 `expires_at` 僅顯示 `Asia/Taipei` 日期 `YYYY-MM-DD`；後端 API payload 與業務判定口徑仍維持 UTC。

### 7-1) 共用輸入驗證規則
- 範圍僅限「會寫入後端並持久化」的欄位；純查詢、篩選、搜尋欄位不適用此規則。
- persisted text fields 採「阻擋明顯程式片段」策略，不採極端字元白名單，以避免誤傷正常中英文內容。
- 前端需先提示/阻擋，後端需再次驗證；相同違規 payload 直接打 API 時一律回 `422 VALIDATION_ERROR`。
- persisted numeric fields 若為使用者可輸入值，前端需在輸入/貼上階段阻擋非 ASCII digits，送出前再驗證一次；後端不得接受非 digits payload。

### 7-2) Data Table Query Contract
- DataGrid 的 raw `filterModel`、`sortModel` 不得直接作為公開 API 契約；前端需先轉成受控 query 參數，再呼叫後端 API。
- 只要頁面採 `server-side table`，分頁、排序、欄位篩選、`total` 與頁數都必須由後端資料集計算；前端不得再對當前頁 rows 做 local filter。
- 只有 `local-full-dataset table` 可保留前端 local filtering/sorting/pagination；若未來改為後端分頁，需同步升級為 `server-side table` 並補齊 query contract。
- `server-side table` 的欄位若沒有對應後端 query contract，前端必須將該欄位標示為 `filterable: false` 或 `sortable: false`，不得留下會誤導使用者的 UI。
- 字串欄位 filter operator 僅允許白名單語意：
  - 識別/名稱類字串（如 `account`、`name`、`email`、`key_alias`、`target_id`、`error_code`）僅允許 `contains`，語意為 case-insensitive substring match。
  - 列舉欄位（如 `status`、`scope`、`result`、`provider`、`role`、`event_type`、`target_type`）僅允許 exact match。
  - 日期欄位僅允許區間查詢，使用 `from/to` 或 `<field>_from/<field>_to`；不得把 DataGrid 原生日期 operator 直接暴露成公開 API。
  - 數字/識別碼欄位（如 `sysid`）僅允許 exact match。
- 本 repo 現階段 Data Table 分類如下：
  - `server-side table`：`My API Keys Page`、`Whitelist Admin Page`、`Admin List Page`（管理者名單主表格）、`Admin Dashboard Page`、`Operation Audit Logs Page`（含 Scheduler Logs tab）、`Auth Audit Logs Page`、`System Announcements Page`
  - `local-full-dataset table`：`Admin List Page`（新增管理者查詢候選表格）、`Institute View Page`

## 功能需求
### Must Have（MVP）
- 權限模型僅區分 `user` 與 `admin`
- `whitelist` 僅影響登入/申請資格，不影響角色；若同一身份同時命中 `active whitelist` 與 `active admins`，有效角色仍為 `admin`
- 提供 OAuth/SSO 登入入口（`GET /main/login`、`GET /main/auth/callback`）並建立 session auth context
- 正式環境僅允許以 session auth context 驗證；header auth 僅限 `dev/test`
- 環境設定檔載入需支援 `ENV_FILE`（正式部署建議 `/home/app/config/.env`）；未設定時可回退 `backend/.env`
- frontend build 環境判定固定依序讀取 `/home/app/config/.env`、`backend/.env` 的 `APP_ENV`；當 `/home/app/config/.env` 存在且 `APP_ENV=prod` 時，正式 bundle 不得包含 `src/mocks` 或 `src/test` 模組
- 所有會變更資料的 API 皆需通過 CSRF 驗證
- 僅符合資格的人員可進入系統與申請 API Key（研究人員名單職稱代碼命中，或特殊人員名單 `active` 命中）
- 特殊人員名單管理能力（新增、查詢、停用/啟用）
- 系統公告能力（有效公告查詢、admin CRUD、公告區塊內的服務使用說明提示卡）
- 研究人員名單由外部服務提供並以職稱代碼判斷
- 本系統不同步維護本地研究人員名單；申請時以外部服務即時查詢為準
- 外部研究人員服務失敗（timeout/5xx）時：允許進入系統，但阻擋申請
- 申請成功時立即核發 API Key；provider timeout/5xx 時直接回傳 `503 PROVIDER_UNAVAILABLE`
- 需提供 API Key 到期前 `30|14|7|3|1` 天多段式提醒信機制，通知申請者本人可進行展延
  - 主旨固定為 `[AS-ITS] API Key 將於 {days_before} 天後到期 / API Key Expiration Notice ({days_before} Days Remaining)`，其中 `{days_before}` 僅允許 `30|14|7|3|1`
  - 信件需提供中文與英文雙語內容，並固定包含服務申請／展延網址 `https://api.ascs.sinica.edu.tw/main/`
  - 信件中的到期時間需顯示為 `Asia/Taipei` 對應的 `UTC+8` 在地時間；中文格式為 `YYYY 年 M 月 D 日 HH:MM（UTC+8）`，英文格式為 `Month D, YYYY, HH:MM (UTC+8)`
- API 生效時長固定天數選單（`30|180|360`）
- API Key 對外前綴依環境決定：`APP_ENV=prod` 為 `sk-` + 30 碼隨機字元，`dev/test` 為 `AS-` + 30 碼隨機字元（總長皆為 33）
- API Key 明文只顯示一次
- 系統儲存 `key_hash` 與加密密文（`key_ciphertext`），不直接儲存明文
- API Key lifecycle 採 `External SoT + Encrypted Local Secret`：`applications/create`、`renew`、`extend`、`revoke` 皆以 provider 結果為主，本地僅於 provider 成功後同步狀態
- `renew` 允許 `revoked|expired` key；`active` key 不可 renew
- `active` key 可隨時展延；`expired|revoked` key 不可展延
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
- 若目標 key 缺少 `key_ciphertext` 或 `key_kek_version`，或解密失敗，`extend`、`revoke` 必須立即失敗，不得呼叫 provider，也不得變更本地狀態；`renew` 不得依賴舊 key 明文或 `key_ciphertext`。
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
- `duration_days` (int, required, allowed: `30|180|360`)
- `original_duration_days` (int, required；保存原始申請時長，供 extend 基數計算使用)
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
- `application_date` 初次核發時為原始申請日期；每次 extend 成功後都需改寫為本次展延當日，作為新的起算日
- `duration_days` 為業務顯示欄位，不等同 provider `duration` 傳值；每次 extend 成功後一律重置為 `original_duration_days`，代表目前這一輪有效期時長
- `original_duration_days` 為內部計算欄位，需保存初次核發時的原始申請時長；後續 extend 不得改寫，供 fixed-day 展延推導使用
- `expires_at` 為目前有效到期時間；extend 時一律需先將 `application_date` 改寫為 `extend_action_date`，再以 `new_expires_at = application_date + original_duration_days` 重新計算
  - `is_proxy_submission = false` 時，`proxy_operator_account = NULL`
  - `is_proxy_submission = true` 時，`proxy_operator_account` 需記錄實際代送的 `admin account`
  - 完整操作者身份應透過 `operation_audit_logs` 取得，不重複存放於 application row

### Entity: `api_keys`
- `id` (string/uuid)
- `application_id` (fk -> api_key_applications.id)
- `key_hash` (string, required)
- `masked_key` (string, 遮罩格式依 `APP_ENV` 決定：`prod` 為 `sk-...` + 後 4 碼，`dev/test` 為 `AS-...` + 後 4 碼；response only)
- `key_alias` (string, nullable；顯示預設值為系統產生 alias，初始為 `for_{owner_account}`，必要時自動補 `_vN`，可由 admin 更新)
- `key_ciphertext` (string, encrypted at rest, nullable for legacy rows)
- `key_kek_version` (string, key-encryption-key version tag)
- `length` (int, MVP 固定 30，表示隨機段長度，不含 key prefix)
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

### Entity: `announcements`
- `id` (uuid/string, required)
- `title` (string, required)
- `body` (text/string, required)
- `status` (string, required；允許值 `active|inactive`)
- `publish_from` (datetime, nullable；開始對外顯示時間)
- `publish_to` (datetime, nullable；結束對外顯示時間)
- `created_by` (string, required；建立公告的 admin account)
- `updated_by` (string, required；最後更新公告的 admin account)
- `created_at` (datetime, required)
- `updated_at` (datetime, required)
- 規則：
  - `title`、`body` 套用 persisted-text 驗證
  - 若 `publish_from` 與 `publish_to` 同時存在，必須滿足 `publish_from <= publish_to`
  - `status=active` 且排程視窗命中時，該公告才可出現在一般前台公告區塊

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
- `error_detail` (string, nullable；僅供管理者除錯的安全摘要，僅允許白名單內容)
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
- `user_lookup` 類型事件中，`action` 需記錄查詢用途（`proxy_application|admin_create|whitelist_create`），`target_type` 固定為 `user_search`，`target_id` 記錄 trim 後查詢關鍵字。
- `error_detail` 僅允許例外類型、受控錯誤訊息摘要與必要業務上下文；不得包含 stack trace、SQL、完整第三方 payload。
- 不得記錄 API key 明文、token、password、client secret 等敏感憑證。

## 權限規則（MVP）
- `user`：可使用 `GET /main/api/v1/api-keys`、`GET /main/api/v1/api-keys/{id}`、`POST /main/api/v1/api-keys/{id}/revoke`、`POST /main/api/v1/api-keys/{id}/renew`、`POST /main/api/v1/api-keys/{id}/extend`，僅可操作本人 key。
- `user`：不可更新 `key_alias`。
- `admin`：可查詢全部 API Key 與申請紀錄，可管理特殊人員名單（沿用受保護路徑 `/main/api/v1/whitelists*`），可啟用/停用其他使用者管理者身分（沿用受保護路徑 `/main/api/v1/admins/{id}/enable|disable`）。
- `admin`：可使用 `PATCH /main/api/v1/api-keys/{id}` 更新 `key_alias`。
- `user` 與 `admin`：可使用 `GET /main/api/v1/announcements` 取得目前有效公告。
- `admin`：可使用 `POST`、`PATCH`、`DELETE /main/api/v1/announcements*` 管理公告。
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
    - 登入相關未預期錯誤不得直接回框架預設純文字 `Internal Server Error`；需提供可追蹤的 `request_id`
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
    - 若同一身份同時命中 `active whitelist(sysid)` 與 `active admins(id=sysid)`，登入資格仍視為通過；session 可先以 `role=user` 建立，但對外有效角色必須由 `active admins` 覆蓋為 `admin`
    - 若未通過登入資格檢查，回 `302` redirect `/main/login-denied?error=LOGIN_NOT_ELIGIBLE` 且不得建立 session
    - 前端在 `/main/login-denied` 需可直接顯示公開拒絕頁，不得發生自動導回 `/main/login` 的重導循環
    - 若登入流程發生未預期錯誤，需導向公開頁 `/main/login-error`，並以 query string 提供 `route`、`reason`、`request_id`，其中 `route` 至少可區分 `login`、`auth_callback`、`users_me`，`reason` 需為簡短可理解的失敗階段說明（例如 `eligibility_check_failed`）
    - 若缺少必要欄位（任一 `sysId`、`cn`、`chName`、`email`、`instCode`、`tCode`）需拒絕登入
    - 成功與失敗皆需寫入 `auth_audit_logs`
  - Response：
    - 成功回 `302` redirect `/`
    - `401`：`OAUTH_TOKEN_EXCHANGE_FAILED`、`OAUTH_BASIC_FETCH_FAILED`
    - `422`：`OAUTH_CODE_MISSING`、`OAUTH_IDENTITY_INVALID`
    - 非預期 `500` 需提供結構化錯誤內容或 redirect 至 `/main/login-error`，不得只回傳純文字 `Internal Server Error`
- `GET /main/api/v1/users/me`
  - 用途：回傳目前 session 使用者資訊與 CSRF token。
  - 規則：
    - 回傳欄位：`account`、`name`、`email`、`department`、`sysid`、`role`、`csrf_token`
    - 若目前帳號命中 `active admins`，`role` 需回傳 `admin`
    - 若目前帳號同時命中 `active whitelist` 與 `active admins`，`role` 仍需回傳 `admin`
    - 可在 `dev/test` 透過 header auth bootstrap session

### 1) 申請並核發 API Key
- `POST /main/api/v1/api-keys/applications`
- 前置條件：
  - 請求必須為已登入使用者（`account`、`name`、`email`、`department`、`sysid` 由 auth context 提供，並以 auth context 為準）
  - 正式上線閘門：`user` 在 `2026-06-30 00:00 Asia/Taipei` 前送出申請時，必須回 `403 APPLICATION_NOT_LIVE`；`admin` 不受此限制
  - auth context 缺少任一必要欄位（`account`、`name`、`email`、`department`、`sysid`）時，回傳 `422 VALIDATION_ERROR`，且錯誤訊息需指出缺少欄位
  - `sysid` 必須為純數字且為正整數；若不合法，回傳 `422 VALIDATION_ERROR`，且錯誤訊息需指出格式問題
  - `user` 僅能以 auth context 申請本人；`admin` 可選擇代他人申請（透過 `target_identity`）
  - 申請資格必須通過：依序命中 `active whitelist(sysid)`、`active admins(id=sysid)`，或 `tCode` 命中 `LOGIN_ALLOWED_TITLE_CODES`
  - `admin` 代申請時，後端需先依 `target_identity.account` 查人員目錄取得唯一身份，再以該身份的 `account(cn)` 查詢 `tCode` 檢查申請資格
  - 若需查詢 `tCode` 且 Persnl SOAP 服務連線逾時或 5xx，本 API 回傳 `503 SOAP_SERVICE_UNAVAILABLE`，不得建立申請資料
  - `purpose` 經 `trim()` 後不得為空字串；若為空字串或全空白，回傳 `422 VALIDATION_ERROR`
  - `purpose` 與 `target_identity.account` 需通過 persisted-text 驗證；若包含明顯程式語法片段，回傳 `422 VALIDATION_ERROR`
- Request：
```json
{
  "application_date": "2026-05-04",
  "duration_days": 180,
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
  "api_key_plaintext": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}
```
- Response（503，provider timeout/5xx）：
```json
{
  "error": {
    "code": "PROVIDER_UNAVAILABLE",
    "message": "provider unavailable",
    "details": "app.api.v1.api_keys:create_application"
  }
}
```
- Response（403，尚未正式上線）：
```json
{
  "error": {
    "code": "APPLICATION_NOT_LIVE",
    "message": "application is not live yet",
    "details": "app.api.v1.api_keys:create_application"
  },
  "go_live_at": "2026-06-30T00:00:00+08:00"
}
```
- 未上線閘門命中時，不得建立 `api_key_applications`、不得建立 `api_keys`、不得呼叫 provider。
- Outbound（系統呼叫 provider `POST {PROVIDER_BASE_URL}/key/generate`）：
```json
{
  "rpm_limit": 500,
  "tpm_limit": 10000,
  "max_parallel_requests": 0,
  "max_budget": 1000.0,
  "budget_duration": "30d",
  "duration": "180d",
  "team_id": "team-001",
  "key_alias": "for_jane.doe",
  "key_type": "llm_api"
}
```
  - auth header 固定為 `Authorization: Bearer {PROVIDER_MASTER_KEY}`；沿用既有 `PROVIDER_MASTER_KEY` 作為 Bearer token 值
  - external provider mode 下 `PROVIDER_TEAM_ID` 為必要設定；若缺少此設定，建立與 renew 必須 fail fast，且不得呼叫 provider
  - `budget_duration` 由系統設定映射：`daily->1d`、`weekly->7d`、`monthly->30d`
  - `duration` 由 `duration_days` 映射：`30->30d`、`180->180d`、`360->360d`
  - 本地 `expires_at` 也需沿用同一 fixed-day 規則，不得再使用曆月位移算法
  - 若全域設定中的 `tpm_limit` 或 `rpm_limit` 為 `0`，送往 provider 時需轉為 `null`，表示不限制
  - `max_parallel_requests` 預設為 `0`，表示不限制；本地設定維持 `0`，送往 provider 時需轉為 `null`
  - `team_id` 固定使用 `PROVIDER_TEAM_ID`
  - `key_alias` 預設先送 `for_{owner_account}`；若 provider 回 `400`，系統需自動依序重試 `for_{owner_account}_v2`、`_v3` ...，成功後將最終 alias 寫回本地 `api_keys.key_alias`
  - 目前不送 `budget_limits`
  - 僅送上述新欄位；不再送舊欄位（例如 `account`、`application_id`、`duration_days`、`purpose`、`limit_strategy`）
  - provider 成功回應需自 `response.key` 讀取新明文 secret；不得假設回傳欄位為 `api_key_plaintext`

### 1-1) 全域金鑰條件設定（Admin only）
- `GET /main/api/v1/limit-strategy-config`
- `PATCH /main/api/v1/limit-strategy-config`
- 全域固定單一金鑰條件組合（皆可編輯）：
  - `budget`（額度）：`max_budget`、`budget_duration`
  - `rate_limit`（速度）：`tpm_limit`、`rpm_limit`
  - `concurrency`（平行請求數）：`max_parallel_requests`
- 欄位語意同金鑰條件模板：
  - `max_budget`：總金額額度（USD）。
  - `budget_duration`：重置週期（`daily|weekly|monthly`）。
  - `tpm_limit`：每分鐘 Token 數限制；允許 `0`，表示送往 provider 時轉為 `null`（不限制）。
  - `rpm_limit`：每分鐘請求數限制；允許 `0`，表示送往 provider 時轉為 `null`（不限制）。
  - `max_parallel_requests`：最大平行請求數限制；允許 `0`，表示不限制，本地設定維持 `0`，送往 provider 時轉為 `null`。
- 每把 API Key 需同時套用 `budget`、`rate_limit` 與 `max_parallel_requests` 設定；不提供二選一模式。
- 一般使用者不可查看或修改金鑰條件設定。
- 系統需透過 migration 預先補齊 `global-limit-strategy-config` 預設資料列（`1000/monthly/10000/500/0`）。
- `GET /main/api/v1/limit-strategy-config` 在資料缺漏時仍需回傳相同預設值，作為相容性保險。
- `PATCH /main/api/v1/limit-strategy-config` 需採 upsert：若設定不存在則建立，存在則更新。
- `PATCH /main/api/v1/limit-strategy-config` 成功時，需同步呼叫 provider `POST {PROVIDER_BASE_URL}/team/key/bulk_update`，request body 固定為：
```json
{
  "team_id": "team-001",
  "all_keys_in_team": true,
  "update_fields": {
    "max_budget": 3000.0,
    "budget_duration": "7d",
    "tpm_limit": 13000,
    "rpm_limit": 700,
    "max_parallel_requests": null
  }
}
```
- `PATCH /main/api/v1/limit-strategy-config` 在 provider `bulk_update` 成功後，需立即回讀 provider `/spend/keys` 驗證目前 `active` keys 的 `budget_duration` 已與本地新設定一致；若回讀失敗、資料無法辨識、缺少對應 key，或任一 key 的 `budget_duration` 仍不一致，整次更新需視為失敗並回傳錯誤，不得只更新本地設定後靜默放行。
- `PATCH /main/api/v1/limit-strategy-config` 在 session auth 模式下，若 `X-CSRF-Token` 缺失或不正確需回 `403 FORBIDDEN`。
- `PATCH /main/api/v1/limit-strategy-config` 的 `budget_max_budget`、`rate_limit_tpm`、`rate_limit_rpm`、`max_parallel_requests` 僅接受 ASCII `0-9`；若為空字串、科學記號、小數、負號、全形數字、空白或混合字串，回 `422 VALIDATION_ERROR`。
- 同步 `/team/key/bulk_update` 時，external provider mode 下缺少 `PROVIDER_TEAM_ID` 必須 fail fast，且不得送 request 給 provider。

### 2) 查詢 API Key 清單
- `GET /main/api/v1/api-keys`
- 規則：`user` 僅回傳 auth 使用者本人的資料；`admin` 可查全部資料。
- 查詢模式：此端點為 `server-side table` contract，前端欄位排序、分頁與篩選都必須由此端點對完整資料集處理。
- 到期口徑：`expires_at` 早於查詢當下（UTC）且原始狀態為 `active` 時，API 對外狀態需視為 `expired`（即使 DB 原始欄位尚未同步更新）。
- Usage summary 需使用本地週期性同步/快取資料；此列表端點不得對每列即時呼叫外部 provider 取 usage。
- usage 歷史資料需落地保存於獨立表 `api_key_usage_snapshots`，作為 `/usage` 與 `GET /main/api/v1/api-keys/usage-series` 的每日聚合歷史來源。
- `api_key_usage_snapshots` 最少需保存：`api_key_id`、`bucket_granularity`、`bucket_start_utc`、`bucket_end_utc`、`spend`、`prompt_tokens`、`completion_tokens`、`total_tokens`、`budget_reset_at`、`synced_at`。
- `api_key_usage_snapshots` 第一版固定只寫入 `bucket_granularity=day` 的資料，且需以 `(api_key_id, bucket_granularity, bucket_start_utc)` 維持唯一性。
- 既有 `api_keys.usage_*` 欄位保留作為最新快取鏡像，持續提供 `GET /main/api/v1/api-keys` 的 `usage_summary`；歷史圖表不得直接讀 `api_keys.usage_*`。
- usage summary 與 token history 為雙來源：
  - provider `/spend/keys` 提供 current-cycle summary 欄位：`spend`、`budget_duration`、`budget_reset_at`，以及同步時間來源 `updated_at`
  - provider `/spend/logs/v2` 提供逐筆 usage logs，作為 `prompt_tokens`、`completion_tokens`、`total_tokens` 與 daily history buckets 的來源
- usage log 同步查詢鍵優先使用本地 `key_hash` 對應 provider log 的 `api_key`；若未來 provider 相容性需要，可退回 `key_alias`。
- usage 同步時僅累計 provider spend logs 中 `status=success` 的紀錄；`failure` 紀錄不得計入 token totals，也不得用於覆寫 current-cycle token 快取。
- usage 同步排程預設每 `5` 分鐘執行一次，僅同步目前 `active` keys；若 provider 查詢失敗，不得中斷其他 keys 的同步。
- 讀取欄位語意：
- 對曾 extend 的 key：`application_date` 需改為最近一次成功展延當日；`duration_days` 需重置為 `original_duration_days`，代表目前這一輪有效期時長；`expires_at` 為重新起算後的目前有效到期時間。
- Query：`page`, `page_size`, `status`, `owner_account`, `owner_name`, `key_alias`, `application_date_from`, `application_date_to`, `issued_at_from`, `issued_at_to`, `expires_from`, `expires_to`, `sort_by`, `sort_dir`
  - `page_size` 定義為每頁顯示筆數（非全量上限）。
  - `status` 為 exact match，allowed: `active|revoked|expired`
  - `/api-keys` 頁前端首次載入時，狀態篩選欄位預設為 `active`，因此初始查詢預設僅顯示啟用中 API Keys；使用者仍可切換為 `revoked`、`expired` 或清空成全部狀態。
  - `owner_account`、`owner_name`、`key_alias` 為 case-insensitive `contains` 語意；`owner_*` 僅 `admin` 可跨人查詢，`user` 不得用於越權查詢
  - `application_date_from`、`application_date_to` 格式為 `YYYY-MM-DD`，基準欄位為 `application_date`
  - `issued_at_from`、`issued_at_to` 格式為 UTC `date-time`（RFC 3339），基準欄位為 `issued_at`
  - `expires_from`、`expires_to` 格式為 UTC `date-time`（RFC 3339），基準欄位為 `expires_at`
  - `sort_by` 僅允許既定欄位白名單；`sort_dir` 僅允許 `asc|desc`
  - 前端清單需採伺服器分頁，透過 `page/page_size` 可翻頁讀取完整資料集（不限於首 20 筆）。
- Response（200）：
```json
{
  "items": [
    {
      "id": "...",
      "status": "active",
      "masked_key": "sk-...wxyz",
      "key_alias": "for_jane.doe_v2",
      "owner_account": "jane.doe",
      "owner_name": "Jane Doe",
      "expires_at": "...",
      "usage_summary": {
        "spend": 200.0,
        "prompt_tokens": 1200,
        "completion_tokens": 300,
        "total_tokens": 1500,
        "max_budget": 1000.0,
        "remaining_budget": 800.0,
        "tpm_limit": 10000,
        "rpm_limit": 500,
        "max_parallel_requests": 8,
        "budget_reset_at": "...",
        "synced_at": "..."
      }
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```
- `usage_summary` 欄位語意：
  - `spend`：目前 budget cycle 的累計已花費金額（USD）；後端需先依 `usage_summary.budget_reset_at` 與目前生效的 `budget_duration` 推回 current-cycle window，再只加總本地 `api_key_usage_snapshots` 中落在該 window 的 daily buckets；未知時為 `null`
  - `prompt_tokens`、`completion_tokens`、`total_tokens`：目前 budget cycle 的 token totals；需與 `spend` 使用相同 current-cycle window 與相同本地 daily bucket 聚合口徑；未知時為 `null`
  - `max_budget`：目前金鑰管理（limit strategy config）的總額度（USD）；`0` 表示 unlimited；未知時為 `null`
  - `remaining_budget`：由後端以 current-cycle `spend` 計算 `max(max_budget - spend, 0)`；`0` 可表示 exhausted，也可在 `max_budget=0` 時表示 unlimited；未知時為 `null`
  - `tpm_limit`、`rpm_limit`：目前金鑰管理（limit strategy config）的速率限制設定值；`0` 表示 unlimited；未知時為 `null`
  - `max_parallel_requests`：目前金鑰管理（limit strategy config）的最大平行請求數設定值；`0` 表示 unlimited；未知時為 `null`
  - `budget_reset_at`：下次額度重置時間，直接使用 provider `/spend/keys` 回傳或同步鏡像值；若 provider 未提供則為 `null`
  - `synced_at`：本地 summary mirror 最後同步時間；優先使用 provider `/spend/keys.updated_at`，若 provider 未提供則以本次同步執行時間為準；未知時為 `null`
- `total` 定義為符合目前篩選條件的總筆數（非當頁 `items` 長度）。

### 2-1) 查詢 API Key 使用量時序
- `GET /main/api/v1/api-keys/usage-series`
- 規則：`user` 僅可查本人 key；`admin` 可查任意 key；不得回傳明文 key。
- Query：`key_id`, `granularity`, `from`, `to`
  - `key_id` 必填。
  - `granularity` 必填，第一版僅允許 `day`。
  - `from`、`to` 必填，格式為 `YYYY-MM-DD`，代表 `Asia/Taipei` 日曆日區間。
  - `from` 不得晚於 `to`；若參數格式錯誤、缺值、granularity 不合法，回傳 `422 VALIDATION_ERROR`。
- 時間語意：
  - DB bucket 一律以 UTC 欄位 `bucket_start_utc`、`bucket_end_utc` 儲存。
  - 查詢區間與畫面日期標籤一律以 `Asia/Taipei` 的日曆日解讀。
  - 後端需正確處理 Taipei 日期跨 UTC 換日的情況，不得因 UTC 分界將同一 Taipei 日拆成兩天。
- Response（200）：
```json
{
  "key_id": "...",
  "granularity": "day",
  "from": "2026-06-01",
  "to": "2026-06-30",
  "items": [
    {
      "bucket_start": "2026-06-01T00:00:00+08:00",
      "bucket_label": "2026-06-01",
      "prompt_tokens": 1000,
      "completion_tokens": 500,
      "total_tokens": 1500,
      "spend": 1.25
    }
  ]
}
```
- `items` 僅回傳實際有資料的 bucket；若查詢區間無資料，回傳空陣列，不以前端或後端補零。
- 錯誤回應：
  - `403 FORBIDDEN` / `KEY_NOT_OWNED_BY_USER`：使用者不可查他人 key
  - `404 VALIDATION_ERROR`：key 不存在
  - `422 VALIDATION_ERROR`：查詢參數不合法

### 2-1-1) 查詢全部可見 API Keys 歷史累計使用量
- `GET /main/api/v1/api-keys/usage-total`
- 規則：`user` 僅可聚合本人全部 keys；`admin` 可聚合全部可見 keys；不得回傳明文 key。
- Query：第一版不提供日期區間或粒度查詢參數。
- 聚合來源：僅使用本地 `api_key_usage_snapshots` 的歷史 bucket；不得即時呼叫 provider。
- 聚合口徑：加總全部可見 keys 的全部歷史 bucket，回傳累計 `prompt_tokens`、`completion_tokens`、`total_tokens`。
- 第一版回應不需回傳 daily buckets，也不需同時回傳 current-cycle summary。
- Response（200）：
```json
{
  "scope": "all_visible_keys",
  "prompt_tokens": 1000,
  "completion_tokens": 500,
  "total_tokens": 1500,
  "key_count": 3
}
```
- `key_count` 定義為本次聚合範圍內可見 API Key 總數；沒有歷史 usage bucket 的 key 仍需計入 `key_count`，但 token totals 貢獻為 `0`。

### 2-2) 查詢每位使用者 API Key 申請統計（Admin Dashboard）
- `GET /main/api/v1/api-keys/statistics/users`
- 規則：僅 `admin` 可使用；回傳為申請人維度聚合結果，不得包含明文 key。
- 查詢模式：此端點為 `server-side table` contract；表格分頁、排序、欄位篩選與圖表口徑都必須以此端點回傳為準。
- 統計口徑：`active/revoked/expired` 與 `scope` 篩選需採相同到期口徑（`expires_at` 已過且原始 `active` 視為 `expired`）。
- Query：`page`, `page_size`, `q`, `scope`, `from`, `to`, `owner_account`, `owner_name`, `owner_email`, `owner_department`, `sort_by`, `sort_dir`
  - `scope` allowed: `all|active|revoked|expired`（預設 `all`）
  - `q` 為全域搜尋，僅比對 `account`、`name`、`email`
  - `owner_account`、`owner_name`、`owner_email`、`owner_department` 為欄位級 case-insensitive `contains` 篩選；其語意獨立於 `q`
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
- 讀取欄位語意：
- 對曾 extend 的 key：`application_date` 需改為最近一次成功展延當日；`duration_days` 需重置為 `original_duration_days`，代表目前這一輪有效期時長；`expires_at` 為重新起算後的目前有效到期時間。
- 回傳 `key_alias`；若資料未設定則回傳系統產生 alias（初始為 `for_{owner_account}`，若 provider 衝突則可能為 `for_{owner_account}_vN`）。
- 回傳可包含申請人識別欄位 `owner_account`、`owner_name`（供管理者辨識申請來源）。
- 回傳應包含 `purpose` 供詳情頁顯示；若歷史資料未留存用途，前端顯示 `-`。
- 回傳應包含 `department` 供詳情頁顯示；若歷史資料未留存單位，前端顯示 `-`。
- frontend detail 顯示需直接沿用上述語意，不得將 `duration_days` 解讀為其他輪次或累加時長。
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

### 3-2) 背景同步（API Key Usage Snapshot）
- 目的：週期性自 provider `/spend/keys` 與 `/spend/logs/v2` 同步每把 `active` API Key 的最新 usage 快取與每日 bucket 歷史，供列表 `Usage` 與 `/usage` 圖表共同使用。
- summary metadata 來源：`/spend/keys` 提供 `spend`、`budget_duration`、`budget_reset_at` 與 `updated_at`；其中 `budget_reset_at` 為 current-cycle reset boundary 的來源。`budget_duration` 僅作為 provider 同步一致性觀測用途，不作為本地 current-cycle window 計算依據。
- history 來源：`/spend/logs/v2` 提供最近 `30` 天逐筆 usage logs，作為 daily bucket 歷史來源；列表 `usage_summary` 的 `spend` 與 token totals 皆需以本地 daily buckets 聚合產生，不得直接顯示舊 cache。
- 查詢鍵：
  - `/spend/keys` 以 provider 回傳的 `token` 與本地 `key_hash` 優先對應；若對應失敗，再以 `key_alias` 補充比對。
  - `/spend/logs/v2` 以本地 `key_hash` 對應 provider query `api_key`；若未來 provider 相容性需要，可退回 `key_alias`。
- 查詢時間窗：每次同步需抓取最近 `30` 天的 rolling window，並需對 provider 一併帶 `start_date`、`end_date`；格式固定為 `YYYY-MM-DD HH:MM:SS`。
- 聚合規則：只累計 `status=success` 的 spend logs；需先依 `Asia/Taipei` 日曆日聚合後，再寫入對應的 daily bucket。`failure` logs 僅供維運排查，不得寫入 usage snapshot。
- token 聚合規則：`prompt_tokens`、`completion_tokens`、`total_tokens` 皆只累計 `status=success` 的 spend logs；若單筆 log 缺少個別 token 欄位，該欄位以 `0` 累計，不得因缺欄中止整把 key 的 snapshot 寫入。
- 落地規則：每次同步需對 rolling window 內各日 bucket 做 upsert；同一天 bucket 允許後續同步覆寫更新，不得重複插入相同 `(api_key_id, bucket_granularity, bucket_start_utc)`。
- 最新快取規則：同步完成後，可同步覆寫 `api_keys.usage_*` 作為 mirror / 維運快取；但 `GET /main/api/v1/api-keys` 對外回傳 `usage_summary` 時，不得直接把 `api_keys.usage_spend` 或其他 `usage_*` 快取值當作最終 truth source。
- 歷史值規則：`GET /main/api/v1/api-keys/usage-series` 一律讀取 `api_key_usage_snapshots` 的 daily bucket 歷史；`GET /main/api/v1/api-keys` 需以 `usage_budget_reset_at` + 目前 `limit_strategy_config.budget_duration` 推回 current-cycle window，再對 `api_key_usage_snapshots` 的 daily buckets 聚合後組成 `usage_summary`。
- current-cycle token cache 規則：usage sync 腳本在覆寫 `api_keys.usage_prompt_tokens`、`usage_completion_tokens`、`usage_total_tokens` 時，也需以本地 `limit_strategy_config.budget_duration` 搭配 provider `budget_reset_at` 判定 current-cycle window，不得改用 provider summary 內的 `budget_duration` 單獨決定週期。
- 額度重置規則：`budget_reset_at` 一律以 provider `/spend/keys` 回傳值為準，語意固定為「下一次重置時間」；若 provider 未提供則為 `null`，本系統不得再自行推算。
- 執行方式：由排程觸發腳本（如 systemd timer 或 cron）；預設每 `5` 分鐘執行一次。
- 全量遍歷規則：每次執行需遍歷全部 `active` keys；腳本參數 `batch_size` 僅代表單次 DB 候選批次大小與 provider 分頁預期大小，不得把 `batch_size` 視為整次同步只處理前 N 把 key 的上限。
- 正式上線篩選規則：同步候選 key 僅包含 `issued_at >= 2026-06-30 00:00:00 Asia/Taipei`（`2026-06-29T16:00:00Z`）的 `active` keys；正式上線前核發的 key 不再呼叫 provider `/spend/keys` summary 對應或 `/spend/logs/v2` history 查詢。
- 修復模式：腳本需支援維運修復模式，用於補齊 `api_keys.usage_*` current-cycle cache 缺失的 `active` keys。修復模式仍需以 provider `/spend/keys` + `/spend/logs/v2` 為資料來源，不得直接以 `api_key_usage_snapshots` daily bucket 反推摘要。
- 容錯：
  - `/spend/keys` summary sync 失敗時，需記錄 `summary_sync_failed` 類型訊息，但不得中斷 `/spend/logs/v2` history sync。
  - 單把 key `/spend/logs/v2` provider 查詢失敗時，需記錄 `history_sync_failed` 或對應錯誤並繼續同步其他 keys。
  - provider `/spend/logs/v2` 回傳的 `total`、`page`、`page_size`、`total_pages` 需納入同步完整性檢查；若單頁 metadata 與 request 或實際 records 明顯不一致，該 key 本次回應視為不可信，需記 warning 並跳過該 key，不得覆蓋其既有 daily bucket 與最新快取鏡像。
  - daily bucket 歷史仍維持以 `Asia/Taipei` 日曆日聚合；即使 budget reset 發生在同一天中途，`/usage-series` 的單日 bucket 仍保留完整日曆日成功 usage，不得切分成半天 bucket。
  - 列表 `usage_summary` 的 current-cycle aggregate 需以 `/spend/keys.budget_reset_at` 作為下一次 reset boundary，並以目前生效的 `limit_strategy_config.budget_duration` 回推 cycle start；之後只加總本地 `api_key_usage_snapshots` 中落在該 window 的 daily buckets。
  - 因本地歷史第一版僅保存 `bucket_granularity=day`，當 current-cycle window 與 Taipei 日曆日 bucket 發生部分重疊時，列表摘要可按 bucket overlap 納入該日 bucket；但不得把 window 之外、完全不相交的 bucket 算入。
  - 若某把 key 在目前 cycle 內查無符合 window 的 daily buckets，但已知有效 `budget_reset_at` 與 `budget_duration`，列表 `usage_summary` 需顯示 `spend=0` 與 token totals `0`，不得沿用舊 cache；既有 daily bucket 不需補造假資料。
  - 若 provider 缺少 `budget_reset_at` 或目前 `budget_duration` 不可判定、致使 current cycle 無法判定，列表 `usage_summary` 的 `spend`、`prompt_tokens`、`completion_tokens`、`total_tokens`、`remaining_budget` 需回 `null`，並保留 `budget_reset_at` / `synced_at` metadata 供前端顯示。
  - provider timeout、5xx、payload 無法辨識時，不得覆蓋該 key 既有成功 daily bucket 或最新快取鏡像。
  - 非 `active` key 不再同步新的 usage bucket，但既有歷史資料需保留供查詢。
- 稽核與維運：排程需輸出執行時間、候選 key 數、實際處理 key 數、history 寫入筆數、summary cache 寫入/跳過 key 數、token cache 寫入/跳過 key 數與錯誤訊息，供維運追蹤。

### 4) 停用 API Key
- `POST /main/api/v1/api-keys/{id}/revoke`
- 規則：
  - `user` 僅可停用本人 `active` key；`admin` 可停用任意 `active` key。
  - revoke 對應 provider `delete`；前端不得提供舊明文 key，後端需從 `key_ciphertext` 解密後直接呼叫 provider。
  - 呼叫 provider `delete` 時，request body 需以 `keys` 陣列傳送舊明文 key；單筆 revoke 也需包成單元素陣列。
  - provider `delete` 成功後，才可將本地 `api_keys.status` 與對應 `api_key_applications.status` 同步為 `revoked`。
  - provider timeout / 5xx / 明確拒絕、缺少密文、或解密失敗時，本地不得先標記為 `revoked`。

### 4-2) 續發（Renew）API Key
- `POST /main/api/v1/api-keys/{id}/renew`
- 規則：
  - `user` 僅可續發本人 `revoked|expired` key；`admin` 可續發任意 `revoked|expired` key。
  - renew 對應 provider `generate`；前端不得提供舊明文 key，後端也不得依賴來源 key 的 `key_ciphertext` 或舊 key 明文。
  - 呼叫 provider `generate` 時，request body 沿用 applications create 的 `generate` wire format，且必須包含 `team_id`；payload 不得包含 `key`。
  - renew 送往 provider 的 `key_alias` 需優先沿用目前 key alias；若 provider 回 `400`，系統需自動補 `_vN` 後重試，成功後將最終 alias 寫入新 key。
  - renew 會在 provider 成功後建立新 key（`status=active`），不是把舊 key 改回 `active`。
  - 新 key 的 `duration_days` 與 `purpose` 需沿用來源 key 的原資料。
  - provider 成功但本地同步失敗時，需保留可追蹤資訊並支援 retry / reconciliation，避免 provider 與本地資料不一致。
- renew 成功時，回傳一次性 `api_key_plaintext`。
  - renew 的新明文需自 provider response `key` 讀取。
  - 續發成功後，來源 key 對 `user` 列表需隱藏；`admin` 列表仍需可見完整歷史。

### 4-3) 展延（Extend）API Key
- `POST /main/api/v1/api-keys/{id}/extend`
- Request：
```json
{}
```
- 規則：
  - `user` 僅可展延本人 `active` key；`admin` 可展延任意 `active` key。
  - extend request 不再接收 `duration_days`；每次 extend 一律沿用該 key 初次核發時保存的 `original_duration_days` 作為本次展延時長。
  - extend 成功後，讀取 API 的 `application_date` 需改為本次展延當日；`duration_days` 一律設為 `original_duration_days`，代表目前這一輪有效期時長。
  - 展延判定口徑需與查詢一致：`expires_at` 已過且原始狀態為 `active` 時，需視為 `expired`，並以 `KEY_NOT_EXTENDABLE` 拒絕展延。
  - extend 對應 provider `update`；前端不得提供舊明文 key，後端需從 `key_ciphertext` 解密後直接呼叫 provider。
  - 呼叫 provider `update` 時，request body 需以 `key` 欄位傳送舊明文 key，其餘限制欄位沿用 `generate` wire format；`duration` 一律直接送 `original_duration_days` 對應的 `30d|180d|360d`，不得再依 `api_keys.created_at` 累算總天數。
  - extend 送往 provider 的 `key_alias` 需優先沿用目前 key alias；若 provider 回 `400`，系統需自動補 `_vN` 後重試，成功後將最終 alias 寫回原 key。
  - extend 會在 provider 成功後沿用原 key，更新同一筆 key 的有效期限與狀態（必要時轉為 `active`）；新的 `expires_at` 一律以本次展延當日重新起算：`new_expires_at = application_date + original_duration_days`，不得累加先前展延時長，也不得使用剩餘天數補差。
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
- 規則：僅 `admin` 可使用；`key_alias` 不可為空字串；僅允許中英文、數字、`_`、`-`、`、`；若與其他 key alias 重複需回傳 `409 KEY_ALIAS_DUPLICATE`；external provider mode 下需先同步 provider `update` 成功後才可提交本地更新，成功後回傳更新後單筆資料。
- `key_alias` 需通過 persisted-text 驗證；若包含明顯程式語法片段或 `_`、`-`、`、` 以外特殊符號，回傳 `422 VALIDATION_ERROR`。

### 4-1) 受控回取 API Key 明文（Reveal）
- `POST /main/api/v1/api-keys/{id}/reveal`
- 規則：僅 `admin` 可使用；此端點為受控 break-glass 流程，不屬一般列表/詳情查詢。
- 規則：不得作為一般 `renew`、`extend`、`revoke` 流程依賴。
- 規則：回應需帶 `Cache-Control: no-store`。
- Response（200）：
```json
{
  "id": "...",
  "api_key_plaintext": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "key_kek_version": "v1"
}
```

### 5) 特殊人員名單管理 API（沿用受保護路徑）
- `POST /main/api/v1/whitelists`：新增特殊人員名單（需帶 `sysid`、`account`、`name`、`email`）
- `GET /main/api/v1/whitelists`：查詢特殊人員名單列表，需支援 `page`、`page_size`、`status`、`sysid`、`account`、`name`、`email`、`created_from`、`created_to`、`updated_from`、`updated_to`、`sort_by`、`sort_dir`
- `PATCH /main/api/v1/whitelists/{id}`：更新狀態（`active/inactive`）與備註
- `DELETE /main/api/v1/whitelists/{id}`：刪除特殊人員名單條目（實體刪除）
- 規則：僅 `admin` 可使用。
- `POST /main/api/v1/whitelists`、`PATCH /main/api/v1/whitelists/{id}`、`DELETE /main/api/v1/whitelists/{id}` 在 session auth 模式下，若 `X-CSRF-Token` 缺失或不正確需回 `403 FORBIDDEN`。
- `POST /main/api/v1/whitelists` 若 `sysid` 重複需回 `409 WHITELIST_SYSID_DUPLICATED`。
- 回傳欄位至少包含：`id`、`sysid`、`account`、`name`、`email`、`status`、`note`、`created_at`、`updated_at`。
- `note` 若存在，需通過 persisted-text 驗證；僅允許中英文、數字、空白、`_`、`-`、`、`，正常中英文混合內容需可成功儲存。

### 5-1) 特殊人員名單新增前使用者查詢 API
- `GET /main/api/v1/users?q={keyword}`
- 用途：供管理者透過 Persnl SOAP 查詢候選人資料（供新增管理者/特殊人員前使用）。
- 規則：
  - 僅 `admin` 可使用。
  - `q` 為必填，且僅用於 `account`、`name` 查詢。
  - `lookup_context` 為必填，且僅允許 `proxy_application`、`admin_create`、`whitelist_create`，用於稽核查詢用途。
  - `q` 未提供、空字串或空白字串時，回傳 `422 VALIDATION_ERROR`。
  - 不論 `q` 值內容為何，資料來源皆為 Persnl SOAP（`PERSNL_SOAP_URL`）。
  - 回傳欄位至少包含 `id`、`sysid`、`account`、`name`、`email`、`department`（對應單位代碼 `instCode`）、`status`。
  - 成功與失敗皆需寫入 `operation_audit_logs`；`event_type=user_lookup`、`action=lookup_context`、`target_type=user_search`、`target_id` 為 trim 後查詢關鍵字。
- 單位主檔同步：`Persnl.getInstitutes` 供背景同步作業與受控手動同步使用；除 `POST /main/api/v1/institutes/sync` 與既定背景同步流程外，不得在其他查詢 API 請求路徑中即時呼叫。
- 錯誤回應：
  - `403 FORBIDDEN`：非 `admin`
  - `422 VALIDATION_ERROR`：`q` 不合法
  - `422 VALIDATION_ERROR`：`lookup_context` 不合法
  - `503 SOAP_SERVICE_UNAVAILABLE`：Persnl SOAP timeout/5xx

### 5-4) 管理者名單查詢 API
- `GET /main/api/v1/admins`
- 用途：供管理者查看管理者名單（來源 `admins`）。
- 規則：
  - 僅 `admin` 可使用。
  - 資料來源為本地 DB `admins`（含 `active`、`inactive`）。
  - 不得在此 API 路徑呼叫 Persnl SOAP。
- 需支援 `page`、`page_size`、`status`、`sysid`、`account`、`name`、`email`、`created_from`、`created_to`、`updated_from`、`updated_to`、`sort_by`、`sort_dir`。
- `status`、`sysid` 為 exact match；`account`、`name`、`email` 為 case-insensitive `contains`；時間欄位為區間查詢。
- 回傳欄位至少包含 `id`、`sysid`、`account`、`name`、`email`、`department`、`status`、`created_at`、`updated_at`。

### 5-2) 目前使用者語言偏好 API
- `GET /main/api/v1/users/preferences/locale`
  - 回傳格式：`{ "preferred_locale": "zh-TW" | "en" | null }`
- `PATCH /main/api/v1/users/preferences/locale`
  - Request body：`{ "preferred_locale": "zh-TW" | "en" }`
  - 僅允許 `zh-TW|en`，其餘值回傳 `422 VALIDATION_ERROR`

### 5-5) System Announcements API
- `GET /main/api/v1/announcements`
- 用途：提供登入後共用版型與公告管理頁查詢公告。
- 規則：
  - `user` 與 `admin` 都可使用。
  - 預設回目前有效公告。
  - 成功回應為分頁結構 `{ items, page, page_size, total }`。
  - `admin` 可透過 `scope=all` 取得全部公告；非 `admin` 傳 `scope=all` 需回 `403 FORBIDDEN`。
  - 第一版需支援 `page`、`page_size`、`scope`、`status`、`title`、`publish_from_from`、`publish_from_to`、`publish_to_from`、`publish_to_to`、`updated_from`、`updated_to`、`sort_by`、`sort_dir`。
  - `title` 為 case-insensitive `contains`；`status` 為 exact match；日期欄位為區間查詢。
  - 回傳欄位至少包含 `id`、`title`、`body`、`status`、`publish_from`、`publish_to`、`created_at`、`updated_at`。
- `POST /main/api/v1/announcements`
- `PATCH /main/api/v1/announcements/{id}`
- `DELETE /main/api/v1/announcements/{id}`
- 規則：
  - 僅 `admin` 可使用，且需記錄操作稽核資訊（操作者、時間）。
  - `POST/PATCH` payload 至少包含 `title`、`body`、`status`、`publish_from`、`publish_to`
  - `DELETE` 為實體刪除。

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

### 5-3-0) 可用模型清單查詢 API
- `GET /main/api/v1/models`
- 用途：提供已登入使用者查看目前 provider 提供的全域模型清單。
- 規則：
  - `user` 與 `admin` 都可使用。
  - 後端需代理 provider `GET /models`。
  - 本次固定查詢全域模型清單，不帶 `team_id`。
  - 不得傳送 `include_metadata`、`include_model_access_groups`、`only_model_access_groups`。
  - 若 provider 回傳 OpenAI-style `data` 陣列，需取每筆 `id` 作為 `id` 與 `label`。
  - 若 provider 回傳字串陣列，需將每個字串映射為 `{ id, label }`。
  - 需去除空值、以 `id` 去重，並依字母排序後回傳。
  - 若 provider 成功但無有效模型，回傳空清單。
  - 若 provider timeout 或 `5xx`，回傳 `503 PROVIDER_UNAVAILABLE`。
  - 若 provider payload 無法辨識，需回傳受控錯誤，不得洩漏原始 payload。
- Response（200）：
```json
{
  "items": [
    {
      "id": "gpt-4o-mini",
      "label": "gpt-4o-mini"
    }
  ],
  "total": 1,
  "fetched_at": "2026-06-05T12:00:00Z"
}
```

### 5-3-1) 單位主檔手動同步 API
- `POST /main/api/v1/institutes/sync`
- 用途：供管理者在「單位代碼資料檢視」頁手動觸發單位主檔同步（後端呼叫 `Persnl.getInstitutes` 並同步本地 DB）。
- 規則：
  - 僅 `admin` 可使用。
  - 需通過 CSRF 驗證與 admin mutation rate limit。
  - 全域同時間僅允許一個手動同步請求執行；只有取得執行權的請求可呼叫 `Persnl.getInstitutes`。
  - 手動同步控制狀態需為 DB 持久化狀態，至少可表達：`status(idle|running)`、`last_result`、`last_started_at`、`last_finished_at`、`cooldown_until`。
  - 若已有其他手動同步處於 `running`，需回傳 `429 INSTITUTE_SYNC_IN_PROGRESS`。
  - 若目前時間早於 `cooldown_until`，需回傳 `429 INSTITUTE_SYNC_COOLDOWN`。
  - `429` 回應需包含至少以下 machine-readable 欄位，供前端顯示冷卻資訊：`retry_after_seconds`、`next_allowed_at`。
  - 成功時需回傳同步統計：`fetched_count`、`inserted_count`、`updated_count`、`unchanged_count`、`deactivated_count`。
  - 成功回應 shape 維持不變，不新增其他必要欄位。
  - 成功完成後需進入全域 cooldown；目前 cooldown 常數先寫死：成功 `15` 分鐘、失敗 `1` 分鐘。
  - Persnl SOAP timeout/5xx 或內部例外結束時，都必須釋放 `running` 狀態，避免控制狀態卡死。
  - Persnl SOAP timeout/5xx 時回傳 `503 SOAP_SERVICE_UNAVAILABLE`。

### 5-3-2) 單位主檔同步狀態查詢 API
- `GET /main/api/v1/institutes/sync-status`
- 用途：供「單位代碼資料檢視」頁初始化手動同步按鈕狀態與 cooldown 倒數。
- 規則：
  - 僅 `admin` 可使用。
  - 回傳目前手動同步控制狀態。
  - 當無 cooldown 生效時，`retry_after_seconds` 回傳 `0`，`next_allowed_at` 回傳 `null`。
- Response（200）：
```json
{
  "status": "idle",
  "retry_after_seconds": 0,
  "next_allowed_at": null
}
```

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
  - `GET /main/api/v1/users`
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
- failure 事件需額外記錄 `error_detail`，供管理者以 `request_id` 搭配稽核頁快速除錯；內容須為安全摘要，不得包含敏感資訊或 stack trace。
- 若 audit 寫入失敗，不得改變原本 API 成功/失敗語意（主流程優先）。

### 6-2) 操作稽核熱資料查詢（v1）
- `GET /main/api/v1/operation-audit-logs`
- 規則：僅 `admin` 可使用。
- 查詢模式：此端點為 `server-side table` contract；分頁、排序與欄位篩選需由後端對完整資料集處理。
- 查詢參數：`page`、`page_size`、`from`、`to`、`event_type`、`action`、`result(success|failure)`、`actor_account`、`target_type`、`target_id`、`error_code`、`sort_by`、`sort_dir`。
- 欄位語意：
  - `event_type`、`result`、`target_type` 為 exact match。
  - `action`、`actor_account`、`target_id`、`error_code` 為 case-insensitive `contains`。
  - `sort_by` 僅允許既定欄位白名單；`sort_dir` 僅允許 `asc|desc`。
- 預設熱資料窗：若未提供 `from/to`，回傳最近 7 天資料。
- 排序：`created_at desc`（最新優先）。
- 回傳欄位（精簡 + 失敗詳情）：`created_at`、`event_type`、`action`、`result`、`actor_account`、`target_type`、`target_id`、`error_code`、`request_id`、`error_detail`。
- `error_detail` 僅在 `failure` 事件提供除錯摘要；`success` 事件回傳 `null`。

### 6-3) 登入稽核熱資料查詢（v1）
- `GET /main/api/v1/auth-audit-logs`
- 規則：僅 `admin` 可使用。
- 查詢模式：此端點為 `server-side table` contract；分頁、排序與欄位篩選需由後端對完整資料集處理。
- 查詢參數：`page`、`page_size`、`from`、`to`、`provider`、`result(success|failure)`、`account`、`sysid`、`role`、`error_code`、`request_id`、`sort_by`、`sort_dir`。
- 欄位語意：
  - `provider`、`result`、`role` 為 exact match。
  - `account`、`error_code`、`request_id` 為 case-insensitive `contains`。
  - `sysid` 為 exact match。
  - `sort_by` 僅允許既定欄位白名單；`sort_dir` 僅允許 `asc|desc`。
- 預設熱資料窗：若未提供 `from/to`，回傳最近 7 天資料。
- 排序：`created_at desc`（最新優先）。
- 回傳欄位（精簡）：`created_at`、`provider`、`result`、`account`、`sysid`、`role`、`error_code`、`request_id`。
- `created_at` 格式需為 UTC `date-time`（RFC 3339，例如 `2026-05-21T08:28:20Z`）。
- 回傳不得包含敏感憑證資訊（access token、refresh token、password、client secret）。

### 6-4) 排程器日誌熱資料查詢（v1）
- `GET /main/api/v1/scheduler-logs`
- 規則：僅 `admin` 可使用。
- 查詢模式：此端點為 `server-side table` contract；分頁、排序與欄位篩選需由後端對完整資料集處理。
- Scheduler Logs tab 在 `file_mode=date` 時，前端需先讓使用者選擇 `job`，再以後端回傳的可用檔案清單選擇單一 `YYYY-MM-DD.log`；不得要求使用者手動輸入或從日曆自由挑選不存在的日期。
- Scheduler Logs tab 在 `file_mode=all|latest` 時，前端不顯示日期選擇器與檔案選單；查詢條件僅保留 `job`、`level`、`q` 與排序/分頁。
- 資料來源：僅允許讀取既有檔案式 scheduler logs；日誌根目錄使用 `SCHEDULER_LOG_ROOT`，未設定時 fallback `/home/app/log`。
- 支援 `job` 白名單：
  - `sync_expired_api_keys`
  - `sync_api_key_usage`
  - `send_expiration_reminders`
- 查詢參數：`page`、`page_size`、`job`、`file_mode`、`from`、`to`、`level`、`q`、`sort_dir`。
- 欄位語意：
  - `job` 為 exact match，且僅允許白名單值。
  - `file_mode` 僅允許 `date|all|latest`，預設 `date`。
  - `file_mode=date` 時，`from`、`to` 格式為 `YYYY-MM-DD`，以 `Asia/Taipei` 日曆日對應日誌檔日期；未提供時預設查最近 7 天。
  - `file_mode=all` 時，忽略 `from`、`to`，改為讀取目標 `job` 目錄下全部符合 `YYYY-MM-DD.log` 的檔案；若未指定 `job`，則對全部白名單 job 各自讀取全部檔案後合併。
  - `file_mode=latest` 時，忽略 `from`、`to`，改為只讀取目標 `job` 目錄下最新一個符合 `YYYY-MM-DD.log` 的檔案；若未指定 `job`，則對全部白名單 job 各自讀取最新檔後合併。
  - `level` 僅允許 `INFO|WARNING|ERROR|CRITICAL`，為 exact match。
  - `q` 為 case-insensitive `contains`，同時比對 parsed `message` 與 `raw_line`。
  - `sort_dir` 僅允許 `asc|desc`，預設 `desc`。
- 檔案處理規則：
  - 僅可由白名單 `job` 映射到白名單目錄，不得接受任意路徑或檔名輸入。
  - `file_mode=date` 需依日期區間展開對應 daily log file 清單，缺少的日誌檔視為空資料，不得回錯。
  - `file_mode=all|latest` 僅可接受符合 `YYYY-MM-DD.log` 命名規則的檔案；其他檔名一律忽略。
  - 需解析既有 log format：`[timestamp] level=LEVEL message`；若僅能部分解析，仍需保留 `raw_line`。
  - 合併多檔結果後，再統一套用 filter、sort 與 pagination。
- 排序：
  - `desc`：`timestamp desc`
  - `asc`：`timestamp asc`
- Response（200）：
```json
{
  "available_files": [
    {
      "log_date": "2026-06-17",
      "source_file": "2026-06-17.log"
    }
  ],
  "items": [
    {
      "id": "sync_api_key_usage:2026-06-17:12",
      "job": "sync_api_key_usage",
      "log_date": "2026-06-17",
      "source_file": "2026-06-17.log",
      "timestamp": "2026-06-17T00:05:01+08:00",
      "level": "INFO",
      "message": "event=usage_sync mode=sync processed_keys=10 success=9 failed=1",
      "raw_line": "[2026-06-17T00:05:01+08:00] level=INFO event=usage_sync mode=sync processed_keys=10 success=9 failed=1"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```
- 錯誤回應：
  - `403 FORBIDDEN`：非 `admin`
  - `422 VALIDATION_ERROR`：`job`、`level`、`sort_dir` 或日期參數不合法

### 6-5) 時間欄位輸出規則
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
    "message": "...",
    "details": "app.api.v1.whitelists:create_whitelist"
  }
}
```
- `error.details` 為 optional string，用於提供受控白名單格式的錯誤來源摘要（例如 `module:function`）。
- `error.details` 僅允許揭露固定來源標籤；不得包含程式碼片段、stack trace、SQL、完整第三方 payload、secret、token 或 API key 明文。

建議錯誤碼：
- `VALIDATION_ERROR`
- `INVALID_APPLICATION_DATE`
- `INVALID_DURATION_DAYS`
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
- 前端對 `VALIDATION_ERROR` 不得僅顯示通用錯誤；需優先顯示後端回傳的具體 `message`，讓使用者可判斷缺少或格式錯誤的欄位

## 驗收標準
### 申請與資格
1. 研究人員名單職稱代碼命中者，或研究名單未命中但特殊人員名單 `active` 命中者，可成功核發 API Key；兩者皆未命中時不得允許進入系統，且申請 API 回傳 `403 APPLICANT_NOT_ELIGIBLE`。
2. 當資格判斷需查詢 `tCode` 且 Persnl SOAP 服務 timeout/5xx 時，登入流程可放行，但申請 API 必須回傳 `503 SOAP_SERVICE_UNAVAILABLE`。
3. 使用者透過 SSO/OAuth 登入後，申請頁需自動帶入 `account`、`name`、`email`、`department`、`sysid`；若 auth context 缺少必要欄位、`sysid` 非數字或非正整數，申請 API 需回傳 `422 VALIDATION_ERROR`，且不得建立申請或 key 紀錄。
4. `duration_days` 僅允許 `30|180|360`，`application_date` 需為合法日期且不得晚於申請當日；非法值需回傳對應驗證錯誤。
5. `admin` 可透過 `target_identity.account` 代他人送出申請；若目錄服務查無帳號、結果不唯一或 Persnl SOAP timeout/5xx，API 需回傳對應 `422 VALIDATION_ERROR` 或 `503 SOAP_SERVICE_UNAVAILABLE`。
6. 一般申請建立的 application row 需保留申請人快照欄位，`is_proxy_submission=false`、`proxy_operator_account=NULL`；代申請需保留目標申請人快照，`is_proxy_submission=true`，且 `proxy_operator_account` 為實際代送的 admin account。
7. `purpose`、proxy `target_identity.account` 若包含明顯程式語法，前端需先提示且不得送出；相同 payload 直接打 API 時需回傳 `422 VALIDATION_ERROR`。

### Key 核發、保存與受控回取
8. 核發成功的 API Key 對外前綴需依 `APP_ENV` 決定：`prod` 為 `sk-` + 30 碼隨機字元，`dev/test` 為 `AS-` + 30 碼隨機字元（總長皆為 33）；明文 key 預設僅於建立成功當下回傳一次，一般查詢端點不得再次回傳明文。
9. 資料庫不得儲存 API Key 明文；需保存 `key_hash`，並可保存 `key_ciphertext` / `key_kek_version` 供受控 reveal 與 lifecycle 操作使用。
10. `POST /main/api/v1/api-keys/{id}/reveal` 僅 `admin` 可使用，回應需包含 `Cache-Control: no-store`；此端點僅供 break-glass，不得成為一般 `renew`、`extend`、`revoke` 流程的依賴。
11. 一次性明文 key 彈窗（含申請成功與 renew 成功）需提供明文 key 複製功能，點擊後 icon 需切換為成功狀態並可自動恢復，且僅可透過明示確認按鈕關閉；不得因 backdrop click、`Esc` 或其他一般 `onClose` 事件消失。

### Provider 與 Lifecycle
12. API key lifecycle 採 external provider 為主權威；`applications`、`renew`、`extend`、`revoke` 均需先完成 provider 操作，再同步本地資料。
13. `extend`、`revoke` 若需舊明文 key，後端必須從 `key_ciphertext` 解密，且明文只可在服務記憶體中短暫使用；不得出現在 DB、log、audit log、exception message。`renew` 不得依賴舊明文 key。
14. 若 provider timeout/5xx、明確拒絕、缺少密文材料、解密失敗或回應不完整，本地不得先改動狀態或有效期限，並需回傳對應錯誤。
15. 若部署使用 local provider adapter 作為開發/測試替身，仍需經由同一 provider abstraction 執行，不得繞過 provider-first 時序直接改本地資料。
16. 外部 provider `POST /key/generate` payload 僅允許 `rpm_limit`、`tpm_limit`、`max_parallel_requests`、`max_budget`、`budget_duration`、`duration`、`team_id`、`key_alias`、`key_type`；`key_type` 固定 `"llm_api"`，`team_id` 固定使用 `PROVIDER_TEAM_ID`，`duration_days(30|180|360)` 需映射為 `30d|180d|360d`，本地 `expires_at` 也需使用相同的 `30|180|360` 天 fixed-day 規則計算，本地設定值為 `0` 的 `rpm_limit` / `tpm_limit` 與 `max_parallel_requests` 需送 `null`，且不得送 `models` 或 `budget_limits`。
17. 外部 provider 驗證 header 需使用 `Authorization: Bearer {PROVIDER_MASTER_KEY}`；`update`、`delete` 若需舊明文 key，request body 一律以 `key` 欄位傳送；`update` 用於 extend 或 alias 同步時可帶 `key_alias`，且 `duration` 一律直接送當次展延基數 `30d|180d|360d`，不得再依 `api_keys.created_at` 累算總天數；本地 `application_date` 仍需在 extend 成功後改寫為本次展延當日，供 UI 顯示目前這一輪有效期；`generate` 成功時一律自 response `key` 讀取新明文 secret。external provider mode 缺少 `PROVIDER_TEAM_ID` 時，`applications`、`renew`、`limit-strategy-config` 同步必須 fail fast。
18. 外部 provider 回傳 `422` 且 body 為 `detail[]` 時，系統需映射為本地 `422 VALIDATION_ERROR`；timeout、5xx、連線錯誤與無法解析必要回應時仍需回 `503 PROVIDER_UNAVAILABLE`。

### Key 查詢、狀態與 Lifecycle 權限
19. `user` 登入後只能看到自己的全部歷史紀錄；若舊 key 已被 renew，來源舊 key 對 `user` 不可見；`admin` 可看到全域完整資料，且每筆至少需能辨識 `owner_account`、`owner_name`。
19. 一般查詢僅能看到 `masked_key`（`APP_ENV=prod` 為 `sk-...XXXX`；`dev/test` 為 `AS-...XXXX`），不得看到明文；清單頁不得顯示建立時間，建立時間僅顯示於單筆詳情視窗。frontend 不得自行把 API 回傳的 `masked_key` 補成 `AS-...`。
20. 單筆詳情需顯示 `purpose`、`department`；若無資料需顯示 `-`。
21. `GET /main/api/v1/api-keys` 與 `GET /main/api/v1/api-keys/{id}` 的 `application_date`、`duration_days`、`expires_at` 語意需一致：對曾 extend 的 key，`application_date` 為最近一次成功展延後的起算日，`duration_days` 為目前這一輪有效期時長（即 `original_duration_days`），`expires_at` 為目前有效到期時間。frontend 清單與詳情不得把曾展延 key 顯示成互相矛盾的時間資訊。
22. `GET /main/api/v1/api-keys` 與 `GET /main/api/v1/api-keys/{id}` 的到期口徑需以 `expires_at` 即時計算；原始狀態為 `active` 且已過期者，對外需顯示為 `expired`。
23. 即使 expired 回填排程停用或失敗，清單、詳情與統計 API 仍需依 effective status 正確呈現 `expired`；回填排程成功後，符合條件的 `api_keys.status` 與 `api_key_applications.status` 需落地更新為 `expired`，且不得誤改 `revoked`。
24. 一般使用者可停用本人 `active` key；停用非本人 key 時需回傳 `KEY_NOT_OWNED_BY_USER` / `403`，停用非 `active` key 時需回傳 `KEY_NOT_ACTIVE`。
25. 一般使用者僅可續發本人 `revoked|expired` key；續發 `active` key 時需回傳 `KEY_NOT_RENEWABLE`，且同一把舊 key 不得重複續發，重複續發需回傳 `KEY_ALREADY_RENEWED`。
26. 一般使用者僅可展延本人 `active` key；展延 `revoked|expired` key 時需回傳 `KEY_NOT_EXTENDABLE`。`active` key 可隨時展延。extend 成功後：
  - `application_date` 一律同步改寫為展延當日，代表最新一輪有效期起算日。
  - `duration_days` 一律重置為 `original_duration_days`，代表目前這一輪有效期時長，不做累加。
  - extend request 不再由使用者選擇天數；每次展延固定沿用該 key 的 `original_duration_days`。
  - `expires_at` 一律以展延當日重新起算：`new_expires_at = application_date + original_duration_days`。
  - provider `duration` 一律直接送 `original_duration_days` 對應的 `30d|180d|360d`，不得再使用 `api_keys.created_at` 累算總天數，也不得使用 `remaining_days` 模型。
27. `budget_max_budget`、`rate_limit_tpm`、`rate_limit_rpm`、`max_parallel_requests` 僅接受 ASCII `0-9`；非數字字元、空字串、科學記號、小數、負號、全形數字與混合字串不得通過前端送出，也不得通過後端 API 驗證。
28. whitelist `note` 需可正常輸入與儲存中英文混合內容，且中文輸入法組字不得被前端驗證破壞；允許空白、`_`、`-`、`、`，但若內容包含明顯程式語法，或含上述以外特殊符號（例如 `.`, `@`, `/`, `<`, `>`），前後端都需拒絕。
29. `key_alias` 僅允許中英文、數字、`_`、`-`、`、`；若包含空白、其他特殊符號，或明顯程式語法，前端需阻擋儲存，後端直接打 API 時需回傳 `422 VALIDATION_ERROR`。
30. `renew`、`extend`、`revoke` 的本地同步不得改變既有受保護 API 路徑、角色模型或現有對外 response shape。

### 到期提醒與通知信
30. 系統需提供背景排程寄送 API Key 到期提醒信；單一排程入口需在同次執行中處理 `30|14|7|3|1` 天全部提醒時段。
31. 提醒判定條件需以 UTC 日期窗口為準：當 `api_keys.status='active'` 且 `expires_at` 落在 `now(UTC)+N days` 的當日區間時，觸發對應 `N` 天提醒；`N` 僅允許 `30|14|7|3|1`。
32. 同一把 key 在同一輪 `expires_at`、同一提醒時段最多成功寄送一次，但不同提醒時段可在不同日期成功寄送；若 `extend` 後 `expires_at` 改變，新的到期日需重新啟動完整提醒週期。
33. 某提醒時段寄送失敗時，不得影響其他 key 或其他提醒時段；只要該時段尚未成功，後續重跑需可再次嘗試。
34. 本輪首次成功寄出任一提醒後，`api_keys.expiration_notice_sent_at` 需填值；寄送失敗不得填值；後續提醒時段不得覆蓋其既有語意。
35. 到期提醒信為目前唯一保留的正式業務信件；`POST /main/api/v1/api-keys/applications`、`POST /main/api/v1/api-keys/{id}/renew` 成功後，以及 `applications|renew|extend|revoke` 遇 `PROVIDER_UNAVAILABLE` 時，系統都不再寄送其他業務通知信。
36. 正式業務通知信內容需中英並列（中文在前、英文在後）；到期提醒信僅寄送申請者本人，需包含正確剩餘天數、到期時間與可展延提示，且信內顯示的到期時間需轉為 `Asia/Taipei`，但提醒判定與資料儲存仍維持 UTC。
37. 通知信模板屬正式契約；主旨、收件者、動態欄位與中英段落順序變更時，需同步更新 `docs/mail.md`。詳細主旨與完整模板內容以 `docs/mail.md` 為準。

### 管理功能與後台查詢
37. 非 `admin` 呼叫特殊人員名單、管理者名單、限制策略、統計、稽核與單位同步相關管理 API 時，均需回傳 `403`。
38. 特殊人員名單比對主鍵為 `sysid`；新增重複 `sysid` 時需回傳 `409 WHITELIST_SYSID_DUPLICATED`，且管理者可刪除條目，刪除後不得再出現在列表。
39. 特殊人員名單新增前使用者查詢（`GET /main/api/v1/users`）僅可使用 `account`、`name` 查詢；不得以 `sysid` 或 `email` 作為查詢條件。管理者名單查詢（`GET /main/api/v1/admins`）需直接讀取 `admins`，不得依賴 Persnl SOAP。
40. 管理者可新增、啟用、停用與刪除管理者；新增後狀態為 `active`，停用後仍保留於名單且狀態改為 `inactive`。`PUT /main/api/v1/admins/{id}` 若已存在需回 `409 ADMIN_ALREADY_EXISTS`；`DELETE` 僅允許刪除 `inactive` 管理者。
41. 前端需阻擋管理者停用自己的管理者權限；管理者新增查詢結果中，對已存在於 `admins` 的人員（包含 `active`、`inactive`）不得顯示新增按鈕。
42. `GET /main/api/v1/api-keys/statistics/users` 僅 `admin` 可用，預設依 `total_applications desc` 排序；`sort_by` 僅允許既定欄位，`scope`、`from`、`to` 與 `application_date` 篩選需生效，且統計結果不得包含 `api_key_plaintext`。
43. 統計 API 每筆資料需包含 `owner_department`；管理者統計表格中的 `total_applications` 與 `active_count` 需可點擊開啟 API Key 明細 Dialog，且明細查詢口徑需跟隨當前 `from`、`to` 篩選；點擊 `active_count` 時僅顯示 `status=active`。
44. `GET /main/api/v1/api-keys` 與 `GET /main/api/v1/api-keys/{id}` 回傳需包含 `key_alias`；未設定時回傳系統產生 alias。`admin` 可透過 `PATCH /main/api/v1/api-keys/{id}` 更新 alias，`user` 呼叫需回傳 `403`，重複 alias 需回傳 `409 KEY_ALIAS_DUPLICATE`；external provider mode 下 alias 更新需同步 provider 狀態。
45. 限制策略設定僅 `admin` 可讀取與更新；`budget_duration` 僅允許 `daily|weekly|monthly`，管理端顯示映射需為 `1天|7天|30天`，且每把 API Key 的限制策略需同時包含 `budget`、`rate_limit` 與 `max_parallel_requests`，其中 `max_parallel_requests` 預設 `0` 代表不限制；不得提供 pending 補發端點或 `issuance_mode` 二選一模式。
46. `admin` 可於 `/institute-view` 查看 `active` institutes 清單與 `total`，並可手動觸發同步；若 Persnl SOAP 不可用，`POST /main/api/v1/institutes/sync` 需回傳 `503 SOAP_SERVICE_UNAVAILABLE`。
46A. `POST /main/api/v1/institutes/sync` 需具備全域 single-flight 與 cooldown 保護：同時間只允許一個手動同步執行；執行中需回 `429 INSTITUTE_SYNC_IN_PROGRESS`，冷卻中需回 `429 INSTITUTE_SYNC_COOLDOWN`，且 `429` 回應至少包含 `retry_after_seconds` 與 `next_allowed_at`。成功後冷卻 `15` 分鐘，失敗後冷卻 `1` 分鐘；成功回應 shape 仍僅包含既有同步統計欄位。
46B. `GET /main/api/v1/institutes/sync-status` 需回傳 DB 持久化的手動同步狀態，供前端重新整理頁面後立即恢復 cooldown 倒數與按鈕 disable 狀態。
47. `user` 與 `admin` 都需可從主導覽列進入「服務使用說明」頁；正式路由為 `/usage-examples`，且頁面中的 `GET /main/api/v1/models` 需允許兩種角色成功呼叫。
47A. 登入後共用主導覽列需支援 responsive 行為：桌機維持頂部 horizontal navigation；較小寬度切換為 hamburger menu + Drawer，且 `系統公告`、`服務使用說明` 仍需維持前兩個共享入口順序。
47B. responsive 主導覽列不得在小螢幕產生導覽標籤重疊、不可讀文字或水平 overflow；active route、語言切換與登出在桌機與 Drawer 內都需可正確使用。
48. `GET /main/api/v1/models` 遇到 provider OpenAI-style `data` 陣列時，需正規化為 `{ id, label }` 清單；provider 回傳字串陣列時也需正規化成功，並去除空值、去重與依字母排序。
49. `GET /main/api/v1/models` 若 provider timeout 或 `5xx`，需回傳 `503 PROVIDER_UNAVAILABLE`；若 provider payload 無法辨識，需走受控錯誤流程，且不得洩漏原始 payload。
50. 服務使用說明頁中的模型清單區塊在 mount 時需自動查詢一次；手動重新整理與每 `15` 分鐘自動刷新需重用同一查詢流程；頁面離開時需清除 timer。
51. 服務使用說明頁需正確呈現 Loading、Empty、Error、Retry 狀態；第一版模型列表僅顯示一欄 `Model`，內容來自 API 回傳的 `label`，且同頁需顯示 repo 內維護的服務說明與至少一組 Python code block。
51AA. 服務使用說明文件需明示每筆 API Key 的用量限額：每分鐘最多 `10` 次請求（`10 RPM`）、每日 token 額度上限 `2,000,000`、同時連線數上限 `3`、上下文視窗 `128K`。
51A. 登入後共用版型不得直接顯示系統公告區塊；系統公告需集中於 `/announcements` 頁，且該頁固定提供連往 `/usage-examples` 的服務使用說明入口。
51B. `GET /main/api/v1/announcements` 對 `user` 與未帶 `scope=all` 的 `admin`，只可回目前有效公告；`inactive`、未到 `publish_from`、或已超過 `publish_to` 的公告不得出現在前台。
51C. `POST /main/api/v1/announcements`、`PATCH /main/api/v1/announcements/{id}`、`DELETE /main/api/v1/announcements/{id}` 僅 `admin` 可使用；非 `admin` 需回 `403`。
51D. 公告 `title`、`body` 若包含 persisted-text 不安全語法需回 `422 VALIDATION_ERROR`；若 `publish_from > publish_to` 也需回 `422 VALIDATION_ERROR`。
51E. `System Announcements Page` 主表格需採 `server-side table`；前端不得只以當前頁 rows 做本地篩選。
51F. `System Announcements Page` 的 `user` 與 `admin` 都需可點擊公告標題，以 modal 檢視該筆公告全文；公告 `body` 不得在列表中直接常駐展開。

### OAuth、Session 與語系
51G. 在 API Key 正式上線前，前端於呼叫 `/main/login`（FISA/OAuth 登入入口）前，需先顯示公開的 `coming-soon` 提示頁；使用者明示點擊後才可真正前往 `/main/login`。正式上線時間到達後，此公開提示頁不得再攔截登入入口。
52. `GET /main/login` 在 `prod` 需導向 OAuth provider；在 `dev/test` 需可直接建立 session auth context 並 redirect `/main/`。`GET /main/auth/callback` 成功時需建立 session 並 redirect `/main/`，失敗時需回錯且寫入 failure audit。
53. 正式環境不得接受 header auth 作為正式認證來源；僅 `dev/test` 可啟用。OAuth 成功登入寫入的角色需固定為 `user`，且流程不得落地 access token、refresh token、password 或 client secret。
54. OAuth callback 需以 claims `sysId/cn/chName/email/instCode/tCode` 建立身份；任一缺漏需拒絕登入。登入資格判斷需遵循 `active whitelist(sysid)` 或 `active admins(id=sysid)`，否則才比對 `LOGIN_ALLOWED_TITLE_CODES`；若同時命中 `active whitelist` 與 `active admins`，最終角色仍以 `admin` 為準。
55. `/main/login-denied` 必須是公開頁；登入失敗導向 `/main/login-denied?error=LOGIN_NOT_ELIGIBLE` 時，使用者需可直接看到拒絕說明與返回登入操作，且不依賴 `GET /main/api/v1/users/me` 成功。
55A. API Key 正式上線前，前端在呼叫 `/main/login` 前需先顯示公開的 `/main/login-coming-soon` 提示頁；使用者明示點擊後才可真正前往 `/main/login`。登入成功後進入 `/main/` 時，`user` 與 `admin` 都需維持既有登入後首頁導向，不得再因未上線而自動跳轉至 `/main/apply/coming-soon`。
56. `GET /main/api/v1/users/me` 需回傳目前使用者資料與 `csrf_token`；所有 `POST/PATCH` 端點在 session auth 模式下，缺少或錯誤 `X-CSRF-Token` 時需回傳 `403 FORBIDDEN`。
57. 系統語言僅支援 `zh-TW`、`en`；DB 無偏好時，系統語言命中 `zh*` 顯示中文、命中 `en*` 顯示英文，其他語系 fallback 為英文，並需立即寫回 DB 作為初始偏好。
58. `GET /main/api/v1/users/preferences/locale` 需回傳目前偏好（`zh-TW|en|null`）；`PATCH` 僅允許 `zh-TW|en`，成功後可立即由 `GET` 讀回。手動切換語言後，重新登入需沿用 DB 偏好，且導覽列、頁標題、按鈕、錯誤/提示訊息與 DataGrid locale 文案需隨語言切換更新。

### 稽核、查詢限制與安全邊界
59. `GET /main/api/v1/users` 與 `POST /main/api/v1/api-keys/applications`、`revoke`、`renew`、`extend`、`whitelists`、`admins`、`announcements`、`limit-strategy-config`、`institutes/sync` 等關鍵操作 API 成功與失敗都需寫入 `operation_audit_logs`，且需可辨識 `error_code`；failure 事件另需提供可供管理者除錯的 `error_detail` 與 `request_id`。其中 `GET /main/api/v1/users` 需以 `lookup_context` 區分 `proxy_application|admin_create|whitelist_create` 用途。
60. `operation_audit_logs` 不得包含 API key 明文或其他敏感憑證；`metadata_json` 與 `error_detail` 僅允許白名單安全內容，不得包含 stack trace、SQL、完整第三方 payload。若 audit 寫入失敗，不得改變主流程成功或失敗語意。
61. `GET /main/api/v1/operation-audit-logs` 與 `GET /main/api/v1/auth-audit-logs` 僅 `admin` 可使用；未提供 `from/to` 時預設回傳最近 7 天熱資料，結果依 `created_at desc` 排序，並支援分頁與既定篩選條件。
61A. `GET /main/api/v1/scheduler-logs` 僅 `admin` 可使用；未提供 `from/to` 時預設回傳以 `Asia/Taipei` 日曆日計算的最近 7 天 scheduler log 熱資料，並依 `timestamp desc` 排序。
61B. `GET /main/api/v1/scheduler-logs` 僅可讀取 `sync_expired_api_keys`、`sync_api_key_usage`、`send_expiration_reminders` 三種既有 job 的檔案式日誌；缺少 daily log file 視為空資料，不得作為錯誤，且不得開放任意 filesystem path 存取。
62. `GET /main/api/v1/users?q=...` 的 `q` 長度不得超過 `100` 字元。
63. 對所有 `server-side table` 頁面，前端 DataGrid 欄位篩選不得只作用於當前頁 rows；`items`、`total`、頁數、排序與篩選結果都必須來自完整資料集的後端查詢。
64. `GET /main/api/v1/api-keys` 的 `owner_account`、`owner_name`、`key_alias` 篩選需採 case-insensitive `contains`；`application_date_from/application_date_to` 與 `expires_from/expires_to` 需分別正確套用到 `application_date` 與 `expires_at`；`sort_by/sort_dir` 僅允許既定白名單欄位與 `asc|desc`。
65. `GET /main/api/v1/api-keys/statistics/users` 的 `q` 僅作全域搜尋；`owner_account`、`owner_name`、`owner_email`、`owner_department` 欄位篩選需彼此獨立且採 case-insensitive `contains`；切換圖表與表格視圖時查詢口徑需保持一致。
65A. `GET /main/api/v1/api-keys` 每筆資料需回傳 `usage_summary`，且需由後端依 `api_keys.usage_*` 最新快取與額度資料組成，不得要求前端自行重算。
65B. `usage_summary.remaining_budget` 不得為負值；`max_budget=0`、`tpm_limit=0`、`rpm_limit=0` 代表 unlimited，對外仍維持 `0`，由前端顯示 `Unlimited`。
65C. `GET /main/api/v1/api-keys` 缺少 usage snapshot 時，`usage_summary.synced_at` 需為 `null`，但前端仍需保留可開啟的 Usage popover。
65D. `GET /main/api/v1/api-keys` 的 `usage_summary.max_budget`、`usage_summary.tpm_limit`、`usage_summary.rpm_limit`、`usage_summary.max_parallel_requests` 必須回傳目前金鑰管理（limit strategy config）設定值，不得沿用個別 key 歷史申請當下的快照值；更新全域金鑰條件後，列表端點下一次讀取即需反映新值，不得等待 usage sync 排程。
65E. `GET /main/api/v1/api-keys/usage-series` 僅允許 `granularity=day`，且需依 `Asia/Taipei` 日曆日回傳每日 token/spend 聚合；DB 內部 UTC bucket 與前端日期語意不得互相衝突。
65F. `POST /main/api/v1/api-keys/applications` 需實作正式上線閘門：`user` 在 `2026-06-30 00:00 Asia/Taipei` 前送出時回 `403 APPLICATION_NOT_LIVE` 並附 `go_live_at`；`admin` 維持可申請/代申請；閘門命中時不得建立任何申請或 key 資料，也不得呼叫 provider。
65F. `api_key_usage_snapshots` 需作為正式 daily usage 歷史來源；同一 `(api_key_id, bucket_granularity, bucket_start_utc)` 只允許一筆有效 bucket，rolling window 重抓時需覆寫既有 bucket，不得產生重複列。
65G. `/usage` 頁需允許 `user` 與 `admin` 依 key + 日期區間查看每日使用量；初始日期區間預設為以 `Asia/Taipei` 計算的最近 `7` 個日曆日（含當日）且欄位不得為空，並需提供 `最近 7 日`、`最近 14 日`、`最近一個月` 快捷選日按鈕；主圖表指標為 `total_tokens`，tooltip 至少顯示 `prompt_tokens`、`completion_tokens`、`total_tokens`，且無資料時需回空狀態而非偽造零值資料。
65H. `/usage` 頁在日期區間超過 `31` 個日曆日時，X 軸仍需對齊完整日期區間且缺資料日不得補 `0`；主圖預設顯示 `31` 天視窗，並提供底部 slider 讓使用者以 `1..31` 天的範圍調整主圖區間，且調整後仍可左右平移瀏覽整段區間。
65I. `/usage` 頁底部 slider 的開始/結束日期 label 在常見桌機與手機寬度下需完整可見，不得因 slider 寬度或端點對齊而被裁切。
66. `GET /main/api/v1/operation-audit-logs` 與 `GET /main/api/v1/auth-audit-logs` 需支援欄位級 server-side sorting/filtering；若某欄位未支援後端 query contract，對應前端欄位必須禁用 filter 或 sort，不得回退成 local table 行為。
66A. `/operation-audit-logs` 頁需沿用既有 admin-only 路由，並新增 Scheduler Logs 第三個 tab；該 tab 的篩選、排序與分頁需完全依賴 `GET /main/api/v1/scheduler-logs`，不得回退成 local table 或另開新路由。
67. 關鍵操作稽核功能、申請人識別欄位調整、統計、`GET /main/api/v1/models` 與 lifecycle 擴充，均不得改動既有受保護 API 路徑與角色模型（`user|admin`）；若需擴充對外 error response，僅允許增加相容性的 optional 欄位（如 `error.details`），不得破壞既有 `error.code` / `error.message` 契約或既有 success response shape。

## Roadmap
### Phase 1：Foundation
- 建立後端專案骨架與資料表 migration
- 實作 `api_key_whitelist`、`api_key_applications`、`api_keys` 基礎模型
- 建立基本錯誤處理與日誌

### Phase 2：MVP API
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

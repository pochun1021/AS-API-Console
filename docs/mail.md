# Mail 測試速查表

本文件提供 AS API Console 的 SMTP 測試最短流程，使用 `backend/scripts/send_test_email.py` 驗證寄信設定。
目前正式業務信件僅保留 API Key 到期提醒信，因此本文件也用於到期提醒排程（`backend/scripts/send_expiration_reminders.py`）的寄信前置檢查與模板驗收。

## 1) 最小必要設定（`.env`）

部署環境建議使用外部設定檔 `/home/app/config/.env`（搭配 `ENV_FILE=/home/app/config/.env`）；本文件中的 `.env` 指該環境變數檔內容。

```env
MAIL_ENABLED=true
MAIL_SERVER=smtp.example.internal
MAIL_PORT=25
MAIL_FROM_NAME=AS API Console

# 可選：需要認證時再填
MAIL_USERNAME=
MAIL_PASSWORD=
```

說明：
- `MAIL_ENABLED` 必須是 `true` 才會送信。
- `MAIL_SERVER`、`MAIL_PORT` 為必要欄位。
- 寄件者地址固定為 `noreply@as.edu.tw`，不使用 `MAIL_FROM` 覆寫。
- `MAIL_USERNAME` / `MAIL_PASSWORD` 可留空（程式會自動走無認證模式）。

## 2) 執行測試信

使用 `uv`：
```bash
cd backend
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/send_test_email.py --to your.name@example.com
```

若環境沒有 `uv`：
```bash
cd backend
. .venv/bin/activate
python scripts/send_test_email.py --to your.name@example.com
```

指定非預設 env 檔：

使用 `uv`：
```bash
cd backend
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/send_test_email.py --to your.name@example.com --env-file .env.local
```

若環境沒有 `uv`：
```bash
cd backend
. .venv/bin/activate
python scripts/send_test_email.py --to your.name@example.com --env-file .env.local
```

## 3) 成功/失敗判讀

- 成功：
  - 終端機輸出 `OK: test email sent to ...`
- 常見失敗：
  - `MAIL_ENABLED is false`：請確認 `.env` 不是 `false`，且沒有拼字錯誤（例如 `trye`）。
  - `MAIL_SERVER is empty`：SMTP 主機未設定。
  - `Connection refused` / timeout：主機、port、網路路徑或防火牆未開通。
  - TLS/SSL 相關錯誤：檢查 `MAIL_STARTTLS` / `MAIL_SSL_TLS` 與 SMTP 端要求是否一致。

## 4) 參數行為備註

- 帳密自動判斷：
  - `MAIL_USERNAME`、`MAIL_PASSWORD` 兩者都有值才使用 SMTP 認證。
  - 任一為空即走無認證模式。
- 本測試信僅驗證 SMTP 連線與發信能力，不會寫入業務資料。

## 5) 到期提醒模板

以下主旨與內容為正式模板契約；若程式調整主旨、收件者、動態欄位或文案語意，需同步更新 `docs/SPEC.md` 與本文件。

### 5.1 到期提醒通知信

- 觸發時機：到期前 `30|14|7|3|1` 天命中提醒窗口時
- 收件者：申請者本人
- 主旨：
  - `[AS-ITS] API Key 將於 {days_before} 天後到期 / API Key Expiration Notice ({days_before} Days Remaining)`
- 動態欄位：
  - `{days_before}`：僅允許 `30|14|7|3|1`
  - `{expires_at_zh}`：格式 `YYYY 年 M 月 D 日 HH:MM（UTC+8）`
  - `{expires_at_en}`：格式 `Month D, YYYY, HH:MM (UTC+8)`
- 內容：

```text
親愛的使用者，您好：
提醒您，您的 API Key 將於 {days_before} 天後到期。
到期時間：{expires_at_zh}
如需持續使用，請於到期前或到期後至系統進行展延（Extend）作業。

服務申請／展延網址：https://api.ascs.sinica.edu.tw/main/

若您未曾申請或使用此 API Key，請與資訊服務處服務台聯繫。
如有其他相關問題，歡迎與我們聯絡。

聯絡資訊：
線上服務台（上班時間）：https://its.sinica.edu.tw/online
電話（上班時間）：(02) 2789-8855
電子郵件：its@sinica.edu.tw

中央研究院資訊服務處 敬啟

Dear User,

This is a reminder that your API Key will expire in {days_before} days.
Expiration Date and Time: {expires_at_en}

If you wish to continue using this API Key, please extend it through the system either before or after its expiration.

Application / Extension URL: https://api.ascs.sinica.edu.tw/main/

If you did not apply for or use this API Key, please contact the IT Service Desk.
For any questions, please feel free to contact us.

Contact Information:
Online Service Desk (Business Hours): https://its.sinica.edu.tw/online
Phone (Business Hours): +886-2-2789-8855
Email: its@sinica.edu.tw

Sincerely,

The Department of Information Technology Services
Academia Sinica
```

## 6) 到期提醒排程快速驗證

```bash
cd backend
ENV_FILE=/home/app/config/.env ./scripts/run_expiration_reminder.sh --dry-run
```

說明：
- `--dry-run` 會檢查目前是否命中任一 `30|14|7|3|1` 天提醒時段的資料筆數，不會實際寄信。
- 提醒判定以 UTC 日期窗口為準；同一支腳本一次會處理全部提醒時段。
- 提醒信內的到期時間顯示為 `Asia/Taipei`；排程判定與資料儲存仍維持 UTC。
- 正式寄送時移除 `--dry-run`；寄送結果與錯誤會寫入 `log/send_expiration_reminders/`。
- 驗收時需確認郵件主旨或內容顯示正確剩餘天數，例如 `30`、`14`、`7`、`3`、`1` 天。

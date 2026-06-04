# Mail 測試速查表

本文件提供 AS API Console 的 SMTP 測試最短流程，使用 `backend/scripts/send_test_email.py` 驗證寄信設定。
同時也可用於 API Key 到期提醒排程（`backend/scripts/send_expiration_reminders.py`）之寄信前置檢查。

## 1) 最小必要設定（`.env`）

部署環境建議使用外部設定檔 `/home/app/config/.env`（搭配 `ENV_FILE=/home/app/config/.env`）；本文件中的 `.env` 指該環境變數檔內容。

```env
MAIL_ENABLED=true
MAIL_SERVER=smtp.example.internal
MAIL_PORT=25
MAIL_FROM=noreply@example.com
MAIL_FROM_NAME=AS API Console

# 可選：需要認證時再填
MAIL_USERNAME=
MAIL_PASSWORD=
```

說明：
- `MAIL_ENABLED` 必須是 `true` 才會送信。
- `MAIL_SERVER`、`MAIL_PORT`、`MAIL_FROM` 為必要欄位。
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
  - `MAIL_FROM is empty`：寄件者地址未設定。
  - `Connection refused` / timeout：主機、port、網路路徑或防火牆未開通。
  - TLS/SSL 相關錯誤：檢查 `MAIL_STARTTLS` / `MAIL_SSL_TLS` 與 SMTP 端要求是否一致。

## 4) 參數行為備註

- 帳密自動判斷：
  - `MAIL_USERNAME`、`MAIL_PASSWORD` 兩者都有值才使用 SMTP 認證。
  - 任一為空即走無認證模式。
- 本測試信僅驗證 SMTP 連線與發信能力，不會寫入業務資料。

## 5) 業務通知模板

以下主旨與內容為正式模板契約；若程式調整主旨、收件者、動態欄位或文案語意，需同步更新 `docs/SPEC.md` 與本文件。

### 5.1 申請成功通知信

- 觸發時機：`POST /main/api/v1/api-keys/applications` 成功後背景寄送
- 收件者：申請者本人
- 主旨：
  - `[AS API Console] 成功申請 API Key / API key application successful`
- 內容：

```text
親愛的使用者，您好：
感謝您申請 API Key 請妥善保管
若此操作非您本人執行，請立即連繫資訊服務處。
若您有任何疑問，歡迎向資訊服務處服務台反映。
聯絡窗口：中央研究院資訊服務處
線上服務台（上班時間）：https://its.sinica.edu.tw/online（密碼27898855）
電話（上班時間）：02-27898855
信箱：its@sinica.edu.tw
中央研究院資訊服務處 敬啟

Dear user,
Thank you for applying for an API key. Please keep it secure.
If this action was not performed by you, please contact the IT Service Desk immediately.
If you have any questions, please contact the IT Service Desk.
Contact: Institute of Information Science, Academia Sinica IT Service Desk
Online Service Desk (business hours): https://its.sinica.edu.tw/online (password: 27898855)
Phone (business hours): 02-27898855
Email: its@sinica.edu.tw
Sincerely,
Academia Sinica IT Service Desk
```

### 5.2 Renew 成功通知信

- 觸發時機：`POST /main/api/v1/api-keys/{id}/renew` 成功後寄送
- 收件者：申請者本人
- 主旨：
  - `[AS API Console] API Key 已更新 / API key renew`
- 內容：

```text
親愛的使用者，您好：
您已成功更新 API Key 請妥善保管
若此操作非您本人執行，請立即連繫資訊服務處。
若您有任何疑問，歡迎向資訊服務處服務台反映。
聯絡窗口：中央研究院資訊服務處
線上服務台（上班時間）：https://its.sinica.edu.tw/online（密碼27898855）
電話（上班時間）：02-27898855
信箱：its@sinica.edu.tw
中央研究院資訊服務處 敬啟

Dear user,
You have successfully renewed your API key. Please keep it secure.
If this action was not performed by you, please contact the IT Service Desk immediately.
If you have any questions, please contact the IT Service Desk.
Contact: Institute of Information Science, Academia Sinica IT Service Desk
Online Service Desk (business hours): https://its.sinica.edu.tw/online (password: 27898855)
Phone (business hours): 02-27898855
Email: its@sinica.edu.tw
Sincerely,
Academia Sinica IT Service Desk
```

### 5.3 Provider 配發失敗通知信

- 觸發時機：`applications`、`renew`、`extend`、`revoke` 任一 provider timeout/5xx
- 收件者：所有 `active` 管理者
- 主旨：
  - `[AS API Console] API Key 配發失敗通知 / API key issuance failure`
- 動態欄位：
  - `{operation}`
  - `{actor_account}`
  - `{actor_role}`
  - `{target_account}`
  - `{error_code}`
- 內容：

```text
管理者您好：
系統偵測到 API Key 配發失敗，請協助確認 provider 連線與服務狀態。
操作類型：{operation}
操作者：{actor_account}（{actor_role}）
目標帳號：{target_account}
錯誤代碼：{error_code}
此通知不包含任何明文金鑰或敏感憑證。

Dear admin,
The system detected an API key issuance failure. Please verify provider connectivity and service status.
Operation: {operation}
Actor: {actor_account} ({actor_role})
Target account: {target_account}
Error code: {error_code}
This notice does not include plaintext keys or sensitive credentials.
```

### 5.4 到期提醒通知信

- 觸發時機：到期前 `30|14|7|3|1` 天命中提醒窗口時
- 收件者：申請者本人
- 主旨：
  - `[AS API Console] API Key 將於 {days_before} 天後到期 / Expires in {days_before} days`
- 動態欄位：
  - `{days_before}`：僅允許 `30|14|7|3|1`
  - `{expires_at_zh}`：格式 `YYYY-MM-DD HH:MM 台灣時間`
  - `{expires_at_en}`：格式 `YYYY-MM-DD HH:MM Asia/Taipei`
- 內容：

```text
親愛的使用者，您好：
提醒您，您的 API Key 將於 {days_before} 天後到期。
到期時間：{expires_at_zh}
若距離到期 30 天內或已到期，您可進行展延（extend）。
若此操作非您本人執行，請立即連繫資訊服務處。
若您有任何疑問，歡迎向資訊服務處服務台反映。
聯絡窗口：中央研究院資訊服務處
線上服務台（上班時間）：https://its.sinica.edu.tw/online（密碼27898855）
電話（上班時間）：02-27898855
信箱：its@sinica.edu.tw
中央研究院資訊服務處 敬啟

Dear user,
This is a reminder that your API key will expire in {days_before} days.
Expiration time: {expires_at_en}
You can extend this key within 30 days before expiration or after it has expired.
If this action was not performed by you, please contact the IT Service Desk immediately.
If you have any questions, please contact the IT Service Desk.
Contact: Institute of Information Science, Academia Sinica IT Service Desk
Online Service Desk (business hours): https://its.sinica.edu.tw/online (password: 27898855)
Phone (business hours): 02-27898855
Email: its@sinica.edu.tw
Sincerely,
Academia Sinica IT Service Desk
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

# Mail 測試速查表

本文件提供 AS API Console 的 SMTP 測試最短流程，使用 `backend/scripts/send_test_email.py` 驗證寄信設定。
同時也可用於 API Key 到期提醒排程（`backend/scripts/send_expiration_reminders.py`）之寄信前置檢查。

## 1) 最小必要設定（`.env`）

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

## 5) 到期提醒排程快速驗證

```bash
cd backend
./scripts/run_expiration_reminder.sh --dry-run
```

說明：
- `--dry-run` 僅檢查目前命中提醒條件的資料筆數，不會實際寄信。
- 正式寄送時移除 `--dry-run`；寄送結果與錯誤會寫入 `log/send_expiration_reminders/`。

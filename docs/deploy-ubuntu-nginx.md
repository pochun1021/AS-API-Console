# Ubuntu + Nginx 部署指南（Systemd + Uvicorn）

本文件提供在 Ubuntu 主機部署 AS API Console 的實作流程，採用：
- Nginx（反向代理）
- Systemd（管理 FastAPI 服務）
- Uvicorn（ASGI server）
- MariaDB（同機安裝示例）
- Let's Encrypt（HTTPS 憑證）

產品/API/data 契約以 `docs/SPEC.md` 為準；本文件僅處理部署與維運。

## 1. 先決條件

- Ubuntu 22.04/24.04（有 sudo 權限）
- 已準備網域，例如 `api-console.example.org`
- DNS A record 已指向此 Ubuntu 主機公網 IP
- 防火牆已開放 `80`、`443`

建議先確認 DNS：
```bash
dig +short api-console.example.org
```

## 2. 安裝系統套件

```bash
sudo apt update
sudo apt install -y nginx mariadb-server python3 python3-venv python3-pip git curl certbot python3-certbot-nginx
```

啟用並檢查服務：
```bash
sudo systemctl enable --now nginx
sudo systemctl enable --now mariadb
sudo systemctl status nginx --no-pager
sudo systemctl status mariadb --no-pager
```

## 3. 建立部署目錄與系統帳號

```bash
sudo useradd --system --create-home --shell /bin/bash asapi
sudo mkdir -p /opt/as-api-console
sudo chown -R asapi:asapi /opt/as-api-console
```

> 下列步驟以 `/opt/as-api-console` 為專案路徑。

## 4. 下載專案與安裝依賴

```bash
sudo -u asapi -H bash -lc '
cd /opt/as-api-console
if [ ! -d .git ]; then
  git clone <YOUR_REPO_URL> .
else
  git pull --ff-only
fi
'
```

### 4.1 Backend 依賴（venv + requirements.txt）

```bash
sudo -u asapi -H bash -lc '
cd /opt/as-api-console/backend
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
'
```

### 4.2 Frontend build

```bash
sudo -u asapi -H bash -lc '
cd /opt/as-api-console/frontend
npm install
npm run build
'
```

## 5. MariaDB 同機初始化

進入 MariaDB：
```bash
sudo mariadb
```

執行 SQL（請替換安全密碼）：
```sql
CREATE DATABASE as_api_console CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'as_api'@'127.0.0.1' IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON as_api_console.* TO 'as_api'@'127.0.0.1';
FLUSH PRIVILEGES;
```

連線測試：
```bash
mariadb -h 127.0.0.1 -u as_api -p as_api_console -e "SELECT 1;"
```

## 6. 設定 backend 環境變數

建立環境檔：
```bash
sudo -u asapi -H bash -lc '
cd /opt/as-api-console/backend
cp -n .env.example .env
'
```

編輯 `/opt/as-api-console/backend/.env`，至少確認以下欄位：

- `APP_DOMAIN=https://api-console.example.org`
- `DB_USER=as_api`
- `DB_PASSWORD=CHANGE_ME_STRONG_PASSWORD`
- `DB_HOST=127.0.0.1`
- `DB_PORT=3306`
- `DB_NAME=as_api_console`
- `API_KEY_ENCRYPTION_SECRET=<strong-random-secret>`
- `ISSUANCE_PROVIDER_MODE=external`（若暫不串 provider 可改 `local`）
- `SESSION_SECRET_KEY=<strong-random-secret>`
- OAuth 必填欄位（依你環境提供）：
  - `OAUTH_AUTH_URI`
  - `OAUTH_TOKEN_URI`
  - `OAUTH_BASIC_URI`
  - `OAUTH_CLIENT_ID`
  - `OAUTH_CLIENT_SECRET`
  - `OAUTH_REDIRECT_URI=https://api-console.example.org/auth/callback`

如果你改用 `DATABASE_URL`，它會覆蓋 `DB_*` 組合結果。
本部署文件為正式環境流程，`TEST_DB_*` / `TEST_DATABASE_URL` 僅供測試使用，正式部署不需要設定。

systemd `EnvironmentFile` 注意事項：
- `.env` 每行使用 `KEY=VALUE`，不要加 `export`
- 布林值請用 `true/false`
- 若缺少 `APP_DOMAIN` 或（未提供 `DATABASE_URL` 且缺 `DB_PASSWORD` / `DB_HOST`），服務會啟動失敗

## 7. 資料庫 migration

```bash
sudo -u asapi -H bash -lc '
cd /opt/as-api-console/backend
. .venv/bin/activate
alembic upgrade head
'
```

確認 revision：
```bash
sudo -u asapi -H bash -lc '
cd /opt/as-api-console/backend
. .venv/bin/activate
alembic current
'
```

## 8. 先手動啟動一次 backend 驗證

```bash
sudo -u asapi -H bash -lc '
cd /opt/as-api-console/backend
. .venv/bin/activate
set -a
source .env
set +a
uvicorn app.main:app --host 127.0.0.1 --port 8000
'
```

另一個 terminal 測試：
```bash
curl -I http://127.0.0.1:8000/
curl -I http://127.0.0.1:8000/docs
```

確認正常後，用 `Ctrl+C` 停掉手動服務。

## 9. 建立 systemd 服務

建立 `/etc/systemd/system/as-api-console.service`：

```ini
[Unit]
Description=AS API Console FastAPI Service
After=network.target mariadb.service

[Service]
Type=simple
User=asapi
Group=asapi
WorkingDirectory=/opt/as-api-console/backend
EnvironmentFile=/opt/as-api-console/backend/.env
ExecStart=/opt/as-api-console/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

載入並啟動：
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now as-api-console
sudo systemctl status as-api-console --no-pager
```

查看 log：
```bash
sudo journalctl -u as-api-console -n 200 --no-pager
```

## 10. 設定 Nginx 反向代理

建立 `/etc/nginx/sites-available/as-api-console`：

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name api-console.example.org;

    client_max_body_size 20m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;

        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

啟用站台：
```bash
sudo ln -sf /etc/nginx/sites-available/as-api-console /etc/nginx/sites-enabled/as-api-console
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

先驗證 HTTP：
```bash
curl -I http://api-console.example.org/
curl -I http://api-console.example.org/docs
```

## 11. 申請 Let's Encrypt 憑證（HTTPS）

```bash
sudo certbot --nginx -d api-console.example.org
```

完成後驗證：
```bash
curl -I https://api-console.example.org/
curl -I https://api-console.example.org/docs
```

測試續約：
```bash
sudo certbot renew --dry-run
```

## 12. 驗收清單

- `https://api-console.example.org/` 可開啟前端
- `https://api-console.example.org/docs` 可開啟 OpenAPI
- `https://api-console.example.org/login` 可進入 OAuth 流程
- `sudo systemctl status as-api-console` 為 `active (running)`
- `sudo systemctl status nginx` 為 `active (running)`
- `sudo certbot renew --dry-run` 成功

## 13. 常用維運指令

重啟服務：
```bash
sudo systemctl restart as-api-console
sudo systemctl reload nginx
```

更新程式（手動）：
```bash
sudo -u asapi -H bash -lc '
cd /opt/as-api-console
git pull --ff-only
cd backend
. .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
cd ../frontend
npm install
npm run build
'
sudo systemctl restart as-api-console
```

## 14. 常見問題排查

### 14.1 502 Bad Gateway

檢查 backend 是否存活：
```bash
sudo systemctl status as-api-console --no-pager
sudo journalctl -u as-api-console -n 200 --no-pager
```

若 backend 未啟動，優先修正 `.env` 或 DB 連線問題。

### 14.2 `/docs` 可開但首頁空白

通常是前端 build 未產生或路徑錯誤：
```bash
sudo -u asapi -H bash -lc 'cd /opt/as-api-console/frontend && npm run build'
sudo systemctl restart as-api-console
```

### 14.3 Alembic migration 失敗

確認 `.env` 中 DB 參數或 `DATABASE_URL` 正確，並檢查 MariaDB 使用者權限。

### 14.4 HTTPS 申請失敗

- 確認網域 DNS 已正確指向主機
- 確認 `80/443` 對外可連
- 確認 Nginx `server_name` 與申請網域一致

## 15. 安全建議（正式環境）

- 使用高強度隨機值作為 `API_KEY_ENCRYPTION_SECRET`、`SESSION_SECRET_KEY`
- 定期更新系統與依賴套件
- 以最小權限原則設定 DB 帳號
- 使用 `ufw` 或雲端安全群組限制不必要對外 port
- 搭配集中式 log/監控（例如 journal forwarding、APM）

## 16. API Key Expired 回填排程部署

狀態策略採混合模式：
- 對外顯示以 effective status 即時計算（`active` + `expires_at` 已過 => `expired`）。
- 透過排程執行 `backend/scripts/run_expire_sync.sh`，將 DB 狀態回填落地。
- 建議頻率：每日 `00:10`。

### 16.1 方案 A（建議）：systemd timer

建立 `/etc/systemd/system/as-api-expire-sync.service`：
```ini
[Unit]
Description=AS API Console Expired API Key Sync
After=network.target mariadb.service

[Service]
Type=oneshot
User=asapi
Group=asapi
WorkingDirectory=/opt/as-api-console/backend
ExecStart=/opt/as-api-console/backend/scripts/run_expire_sync.sh
```

建立 `/etc/systemd/system/as-api-expire-sync.timer`：
```ini
[Unit]
Description=Run expired API key sync daily at 00:10

[Timer]
OnCalendar=*-*-* 00:10:00
Persistent=true
Unit=as-api-expire-sync.service

[Install]
WantedBy=timers.target
```

啟用與驗證：
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now as-api-expire-sync.timer
sudo systemctl list-timers as-api-expire-sync.timer --all
sudo systemctl status as-api-expire-sync.timer --no-pager
```

手動觸發與看 log：
```bash
sudo systemctl start as-api-expire-sync.service
sudo journalctl -u as-api-expire-sync.service -n 200 --no-pager
sudo -u asapi tail -n 100 /opt/as-api-console/log/sync_expired_api_keys/$(TZ=Asia/Taipei date +%F).log
```

### 16.2 方案 B：cron

以 `asapi` 使用者設定 crontab：
```bash
sudo -u asapi crontab -e
```

加入：
```cron
10 0 * * * /opt/as-api-console/backend/scripts/run_expire_sync.sh
```

檢查：
```bash
sudo -u asapi crontab -l
sudo -u asapi tail -n 100 /opt/as-api-console/log/sync_expired_api_keys/$(TZ=Asia/Taipei date +%F).log
```

說明：
- 回填腳本會自行寫入專案根目錄 `log/sync_expired_api_keys/`，以 `Asia/Taipei` 切日並採 `YYYY-MM-DD.log` 每日一檔。
- 建議保留 cron 預設 stdout/stderr 行為（系統郵件或平台收集）；業務執行紀錄以上述檔案為主。

### 16.3 排錯重點
- `.env` 未設定或 DB 參數錯誤：確認 `/opt/as-api-console/backend/.env` 內容。
- 執行環境找不到 `uv`：腳本會自動 fallback 到 `.venv/bin/python` 或 `python`，但仍需先安裝依賴。
- 權限問題：確認 `asapi` 對專案目錄可讀執行，且可連線 DB。

### 16.4 驗證清單（建議）
1. 檢查排程已啟用：
```bash
sudo systemctl list-timers as-api-expire-sync.timer --all
sudo -u asapi crontab -l
```
2. 手動 dry-run：
```bash
sudo -u asapi -H bash -lc 'cd /opt/as-api-console/backend && ./scripts/run_expire_sync.sh --dry-run'
```
3. 檢查當日日誌：
```bash
sudo -u asapi tail -n 100 /opt/as-api-console/log/sync_expired_api_keys/$(TZ=Asia/Taipei date +%F).log
```

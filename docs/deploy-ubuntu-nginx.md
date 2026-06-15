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
- 已準備網域，例如 `api.ascs.sinica.edu.tw`
- DNS A record 已指向此 Ubuntu 主機公網 IP
- 防火牆已開放 `80`、`443`

建議先確認 DNS：
```bash
dig +short api.ascs.sinica.edu.tw
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
sudo useradd --system --create-home --shell /bin/bash asapic
sudo mkdir -p /home/app
sudo chown -R asapic:asapic /home/app
```

> 下列步驟會將 root 下的專案搬遷到 `/home/app/AS-API-Console`。

## 4. 下載專案與安裝依賴

```bash
sudo -u asapic -H bash -lc '
cd /home/app/AS-API-Console
if [ ! -d .git ]; then
  git clone <YOUR_REPO_URL> .
else
  git pull --ff-only
fi
'
```

### 4.1 Backend 依賴（venv + requirements.txt）

```bash
sudo -u asapic -H bash -lc '
cd /home/app/AS-API-Console/backend
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
'
```

### 4.2 Frontend build

```bash
sudo -u asapic -H bash -lc '
cd /home/app/AS-API-Console/frontend
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
CREATE USER 'as_api_console'@'localhost' IDENTIFIED BY 'CHANGE_ME_STRONG_PASSWORD';
GRANT ALL PRIVILEGES ON as_api_console.* TO 'as_api_console'@'localhost';
FLUSH PRIVILEGES;
```

連線測試：
```bash
mariadb -h localhost -u as_api_console -p as_api_console -e "SELECT 1;"
```

## 6. 設定 backend 環境變數

建立環境檔：
```bash
sudo -u asapic -H bash -lc '
mkdir -p /home/app/config
cp -n /home/app/AS-API-Console/backend/.env.example /home/app/config/.env
chmod 600 /home/app/config/.env
'
```

編輯 `/home/app/config/.env`，至少確認以下欄位：

- `APP_DOMAIN=https://api.ascs.sinica.edu.tw/main`
- `DB_USER=as_api_console`
- `DB_PASSWORD=CHANGE_ME_STRONG_PASSWORD`
- `DB_HOST=localhost`
- `DB_PORT=3306`
- `DB_NAME=as_api_console`
- `API_KEY_ENCRYPTION_SECRET=<strong-random-secret>`
- `ISSUANCE_PROVIDER_MODE=external`（若暫不串 provider 可改 `local`）
- `SESSION_SECRET_KEY=<strong-random-secret>`
- `ALLOWED_HOSTS=api.ascs.sinica.edu.tw,localhost,127.0.0.1`
- Persnl SOAP（單位主檔同步使用）：
  - `PERSNL_SOAP_URL`（可選，runtime endpoint）
  - `PERSNL_SOAP_WSDL_URL`（可選，WSDL endpoint）
  - `PERSNL_SOAP_USER`（建議必填）
  - `PERSNL_SOAP_PASSWORD`（建議必填）
  - `PERSNL_SOAP_TIMEOUT_SECONDS=3.0`（可選）
- OAuth 必填欄位（依你環境提供）：
  - `OAUTH_AUTH_URI`
  - `OAUTH_TOKEN_URI`
  - `OAUTH_BASIC_URI`
  - `OAUTH_CLIENT_ID`
  - `OAUTH_CLIENT_SECRET`
  - `OAUTH_REDIRECT_URI=https://api.ascs.sinica.edu.tw/main/auth/callback`

如果你改用 `DATABASE_URL`，它會覆蓋 `DB_*` 組合結果。
本部署文件為正式環境流程，`TEST_DB_*` / `TEST_DATABASE_URL` 僅供測試使用，正式部署不需要設定。

`ENV_FILE` 目標檔注意事項：
- `.env` 每行使用 `KEY=VALUE`，不要加 `export`
- 布林值請用 `true/false`
- 若缺少 `APP_DOMAIN` 或（未提供 `DATABASE_URL` 且缺 `DB_PASSWORD` / `DB_HOST`），服務會啟動失敗

## 7. 資料庫 migration

```bash
sudo -u asapic -H bash -lc '
cd /home/app/AS-API-Console/backend
. .venv/bin/activate
alembic upgrade head
'
```

確認 revision：
```bash
sudo -u asapic -H bash -lc '
cd /home/app/AS-API-Console/backend
. .venv/bin/activate
alembic current
'
```

## 8. 先手動啟動一次 backend 驗證

```bash
sudo -u asapic -H bash -lc '
cd /home/app/AS-API-Console/backend
. .venv/bin/activate
export ENV_FILE=/home/app/config/.env
set -a
source "$ENV_FILE"
set +a
uvicorn app.main:app --host 127.0.0.1 --port 8000
'
```

另一個 terminal 測試：
```bash
curl -I http://127.0.0.1:8000/main/
curl -I http://127.0.0.1:8000/main/docs
```

確認正常後，用 `Ctrl+C` 停掉手動服務。

## 9. 建立 systemd 服務

建立 `/etc/systemd/system/as-api-console.service`：

```ini
[Unit]
Description=AS-API-Console FastAPI Service
After=network.target mariadb.service

[Service]
Type=simple
User=asapic
Group=asapic
WorkingDirectory=/home/app/AS-API-Console/backend
Environment=ENV_FILE=/home/app/config/.env
ExecStart=/home/app/AS-API-Console/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
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

先建立共用安全標頭 snippet `/etc/nginx/snippets/as-api-console-security-headers.conf`：

```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header X-Frame-Options "DENY" always;
add_header Referrer-Policy "no-referrer" always;
add_header Strict-Transport-Security "max-age=15768000" always;
add_header Content-Security-Policy "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://api.ascs.sinica.edu.tw; manifest-src 'self'; upgrade-insecure-requests" always;
```

再建立 `/etc/nginx/sites-available/as-api-console`：

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name api.ascs.sinica.edu.tw;

    client_max_body_size 20m;
    include /etc/nginx/snippets/as-api-console-security-headers.conf;

    location /main/ {
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
curl -I http://api.ascs.sinica.edu.tw/main/
curl -I http://api.ascs.sinica.edu.tw/main/docs
curl -I http://api.ascs.sinica.edu.tw/main/ | rg -i 'content-security-policy|x-frame-options|strict-transport-security'
```

## 11. 申請 Let's Encrypt 憑證（HTTPS）

```bash
sudo certbot --nginx -d api.ascs.sinica.edu.tw
```

憑證安裝後，請再次確認 `443` 的 `/main/` 反向代理仍指向 backend `127.0.0.1:8000`（避免誤導到前端 dev server），且 `443` 的 server block 也有 `include /etc/nginx/snippets/as-api-console-security-headers.conf;`：
```bash
sudo nginx -T | sed -n '/server_name api.ascs.sinica.edu.tw/,/}/p'
```

完成後驗證：
```bash
curl -I https://api.ascs.sinica.edu.tw/main/
curl -I https://api.ascs.sinica.edu.tw/main/docs
curl -I https://api.ascs.sinica.edu.tw/main/ | rg -i 'content-security-policy|x-frame-options|strict-transport-security'
curl -I https://api.ascs.sinica.edu.tw/main/assets/index-*.js | rg -i 'content-security-policy'
```

測試續約：
```bash
sudo certbot renew --dry-run
```

## 12. 驗收清單

- `https://api.ascs.sinica.edu.tw/main/` 可開啟前端
- `https://api.ascs.sinica.edu.tw/main/docs` 可開啟 OpenAPI
- `https://api.ascs.sinica.edu.tw/main/login` 可進入 OAuth 流程
- `curl -I https://api.ascs.sinica.edu.tw/main/` 可看到完整 `Content-Security-Policy`，而非只有 `upgrade-insecure-requests`
- `sudo systemctl status as-api-console` 為 `active (running)`
- `sudo systemctl status nginx` 為 `active (running)`
- `sudo certbot renew --dry-run` 成功

## 13. 常用維運指令

一鍵部署（來源在 root 目錄，不處理 apt / git；搬遷到 `/home/app` 後安裝 backend 套件、frontend install+build、migration 到 head，並自動補齊缺少 crontab）：
```bash
git clone <YOUR_REPO_URL> /root/AS-API-Console
```

再執行：
```bash
bash scripts/deploy_full.sh
```

目錄處理流程：
- 若 `/home/app/AS-API-Console` 已存在，會先備份為 `/home/app/AS-API-Console_YYYYMMDD_HHMMSS.tar.gz`
- 每次部署會帶時間戳產生新備份（同秒重跑才可能同名）
- 備份成功後才刪除舊的 `/home/app/AS-API-Console`
- 將 `--source-dir` 指定的 root clone 來源目錄複製到 `/home/app/AS-API-Console`
- 切換目錄權限為 `asapic:asapic`
- 安裝與設定步驟都成功後，最後才清理 `--source-dir` 指定的 clone 來源目錄

目前腳本的 `ENV_FILE` 決策：
- 優先使用 `ENV_FILE=/home/app/config/.env`
- 若該檔不存在，自動 fallback 使用 `/home/app/AS-API-Console/backend/.env`
- 若兩者都不存在，腳本會直接失敗並提示先建立環境檔
- 每次執行都會重建 `backend/.venv`（`python3 -m venv .venv`）後再安裝 `requirements.txt`
- 每次執行都會執行 frontend `npm install` 後接 `npm run build`
- crontab 除了補齊缺少項目，也會自動將舊版（未帶 `ENV_FILE`）排程行替換為新版
  - 新版 crontab 會寫入本次「實際解析後」的 `ENV_FILE` 路徑

可選參數：
```bash
bash scripts/deploy_full.sh --source-dir /root/AS-API-Console
bash scripts/deploy_full.sh --source-dir /root/AS-API-Console --deploy-user asapic
bash scripts/deploy_full.sh --source-dir /root/AS-API-Console --app-dir /home/app/AS-API-Console
```

可用以下指令確認本次部署使用的環境檔：
```bash
sudo -u asapic crontab -l | rg 'ENV_FILE='
```

DB migration 指令與 revision 判讀規則請以 `docs/runbook-db.md` 為準。

完成後請手動重啟服務：
```bash
sudo systemctl restart as-api-console
```

重啟服務：
```bash
sudo systemctl restart as-api-console
sudo systemctl reload nginx
```

更新程式（手動）：
```bash
sudo -u asapic -H bash -lc '
cd /home/app/AS-API-Console
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

若 backend 未啟動，優先修正實際生效的 `ENV_FILE`（可能是 `/home/app/config/.env` 或 fallback 的 `backend/.env`）與 DB 連線問題。

### 14.2 `/main/docs` 可開但首頁空白

通常是前端 build 未產生或路徑錯誤：
```bash
sudo -u asapic -H bash -lc 'cd /home/app/AS-API-Console/frontend && npm run build'
sudo systemctl restart as-api-console
```

### 14.3 Alembic migration 失敗

確認實際生效的 `ENV_FILE` 中 DB 參數或 `DATABASE_URL` 正確，並檢查 MariaDB 使用者權限（可先用 `sudo -u asapic crontab -l | rg 'ENV_FILE='` 檢查）。

### 14.4 HTTPS 申請失敗

- 確認網域 DNS 已正確指向主機
- 確認 `80/443` 對外可連
- 確認 Nginx `server_name` 與申請網域一致

### 14.5 `Invalid host header`

症狀：
- 開啟 `https://api.ascs.sinica.edu.tw/main/` 出現 `Invalid host header`

常見原因：
- HTTPS (`443`) 的 `location /main/` 被導到前端開發伺服器（例如 `127.0.0.1:5173`）而非 backend `127.0.0.1:8000`。

定位步驟：
```bash
sudo nginx -T | sed -n '/server_name api.ascs.sinica.edu.tw/,/}/p'
sudo ss -ltnp | rg ':80|:443|:8000|:5173'
curl -kI https://api.ascs.sinica.edu.tw/main/
curl -I http://127.0.0.1:8000/main/
```

修復方式（確保 `80` 與 `443` 的 `/main/` 都一致）：
```nginx
location /main/ {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;

    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

套用後驗證：
```bash
sudo nginx -t
sudo systemctl reload nginx
curl -kI https://api.ascs.sinica.edu.tw/main/
curl -kI https://api.ascs.sinica.edu.tw/main/docs
```

### 14.6 CSP 掃描顯示缺少必要指令

症狀：
- 弱點掃描顯示「從 CSP 中缺少必要的指令」
- `/main/` 或 `/main/assets/*.js` 的回應只看到 `Content-Security-Policy: upgrade-insecure-requests`

定位步驟：
```bash
curl -kI https://api.ascs.sinica.edu.tw/main/
curl -kI https://api.ascs.sinica.edu.tw/main/assets/index-<hash>.js
sudo nginx -T | sed -n '/server_name api.ascs.sinica.edu.tw/,/}/p'
sudo rg -n "Content-Security-Policy|as-api-console-security-headers" /etc/nginx
```

常見原因：
- 只在某一個 server block 設定 CSP，導致 `80` 與 `443` 行為不一致
- Certbot 改寫 `443` server block 後，漏掉共用 security headers snippet
- 只保留 `upgrade-insecure-requests`，沒有 `default-src`、`script-src`、`style-src` 等主要 directive

修復方式：
- 確認 `80` 與 `443` 的站台設定都 `include /etc/nginx/snippets/as-api-console-security-headers.conf;`
- 重新載入 Nginx 並再次檢查 response headers

套用後驗證：
```bash
sudo nginx -t
sudo systemctl reload nginx
curl -kI https://api.ascs.sinica.edu.tw/main/ | rg -i 'content-security-policy|x-frame-options|strict-transport-security'
curl -kI https://api.ascs.sinica.edu.tw/main/assets/index-<hash>.js | rg -i 'content-security-policy'
```

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
User=asapic
Group=asapic
WorkingDirectory=/home/app/AS-API-Console/backend
Environment=ENV_FILE=/home/app/config/.env
ExecStart=/home/app/AS-API-Console/backend/scripts/run_expire_sync.sh
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
sudo -u asapic tail -n 100 /home/app/log/sync_expired_api_keys/$(TZ=Asia/Taipei date +%F).log
```

### 16.2 方案 B：cron

以 `asapic` 使用者設定 crontab：
```bash
sudo -u asapic crontab -e
```

加入：
```cron
10 0 * * * ENV_FILE=/home/app/config/.env /home/app/AS-API-Console/backend/scripts/run_expire_sync.sh
```

檢查：
```bash
sudo -u asapic crontab -l
sudo -u asapic tail -n 100 /home/app/log/sync_expired_api_keys/$(TZ=Asia/Taipei date +%F).log
```

說明：
- 回填腳本會自行寫入專案根目錄 `log/sync_expired_api_keys/`，以 `Asia/Taipei` 切日並採 `YYYY-MM-DD.log` 每日一檔。
- 建議保留 cron 預設 stdout/stderr 行為（系統郵件或平台收集）；業務執行紀錄以上述檔案為主。

### 16.3 排錯重點
- `.env` 未設定或 DB 參數錯誤：確認 `/home/app/config/.env` 內容。
- 執行環境找不到 `uv`：腳本會自動 fallback 到 `.venv/bin/python` 或 `python`，但仍需先安裝依賴。
- 權限問題：確認 `asapic` 對專案目錄可讀執行，且可連線 DB。

### 16.4 驗證清單（建議）
1. 檢查排程已啟用：
```bash
sudo systemctl list-timers as-api-expire-sync.timer --all
sudo -u asapic crontab -l
```
2. 手動 dry-run：
```bash
sudo -u asapic -H bash -lc 'cd /home/app/AS-API-Console/backend && ENV_FILE=/home/app/config/.env ./scripts/run_expire_sync.sh --dry-run'
```
3. 檢查當日日誌：
```bash
sudo -u asapic tail -n 100 /home/app/log/sync_expired_api_keys/$(TZ=Asia/Taipei date +%F).log
```

## 16A. API Key Usage Sync 排程部署

usage sync 採本地 snapshot 歷史表策略：
- 對外列表與 health status 讀取本地最新 snapshot，不在 request path 即時打 provider。
- 透過排程執行 `backend/scripts/run_usage_sync.sh`，每 `5` 分鐘以 `key_alias` 查 provider `/spend/logs/v2` 並寫回本地。

### 16A.1 方案 A（建議）：systemd timer

建立 `/etc/systemd/system/as-api-usage-sync.service`：
```ini
[Unit]
Description=AS API Console API Key Usage Sync
After=network.target mariadb.service

[Service]
Type=oneshot
User=asapic
Group=asapic
WorkingDirectory=/home/app/AS-API-Console/backend
Environment=ENV_FILE=/home/app/config/.env
ExecStart=/home/app/AS-API-Console/backend/scripts/run_usage_sync.sh
```

建立 `/etc/systemd/system/as-api-usage-sync.timer`：
```ini
[Unit]
Description=Run API key usage sync every 5 minutes

[Timer]
OnCalendar=*:0/5
Persistent=true
Unit=as-api-usage-sync.service

[Install]
WantedBy=timers.target
```

啟用與驗證：
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now as-api-usage-sync.timer
sudo systemctl list-timers as-api-usage-sync.timer --all
sudo systemctl status as-api-usage-sync.timer --no-pager
```

手動觸發與看 log：
```bash
sudo systemctl start as-api-usage-sync.service
sudo journalctl -u as-api-usage-sync.service -n 200 --no-pager
sudo -u asapic tail -n 100 /home/app/log/sync_api_key_usage/$(TZ=Asia/Taipei date +%F).log
```

### 16A.2 方案 B：cron

以 `asapic` 使用者設定 crontab：
```bash
sudo -u asapic crontab -e
```

加入：
```cron
*/5 * * * * ENV_FILE=/home/app/config/.env /home/app/AS-API-Console/backend/scripts/run_usage_sync.sh
```

檢查：
```bash
sudo -u asapic crontab -l
sudo -u asapic tail -n 100 /home/app/log/sync_api_key_usage/$(TZ=Asia/Taipei date +%F).log
```

### 16A.3 驗證清單（建議）
1. 檢查排程已啟用：
```bash
sudo systemctl list-timers as-api-usage-sync.timer --all
sudo -u asapic crontab -l
```
2. 手動 dry-run：
```bash
sudo -u asapic -H bash -lc 'cd /home/app/AS-API-Console/backend && ENV_FILE=/home/app/config/.env ./scripts/run_usage_sync.sh --dry-run'
```
3. 檢查當日日誌：
```bash
sudo -u asapic tail -n 100 /home/app/log/sync_api_key_usage/$(TZ=Asia/Taipei date +%F).log
```

## 17. 單位主檔同步排程部署

單位主檔同步採背景差異同步模式：
- 資料來源：`Persnl.getInstitutes`
- 執行腳本：`backend/scripts/sync_institutes.py`
- 建議頻率：每日 `00:20`（與 expired 回填 `00:10` 錯峰）

### 17.1 方案 A（建議）：systemd timer

建立 `/etc/systemd/system/as-api-institute-sync.service`：
```ini
[Unit]
Description=AS API Console Institute Master Sync
After=network.target mariadb.service

[Service]
Type=oneshot
User=asapic
Group=asapic
WorkingDirectory=/home/app/AS-API-Console/backend
Environment=ENV_FILE=/home/app/config/.env
ExecStart=/home/app/AS-API-Console/backend/.venv/bin/python /home/app/AS-API-Console/backend/scripts/sync_institutes.py
```

建立 `/etc/systemd/system/as-api-institute-sync.timer`：
```ini
[Unit]
Description=Run institute master sync daily at 00:20

[Timer]
OnCalendar=*-*-* 00:20:00
Persistent=true
Unit=as-api-institute-sync.service

[Install]
WantedBy=timers.target
```

啟用與驗證：
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now as-api-institute-sync.timer
sudo systemctl list-timers as-api-institute-sync.timer --all
sudo systemctl status as-api-institute-sync.timer --no-pager
```

手動觸發與看 log：
```bash
sudo systemctl start as-api-institute-sync.service
sudo journalctl -u as-api-institute-sync.service -n 200 --no-pager
```

### 17.2 方案 B：cron

以 `asapic` 使用者設定 crontab：
```bash
sudo -u asapic crontab -e
```

加入：
```cron
20 0 * * * ENV_FILE=/home/app/config/.env /home/app/AS-API-Console/backend/scripts/run_institute_sync.sh
```

檢查：
```bash
sudo -u asapic crontab -l
```

### 17.3 排錯重點
- OAuth/SOAP 登入失敗：檢查 `/home/app/config/.env` 內 SOAP/OAuth 相關設定與可連線性。
- 外部服務不可用：若 `Persnl.getInstitutes` timeout/5xx，腳本會失敗退出，請先確認外部服務狀態。
- DB 連線錯誤：確認 `DB_*` 或 `DATABASE_URL` 設定與 MariaDB 權限。
- Python/venv 路徑錯誤：確認 `.venv` 已建立且依賴已安裝。

### 17.4 驗證清單（建議）
1. 檢查排程已啟用：
```bash
sudo systemctl list-timers as-api-institute-sync.timer --all
sudo -u asapic crontab -l
```
2. 手動 dry-run：
```bash
sudo -u asapic -H bash -lc 'cd /home/app/AS-API-Console/backend && ENV_FILE=/home/app/config/.env . .venv/bin/activate && ENV_FILE=/home/app/config/.env python scripts/sync_institutes.py --dry-run'
```
3. 若出現 `persnl soap is not configured`，先補齊 `/home/app/config/.env` 的 `PERSNL_SOAP_URL` 或 `PERSNL_SOAP_WSDL_URL`，以及 `PERSNL_SOAP_USER`、`PERSNL_SOAP_PASSWORD`。
4. 實際同步一次：
```bash
sudo -u asapic -H bash -lc 'cd /home/app/AS-API-Console/backend && ENV_FILE=/home/app/config/.env . .venv/bin/activate && ENV_FILE=/home/app/config/.env python scripts/sync_institutes.py'
```

## 18. API Key 到期提醒寄信排程部署

到期提醒寄信採背景排程模式：
- 執行腳本：`backend/scripts/run_expiration_reminder.sh`
- 處理時段：單次執行同時處理 `30|14|7|3|1` 天全部提醒時段
- 建議頻率：每日 `08:30`、`12:30`、`16:30`
- 部署原則：維持單一排程入口，不依提醒天數拆分多個 service、timer 或 cron job

### 18.1 方案 A（建議）：systemd timer

建立 `/etc/systemd/system/as-api-expiration-reminder.service`：
```ini
[Unit]
Description=AS API Console Expiration Reminder Mailer
After=network.target mariadb.service

[Service]
Type=oneshot
User=asapic
Group=asapic
WorkingDirectory=/home/app/AS-API-Console/backend
Environment=ENV_FILE=/home/app/config/.env
ExecStart=/home/app/AS-API-Console/backend/scripts/run_expiration_reminder.sh
```

建立 `/etc/systemd/system/as-api-expiration-reminder.timer`：
```ini
[Unit]
Description=Run API key expiration reminder mailer three times daily

[Timer]
OnCalendar=*-*-* 08:30:00
OnCalendar=*-*-* 12:30:00
OnCalendar=*-*-* 16:30:00
Persistent=true
Unit=as-api-expiration-reminder.service

[Install]
WantedBy=timers.target
```

啟用與驗證：
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now as-api-expiration-reminder.timer
sudo systemctl list-timers as-api-expiration-reminder.timer --all
sudo systemctl status as-api-expiration-reminder.timer --no-pager
```

手動觸發與看 log：
```bash
sudo systemctl start as-api-expiration-reminder.service
sudo journalctl -u as-api-expiration-reminder.service -n 200 --no-pager
sudo -u asapic tail -n 100 /home/app/log/send_expiration_reminders/$(TZ=Asia/Taipei date +%F).log
```

### 18.2 方案 B：cron

以 `asapic` 使用者設定 crontab：
```bash
sudo -u asapic crontab -e
```

加入：
```cron
30 8,12,16 * * * ENV_FILE=/home/app/config/.env /home/app/AS-API-Console/backend/scripts/run_expiration_reminder.sh
```

檢查：
```bash
sudo -u asapic crontab -l
sudo -u asapic tail -n 100 /home/app/log/send_expiration_reminders/$(TZ=Asia/Taipei date +%F).log
```

### 18.3 排錯重點
- `MAIL_ENABLED` 不是 `true`：會略過寄信；請檢查 `/home/app/config/.env`。
- SMTP 參數缺失：檢查 `MAIL_SERVER`、`MAIL_PORT` 與帳密設定；寄件者地址固定為 `noreply@as.edu.tw`。
- 執行環境找不到 `uv`：腳本會自動 fallback 到 `.venv/bin/python` 或 `python`，但仍需先安裝依賴。
- 若查無資料寄送：先以 `--dry-run` 檢查是否有命中任一 `30|14|7|3|1` 提醒時段的 `active` 資料。
- 若只收到部分提醒：確認 `api_key_expiration_notices` 是否已有該 key、該輪 `expires_at`、該提醒時段的成功紀錄；同時段成功紀錄存在時不應重寄。

### 18.4 驗證清單（建議）
1. 檢查排程已啟用：
```bash
sudo systemctl list-timers as-api-expiration-reminder.timer --all
sudo -u asapic crontab -l
```
2. 手動 dry-run：
```bash
sudo -u asapic -H bash -lc 'cd /home/app/AS-API-Console/backend && ENV_FILE=/home/app/config/.env ./scripts/run_expiration_reminder.sh --dry-run'
```
   - 預期：輸出會反映是否命中任一 `30|14|7|3|1` 提醒時段，不限於 30 天。
3. 檢查當日日誌：
```bash
sudo -u asapic tail -n 100 /home/app/log/send_expiration_reminders/$(TZ=Asia/Taipei date +%F).log
```
4. 若需手動驗證正式寄送：
```bash
sudo systemctl start as-api-expiration-reminder.service
```
   - 預期：同一次執行會處理全部提醒時段；郵件主旨或內容需顯示正確剩餘天數。

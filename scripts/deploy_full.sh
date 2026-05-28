#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

usage() {
  cat <<'USAGE'
Usage: bash scripts/deploy_full.sh [options]

Options:
  --deploy-user <user>  User for crontab check/update (default: aspaic)
  --app-dir <path>      Application directory (default: /home/app/AI-API-Console)
  -h, --help            Show this help message
USAGE
}

DEPLOY_USER="aspaic"
APP_DIR="/home/app/AI-API-Console"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --deploy-user)
      DEPLOY_USER="$2"
      shift 2
      ;;
    --app-dir)
      APP_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if ! command -v sudo >/dev/null 2>&1; then
  echo "sudo is required." >&2
  exit 1
fi

if [[ ! -d "$APP_DIR/backend" || ! -d "$APP_DIR/frontend" ]]; then
  echo "Invalid app directory: $APP_DIR" >&2
  echo "Expected backend/ and frontend/ under app directory." >&2
  exit 1
fi

log "Installing backend dependencies"
sudo -u "$DEPLOY_USER" -H bash -lc "
set -euo pipefail
cd '$APP_DIR/backend'
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
"

log "Installing frontend dependencies"
sudo -u "$DEPLOY_USER" -H bash -lc "
set -euo pipefail
cd '$APP_DIR/frontend'
npm install
"

log "Running database migration to head"
sudo -u "$DEPLOY_USER" -H bash -lc "
set -euo pipefail
cd '$APP_DIR/backend'
. .venv/bin/activate
alembic upgrade head
alembic current
"

log "Checking and updating crontab entries"
EXPIRE_JOB="10 0 * * * ${APP_DIR}/backend/scripts/run_expire_sync.sh"
INSTITUTE_JOB="20 0 * * * cd ${APP_DIR}/backend && . .venv/bin/activate && python scripts/sync_institutes.py"
REMINDER_JOB="30 0 * * * ${APP_DIR}/backend/scripts/run_expiration_reminder.sh"

CURRENT_CRON="$(sudo -u "$DEPLOY_USER" crontab -l 2>/dev/null || true)"
UPDATED_CRON="$CURRENT_CRON"
ADDED=()

ensure_job() {
  local job="$1"
  if ! printf '%s\n' "$UPDATED_CRON" | grep -F -x "$job" >/dev/null 2>&1; then
    if [[ -n "$UPDATED_CRON" ]]; then
      UPDATED_CRON+=$'\n'
    fi
    UPDATED_CRON+="$job"
    ADDED+=("$job")
  fi
}

ensure_job "$EXPIRE_JOB"
ensure_job "$INSTITUTE_JOB"
ensure_job "$REMINDER_JOB"

if [[ "${#ADDED[@]}" -gt 0 ]]; then
  printf '%s\n' "$UPDATED_CRON" | sudo -u "$DEPLOY_USER" crontab -
  log "Added missing crontab entries (${#ADDED[@]})"
else
  log "All required crontab entries already exist"
fi

log "Deployment flow completed"
cat <<DONE

Completed steps:
- Backend dependencies installed
- Frontend dependencies installed
- Alembic upgraded to head
- Crontab checked and updated for missing jobs

Crontab target user: $DEPLOY_USER
App directory: $APP_DIR

Entries added this run:
$(if [[ "${#ADDED[@]}" -eq 0 ]]; then echo '- none'; else printf -- '- %s\n' "${ADDED[@]}"; fi)
DONE

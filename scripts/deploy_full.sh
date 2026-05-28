#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

usage() {
  cat <<'USAGE'
Usage: bash scripts/deploy_full.sh [options]

Options:
  --deploy-user <user>  User for crontab check/update (default: asapic)
  --app-dir <path>      Application directory (default: /home/app/AS-API-Console)
  -h, --help            Show this help message
USAGE
}

DEPLOY_USER="asapic"
APP_DIR="/home/app/AS-API-Console"
ENV_FILE_PATH="/home/app/config/.env"

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
EXPIRE_JOB="10 0 * * * ENV_FILE=${ENV_FILE_PATH} ${APP_DIR}/backend/scripts/run_expire_sync.sh"
INSTITUTE_JOB="20 0 * * * cd ${APP_DIR}/backend && ENV_FILE=${ENV_FILE_PATH} . .venv/bin/activate && ENV_FILE=${ENV_FILE_PATH} python scripts/sync_institutes.py"
REMINDER_JOB="30 0 * * * ENV_FILE=${ENV_FILE_PATH} ${APP_DIR}/backend/scripts/run_expiration_reminder.sh"

LEGACY_EXPIRE_JOB="10 0 * * * ${APP_DIR}/backend/scripts/run_expire_sync.sh"
LEGACY_INSTITUTE_JOB="20 0 * * * cd ${APP_DIR}/backend && . .venv/bin/activate && python scripts/sync_institutes.py"
LEGACY_REMINDER_JOB="30 0 * * * ${APP_DIR}/backend/scripts/run_expiration_reminder.sh"

CURRENT_CRON="$(sudo -u "$DEPLOY_USER" crontab -l 2>/dev/null || true)"
UPDATED_CRON="$CURRENT_CRON"
ADDED=()
REPLACED=()

remove_job() {
  local job="$1"
  local new_cron
  new_cron="$(printf '%s\n' "$UPDATED_CRON" | grep -F -x -v "$job" || true)"
  UPDATED_CRON="$(printf '%s' "$new_cron" | sed '/^$/d')"
}

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

replace_legacy_job() {
  local legacy_job="$1"
  local new_job="$2"
  if printf '%s\n' "$UPDATED_CRON" | grep -F -x "$legacy_job" >/dev/null 2>&1; then
    remove_job "$legacy_job"
    ensure_job "$new_job"
    REPLACED+=("$legacy_job")
  fi
}

replace_legacy_job "$LEGACY_EXPIRE_JOB" "$EXPIRE_JOB"
replace_legacy_job "$LEGACY_INSTITUTE_JOB" "$INSTITUTE_JOB"
replace_legacy_job "$LEGACY_REMINDER_JOB" "$REMINDER_JOB"

ensure_job "$EXPIRE_JOB"
ensure_job "$INSTITUTE_JOB"
ensure_job "$REMINDER_JOB"

if [[ "${#ADDED[@]}" -gt 0 || "${#REPLACED[@]}" -gt 0 ]]; then
  printf '%s\n' "$UPDATED_CRON" | sudo -u "$DEPLOY_USER" crontab -
  log "Crontab updated (added=${#ADDED[@]}, replaced=${#REPLACED[@]})"
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
ENV_FILE path: $ENV_FILE_PATH

Entries added this run:
$(if [[ "${#ADDED[@]}" -eq 0 ]]; then echo '- none'; else printf -- '- %s\n' "${ADDED[@]}"; fi)

Legacy entries replaced this run:
$(if [[ "${#REPLACED[@]}" -eq 0 ]]; then echo '- none'; else printf -- '- %s\n' "${REPLACED[@]}"; fi)
DONE

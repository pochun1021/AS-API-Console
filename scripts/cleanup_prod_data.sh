#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: bash scripts/cleanup_prod_data.sh --confirm-wipe

Required:
  --confirm-wipe    Execute the cleanup. Without this flag, the script exits without changing data.

Environment:
  ENV_FILE          Optional env file path. Load order:
                    1. ENV_FILE
                    2. /home/app/config/.env
                    3. backend/.env
  DB_HOST           Database host
  DB_PORT           Database port (default: 3306)
  DB_USER           Database user
  DB_PASSWORD       Database password
  DB_NAME           Database name

This script deletes business data from the following tables:
  api_key_usage_snapshots
  api_key_expiration_notices
  api_keys
  api_key_applications
  api_key_whitelist
  announcements
  auth_audit_logs
  operation_audit_logs
  user_preferences

This script preserves the following tables:
  admins
  limit_strategy_config
  institutes
  institute_sync_control
USAGE
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 1
  fi
}

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required environment variable: $name" >&2
    exit 1
  fi
}

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

resolve_db_client() {
  if command -v mysql >/dev/null 2>&1; then
    printf '%s\n' "mysql"
    return
  fi
  if command -v mariadb >/dev/null 2>&1; then
    printf '%s\n' "mariadb"
    return
  fi

  echo "Required command not found: mysql or mariadb" >&2
  exit 1
}

resolve_env_file() {
  if [[ -n "${ENV_FILE:-}" ]]; then
    printf '%s\n' "$ENV_FILE"
    return
  fi

  if [[ -f "/home/app/config/.env" ]]; then
    printf '%s\n' "/home/app/config/.env"
    return
  fi

  local script_dir
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  local repo_root
  repo_root="$(dirname "$script_dir")"
  printf '%s\n' "$repo_root/backend/.env"
}

load_env_file() {
  local env_file_path="$1"
  if [[ ! -f "$env_file_path" ]]; then
    return
  fi

  log "Loading environment from $env_file_path"
  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ -z "$line" ]]; then
      continue
    fi
    if [[ "$line" =~ ^[[:space:]]*# ]]; then
      continue
    fi
    if [[ "$line" != *"="* ]]; then
      continue
    fi

    local key="${line%%=*}"
    local value="${line#*=}"

    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    value="${value#"${value%%[![:space:]]*}"}"
    value="${value%"${value##*[![:space:]]}"}"

    if [[ ! "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      continue
    fi

    if [[ "$value" =~ ^\".*\"$ ]]; then
      value="${value:1:${#value}-2}"
    elif [[ "$value" =~ ^\'.*\'$ ]]; then
      value="${value:1:${#value}-2}"
    fi

    export "$key=$value"
  done < "$env_file_path"
}

CONFIRMED="no"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --confirm-wipe)
      CONFIRMED="yes"
      shift
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

if [[ "$CONFIRMED" != "yes" ]]; then
  usage
  exit 1
fi

DB_CLIENT="$(resolve_db_client)"
RESOLVED_ENV_FILE="$(resolve_env_file)"
load_env_file "$RESOLVED_ENV_FILE"
require_env DB_HOST
require_env DB_USER
require_env DB_PASSWORD
require_env DB_NAME

DB_PORT="${DB_PORT:-3306}"

TARGET_TABLES=(
  "api_key_usage_snapshots"
  "api_key_expiration_notices"
  "api_keys"
  "api_key_applications"
  "api_key_whitelist"
  "announcements"
  "auth_audit_logs"
  "operation_audit_logs"
  "user_preferences"
)

PRESERVED_TABLES=(
  "admins"
  "limit_strategy_config"
  "institutes"
  "institute_sync_control"
)

COUNTS_SQL=$(cat <<'SQL'
SELECT 'api_key_usage_snapshots' AS table_name, COUNT(*) AS row_count FROM api_key_usage_snapshots
UNION ALL
SELECT 'api_key_expiration_notices' AS table_name, COUNT(*) AS row_count FROM api_key_expiration_notices
UNION ALL
SELECT 'api_keys' AS table_name, COUNT(*) AS row_count FROM api_keys
UNION ALL
SELECT 'api_key_applications' AS table_name, COUNT(*) AS row_count FROM api_key_applications
UNION ALL
SELECT 'api_key_whitelist' AS table_name, COUNT(*) AS row_count FROM api_key_whitelist
UNION ALL
SELECT 'announcements' AS table_name, COUNT(*) AS row_count FROM announcements
UNION ALL
SELECT 'auth_audit_logs' AS table_name, COUNT(*) AS row_count FROM auth_audit_logs
UNION ALL
SELECT 'operation_audit_logs' AS table_name, COUNT(*) AS row_count FROM operation_audit_logs
UNION ALL
SELECT 'user_preferences' AS table_name, COUNT(*) AS row_count FROM user_preferences
UNION ALL
SELECT 'admins' AS table_name, COUNT(*) AS row_count FROM admins
UNION ALL
SELECT 'limit_strategy_config' AS table_name, COUNT(*) AS row_count FROM limit_strategy_config
UNION ALL
SELECT 'institutes' AS table_name, COUNT(*) AS row_count FROM institutes
UNION ALL
SELECT 'institute_sync_control' AS table_name, COUNT(*) AS row_count FROM institute_sync_control;
SQL
)

CLEANUP_SQL=$(cat <<'SQL'
SET FOREIGN_KEY_CHECKS = 0;
DELETE FROM api_key_usage_snapshots;
DELETE FROM api_key_expiration_notices;
UPDATE api_keys
SET renewed_to_key_id = NULL
WHERE renewed_to_key_id IS NOT NULL;
DELETE FROM api_keys;
DELETE FROM api_key_applications;
DELETE FROM api_key_whitelist;
DELETE FROM announcements;
DELETE FROM auth_audit_logs;
DELETE FROM operation_audit_logs;
DELETE FROM user_preferences;
SET FOREIGN_KEY_CHECKS = 1;
SQL
)

run_sql() {
  local sql="$1"
  local args=(
    --user="$DB_USER"
    --database="$DB_NAME"
    --batch
    --raw
    --skip-column-names
    -e "$sql"
  )

  if [[ "${DB_HOST}" != "localhost" ]]; then
    args=(
      --host="$DB_HOST"
      --port="$DB_PORT"
      "${args[@]}"
    )
  fi

  MYSQL_PWD="$DB_PASSWORD" "$DB_CLIENT" "${args[@]}"
}

log "Cleanup target tables:"
printf '  %s\n' "${TARGET_TABLES[@]}"
log "Preserved tables:"
printf '  %s\n' "${PRESERVED_TABLES[@]}"

log "Row counts before cleanup"
BEFORE_COUNTS="$(run_sql "$COUNTS_SQL")"
printf '%s\n' "$BEFORE_COUNTS"

log "Deleting business data"
run_sql "$CLEANUP_SQL"

log "Row counts after cleanup"
AFTER_COUNTS="$(run_sql "$COUNTS_SQL")"
printf '%s\n' "$AFTER_COUNTS"

admins_before="$(printf '%s\n' "$BEFORE_COUNTS" | awk -F '\t' '$1 == "admins" { print $2 }')"
admins_after="$(printf '%s\n' "$AFTER_COUNTS" | awk -F '\t' '$1 == "admins" { print $2 }')"

if [[ "$admins_before" != "$admins_after" ]]; then
  echo "Validation failed: expected admins row count to remain unchanged, got before=${admins_before} after=${admins_after}" >&2
  exit 1
fi

for table_name in "${TARGET_TABLES[@]}"; do
  row_count="$(printf '%s\n' "$AFTER_COUNTS" | awk -F '\t' -v table_name="$table_name" '$1 == table_name { print $2 }')"
  if [[ "$row_count" != "0" ]]; then
    echo "Validation failed: expected ${table_name} to be empty, got ${row_count}" >&2
    exit 1
  fi
done

log "Cleanup completed successfully. Preserved table admins was not modified."

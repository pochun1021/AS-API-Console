#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
PY_SCRIPT="scripts/test_provider_connectivity.py"
ENV_PATH=""

load_env_file() {
  local file_path="$1"
  local line
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    if [[ "$line" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]]; then
      export "$line"
    fi
  done < "$file_path"
}

if [[ ! -f "${BACKEND_DIR}/${PY_SCRIPT}" ]]; then
  echo "[FAIL] cannot find ${BACKEND_DIR}/${PY_SCRIPT}" >&2
  exit 1
fi

# Load env vars in project-standard order:
# 1) ENV_FILE (if set and exists)
# 2) /home/app/config/.env
# 3) backend/.env
if [[ -n "${ENV_FILE:-}" && -f "${ENV_FILE}" ]]; then
  ENV_PATH="${ENV_FILE}"
elif [[ -f "/home/app/config/.env" ]]; then
  ENV_PATH="/home/app/config/.env"
elif [[ -f "${BACKEND_DIR}/.env" ]]; then
  ENV_PATH="${BACKEND_DIR}/.env"
fi

if [[ -n "${ENV_PATH}" ]]; then
  load_env_file "${ENV_PATH}"
  echo "[INFO] env file used: ${ENV_PATH}"
else
  echo "[INFO] env file used: none"
fi

cd "${BACKEND_DIR}"

if [[ -x "${BACKEND_DIR}/.venv/bin/python" ]]; then
  echo "[INFO] python runtime: ${BACKEND_DIR}/.venv/bin/python"
  exec "${BACKEND_DIR}/.venv/bin/python" "${PY_SCRIPT}"
fi

if command -v uv >/dev/null 2>&1; then
  echo "[INFO] python runtime: uv run python"
  exec uv run python "${PY_SCRIPT}"
fi

echo "[INFO] python runtime: python3"
exec python3 "${PY_SCRIPT}"

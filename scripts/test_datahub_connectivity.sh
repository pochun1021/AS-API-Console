#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/../backend" && pwd)"
PY_MODULE="scripts.test_datahub_connectivity"

# Settings reads ENV_FILE, then the deployment file, then backend/.env.
if [[ -n "${ENV_FILE:-}" ]]; then
  if [[ ! -f "${ENV_FILE}" ]]; then
    echo "[FAIL] ENV_FILE does not exist" >&2
    exit 1
  fi
  echo "[INFO] env file used: ${ENV_FILE}"
elif [[ -f /home/app/config/.env ]]; then
  echo "[INFO] env file used: /home/app/config/.env"
elif [[ -f "${BACKEND_DIR}/.env" ]]; then
  echo "[INFO] env file used: ${BACKEND_DIR}/.env"
else
  echo "[INFO] env file used: none"
fi

cd "${BACKEND_DIR}"
if [[ -x .venv/bin/python ]]; then
  exec .venv/bin/python -m "${PY_MODULE}" "$@"
elif command -v uv >/dev/null 2>&1; then
  exec uv run python -m "${PY_MODULE}" "$@"
else
  exec python3 -m "${PY_MODULE}" "$@"
fi

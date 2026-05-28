#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${BACKEND_DIR}"

ENV_PATH="${ENV_FILE:-.env}"
if [[ -f "${ENV_PATH}" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ENV_PATH}"
  set +a
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run python scripts/sync_expired_api_keys.py "$@"
fi

if [[ -x ".venv/bin/python" ]]; then
  exec .venv/bin/python scripts/sync_expired_api_keys.py "$@"
fi

exec python scripts/sync_expired_api_keys.py "$@"

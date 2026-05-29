#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKEND_DIR="${REPO_ROOT}/backend"
PY_SCRIPT="scripts/test_persnl_connectivity.py"

if [[ ! -f "${BACKEND_DIR}/${PY_SCRIPT}" ]]; then
  echo "[FAIL] cannot find ${BACKEND_DIR}/${PY_SCRIPT}" >&2
  exit 1
fi

if [[ "$#" -gt 0 ]]; then
  echo "[FAIL] this script does not accept arguments" >&2
  exit 1
fi

cd "${BACKEND_DIR}"

if command -v uv >/dev/null 2>&1; then
  export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
  exec uv run python "${PY_SCRIPT}"
fi

exec python3 "${PY_SCRIPT}"

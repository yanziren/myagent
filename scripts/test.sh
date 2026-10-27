#!/usr/bin/env bash
# Create .venv if needed, editable-install claimdesk + pytest, run tests.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON=""
for candidate in python3.12 python3.13 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo "error: no python3 found" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  echo "Creating .venv with $PYTHON ..."
  "$PYTHON" -m venv .venv
fi

PY=".venv/bin/python"
PIP=".venv/bin/pip"

"$PIP" install -U pip -q
"$PIP" install -e . pytest -q

echo "Running pytest ${*:-tests/ -v}"
exec .venv/bin/pytest "${@:-tests/}" -v

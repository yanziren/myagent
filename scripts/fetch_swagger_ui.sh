#!/usr/bin/env bash
# Swagger UI assets for /docs when CDN (jsdelivr) is unreachable.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="$ROOT/claimdesk/api/static/swagger-ui"
VER="${SWAGGER_UI_VERSION:-5.11.0}"
mkdir -p "$DIR"
BASE="https://unpkg.com/swagger-ui-dist@${VER}"
curl -fsSL -o "$DIR/swagger-ui-bundle.js" "${BASE}/swagger-ui-bundle.js"
curl -fsSL -o "$DIR/swagger-ui.css" "${BASE}/swagger-ui.css"
echo "OK: $DIR"

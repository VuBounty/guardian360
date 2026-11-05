#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
"$ROOT/backend/.venv/bin/python" -m pytest -q backend/tests qa/test_analytics_integration.py qa/test_public_api.py qa/test_asset_v25.py qa/test_asset_v25_rc1.py
"$ROOT/backend/.venv/bin/python" -m compileall -q backend/main.py backend/forensic.py backend/asset_valuation.py backend/public_api.py backend/revoke_engine.py backend/analytics.py
if ! command -v node >/dev/null 2>&1; then echo "BLOCK: Node.js required" >&2; exit 2; fi
if command -v node >/dev/null 2>&1; then
 for file in docs/app.js docs/revoke.js docs/config.js docs/analytics.js docs/admin.js docs/readability.js; do node --check "$file"; done
 node qa/test_v25_rc1_ui.cjs
fi
"$ROOT/backend/.venv/bin/python" qa/check_english_release.py

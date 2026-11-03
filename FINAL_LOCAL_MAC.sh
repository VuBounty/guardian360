#!/bin/zsh
# FINAL ONE-PASS QA + START; only local UI/API; no testnet wallet signing.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
mkdir -p .local
chmod 700 .local
if [[ ! -s .local/admin-key.txt ]]; then
  python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > .local/admin-key.txt
  chmod 600 .local/admin-key.txt
fi
export GUARDIAN_ANALYTICS_ADMIN_KEY="$(cat .local/admin-key.txt)"
export CORS_ORIGINS='http://127.0.0.1:5173,http://localhost:5173'
for port in 8000 5173; do
 if lsof -nP -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $port is occupied. Stop that existing GUARDIAN Terminal with Control+C, then run this command again."; exit 1
 fi
done
chmod +x INSTALL_MAC.sh
./INSTALL_MAC.sh
if [[ ! -f .local/final-qa-passed ]]; then
 echo 'Running consolidated offline QA (once for this release)...'
 chmod +x qa/run_final_qa.sh
 ./qa/run_final_qa.sh 2>&1 | tee .local/qa-once.log
 touch .local/final-qa-passed
else
 echo 'Consolidated QA previously passed for this unchanged release. Skipping repeat.'
fi
(
 cd backend
 exec "$ROOT/backend/.venv/bin/python" -m uvicorn main:app --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!
cleanup(){ kill "$BACKEND_PID" 2>/dev/null || true; wait "$BACKEND_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
# Verify startup by checking actual HTTP health instead of a blind sleep.
"$ROOT/backend/.venv/bin/python" - <<'PYWAIT'
import time,urllib.request
for _ in range(35):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1) as response:
            if response.status==200:break
    except Exception: time.sleep(0.2)
else: raise SystemExit('Backend did not become healthy; see Terminal output above.')
PYWAIT
printf '\nGUARDIAN 360 V2.4.2 // ENGLISH DEFAULT // LOCAL BETA // QA PASS\n'
printf 'UI: http://127.0.0.1:5173\nAPI: http://127.0.0.1:8000/api/health\nOwner analytics: http://127.0.0.1:5173/admin.html\n'
printf 'Source publication: ./PUBLISH_TO_VUBOUNTY.sh (requires gh auth)\n'
printf 'Real-wallet revoke transaction sending DISABLED pending testnet/security review.\n'
printf 'Press Control+C to stop all local services.\n\n'
python3 local_server.py

#!/bin/zsh
# GUARDIAN 360 V2.4.2 — QA exactly once, local health smoke, GitHub source publication.
# Does not send wallet transactions and does not deploy a public signing backend.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
mkdir -p .local
chmod 700 .local
if [[ ! -s .local/admin-key.txt ]]; then
  python3 -c 'import secrets;print(secrets.token_urlsafe(32))' > .local/admin-key.txt
  chmod 600 .local/admin-key.txt
fi
export GUARDIAN_ANALYTICS_ADMIN_KEY="$(cat .local/admin-key.txt)"
export CORS_ORIGINS='http://127.0.0.1:5173,http://localhost:5173'
for p in 8000 5173; do
  if lsof -nP -iTCP:$p -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $p is busy. Stop the older GUARDIAN server once with Control+C; then rerun."; exit 1
  fi
done
chmod +x INSTALL_MAC.sh
./INSTALL_MAC.sh
if [[ ! -f .local/final-qa-passed ]]; then
  echo 'Running consolidated QA once...'
  chmod +x qa/run_final_qa.sh
  ./qa/run_final_qa.sh 2>&1 | tee .local/qa-once.log
  touch .local/final-qa-passed
else
  echo 'QA marker found for this unchanged release: no repeat run.'
fi
(
  cd backend
  exec "$ROOT/backend/.venv/bin/python" -m uvicorn main:app --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!
python3 local_server.py &
FRONTEND_PID=$!
cleanup(){ kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true; wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM
"$ROOT/backend/.venv/bin/python" - <<'PYQA'
import urllib.request,time
for url,expected in [('http://127.0.0.1:8000/api/health',b''),('http://127.0.0.1:5173/',b'WALLET SECURITY OPERATIONS / V2.4.2')]:
    err=None
    for attempt in range(45):
        try:
            with urllib.request.urlopen(url,timeout=2) as res:
                text=res.read()
                if res.status!=200 or (expected and expected not in text):raise ValueError('Response invalid')
                if url.endswith('/'):
                    assert b'@SpaceAIFinance' in text
                    assert b'lang="en"' in text
                print('PASS',url)
                break
        except Exception as e: err=e;time.sleep(.2)
    else: raise SystemExit('FAIL '+url+' : '+str(err))
req=urllib.request.Request('http://127.0.0.1:8000/api/scan',method='OPTIONS',headers={'Origin':'http://127.0.0.1:5173','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
with urllib.request.urlopen(req,timeout=2) as res:
    assert res.status==200
    assert res.headers.get('Access-Control-Allow-Origin')=='http://127.0.0.1:5173'
print('PASS CORS preflight from trusted local UI')
PYQA
cleanup
trap - EXIT INT TERM
printf '\nFINAL LOCAL QA: PASS. Both test servers stopped cleanly.\n'
printf 'To use the local app later: ./FINAL_LOCAL_MAC.sh\n'
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  echo 'GitHub CLI is authenticated. Checking target account and publishing source code...'
  chmod +x PUBLISH_TO_VUBOUNTY.sh
  ./PUBLISH_TO_VUBOUNTY.sh
else
  echo 'PUBLICATION PENDING: GitHub CLI authentication is not yet available.'
  echo 'On Mac, run: brew install gh    (if needed)'
  echo 'Then:       gh auth login'
  echo 'Finally:    ./PUBLISH_TO_VUBOUNTY.sh'
  echo 'Do not paste GitHub tokens into chat.'
fi

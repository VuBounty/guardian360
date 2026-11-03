#!/bin/zsh
# Install missing dependencies only; QA is run by the finalization script once.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if [[ ! -x backend/.venv/bin/python ]]; then
  echo '[INSTALL] Creating Python environment'
  python3 -m venv backend/.venv
fi
if ! backend/.venv/bin/python -c 'import fastapi,uvicorn,httpx,pydantic,pytest,pytest_asyncio' >/dev/null 2>&1; then
  echo '[INSTALL] Installing missing Python packages (including pytest-asyncio)'
  backend/.venv/bin/python -m pip install -r backend/requirements.txt
else
  echo '[INSTALL] Python dependencies already available'
fi
chmod +x qa/run_final_qa.sh

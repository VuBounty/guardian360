#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
if ! command -v gh >/dev/null 2>&1; then
  echo 'GitHub CLI missing. On Mac: brew install gh && gh auth login'; exit 2
fi
if ! gh auth status >/dev/null 2>&1; then
  echo 'GitHub authorization is required. Run gh auth login yourself (never share tokens).'; exit 2
fi
LOGIN="$(gh api user --jq .login)"
if [[ "${LOGIN:l}" != "vubounty" ]]; then
  echo "Authenticated as $LOGIN, expected Vubounty. Aborting to prevent publishing in the wrong account."; exit 2
fi
if [[ -d .git ]]; then
  echo 'A Git repository already exists. Inspect before publishing; refusing to rewrite it.'; exit 2
fi
if gh repo view Vubounty/guardian360 >/dev/null 2>&1; then
  echo 'Vubounty/guardian360 already exists. Refusing to overwrite it automatically.'; exit 2
fi
# One last guard against accidental file inclusion.
if [[ -f .local/admin-key.txt || -f backend/data/analytics.db ]]; then
  echo 'Local private files exist. They are ignored by .gitignore; inspect git status before publishing.'
fi
git init -b main
git add .
if git diff --cached --name-only | grep -Eq '(^|/)(admin-key\.txt|analytics\.db|\.env$|bsc-live-results.*\.json)$'; then
  echo 'PRIVATE FILE DETECTED: refusing to commit.'; exit 2
fi
git commit -m 'GUARDIAN 360 V2.4.2: English-first security terminal, local beta QA'
gh repo create Vubounty/guardian360 --public --source=. --remote=origin --push
printf '\nSOURCE REPOSITORY CREATED.\nhttps://github.com/Vubounty/guardian360\n'
echo 'GitHub Pages is NOT automatically published. No live backend or public revoke is deployed.'

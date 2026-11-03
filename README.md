# GUARDIAN 360 — V2.4.2 English Final Local Beta

**Blacksite / Retro DOS Security Terminal** by @SpaceAIFinance. The full UI is now English by default (`lang=en`), with browser-native translation available. **CSS layout and technical font remain unchanged.**

> **LOCAL BETA / NOT AUDITED. No successful live MetaMask revoke has been independently verified. Transaction submission is deliberately DISABLED (`GUARDIAN_ENABLE_REVOKE_TRANSACTIONS=false`).**

## One Mac command after download

Download `guardian360-v2.4.2-english-final.zip` to `~/Downloads`, then in Terminal:

```bash
cd ~/Myproject/GUARDIAN360 && unzip -o ~/Downloads/guardian360-v2.4.2-english-final.zip && cd guardian360-v2.4.2-english-final && chmod +x FINAL_LOCAL_MAC.sh && ./FINAL_LOCAL_MAC.sh
```

The command creates `.venv` if needed, installs dependencies, runs the consolidated offline QA **once** and starts API (127.0.0.1:8000) and UI (127.0.0.1:5173) in one terminal. It refuses to overwrite existing processes listening on those ports. Ctrl+C stops both. It never requests seed phrase/private keys.

- UI: http://127.0.0.1:5173
- API health: http://127.0.0.1:8000/api/health
- Analytics owner (local only): http://127.0.0.1:5173/admin.html
- Admin key remains in `.local/admin-key.txt` (never publish or paste online).

### Scope and important limitations

- Read-only scan: BNB Chain, Ethereum, Base and Arbitrum One. Incomplete indexes or RPC errors are labeled `INCOMPLETE`, **never SAFE**.
- Token catalog, NFT and historical ERC-20/Permit2 approvals are **not comprehensive**. `0 approvals found` does not mean `0 approvals exist`.
- Known MetaMask EIP-7702 delegation is classified informational, not an automatic compromise finding.
- Manual on-chain permission verification is available. Actual revoke submission is disabled until clean testnet E2E and independent review. No mainnet signing for QA.
- Analytics total scans is not unique people; unique-browser counts are opt-in and limited to that browser's pseudonym. Running on localhost does not measure community usage.

## GitHub repository: Vubounty/guardian360

Use `./FINALIZE_AND_PUBLISH_MAC.sh` to run the consolidated QA, perform a short local HTTP/CORS test, and then publish if the GitHub CLI is authenticated as Vubounty. Otherwise use `./PUBLISH_TO_VUBOUNTY.sh` after `gh auth login`. It creates a new public source repository if no repo exists. It will not force-push into an existing repo. The script does **not** publish a working public security scanner; GitHub Pages is static and does not run FastAPI or SQLite.

GitHub Pages is set to manual dispatch only, and contains an offline **source-preview** with disabled scan / wallet actions when no separate reviewed HTTPS backend is configured. Do not enable real signing or place any admin keys / API credentials in `docs/`.

### Publication gates

Public read-only scan: deploy reviewed HTTPS backend + per-origin CORS + rate limits + logging/privacy policy + validated approval-coverage claims. Public revoke: clean testnet transaction + receipt + recheck, wallet interaction checks, and independent security review.

## QA evidence

`QA_FINAL.md` documents one consolidated QA run and remaining blockers. `FINAL_LOCAL_MAC.sh` runs automated checks once per extracted release folder and saves their report to `.local/qa-once.log`. `./qa/run_final_qa.sh` is available to run explicitly if code changes.

© 2026 @SpaceAIFinance. All rights reserved. Code under MIT License; preserve license notice.

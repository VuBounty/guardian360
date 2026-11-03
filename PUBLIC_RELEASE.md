# GUARDIAN 360 — public read-only release package

**Status**: SOURCE READY / NOT DEPLOYED. It is not proof of an active public website.

* GitHub Pages static UI: `https://vubounty.github.io/guardian360/` (check GitHub Actions and HTTP response before claiming live).
* HTTPS API requires a Render account and explicit service creation from `render.yaml`. Nothing deploys automatically from this ZIP.
* API app: `backend/public_api.py`, limited to GET `/api/health`, GET `/api/chains`, POST `/api/scan`; never import or expose `main.app` in the public service.
* Default `GUARDIAN_PUBLIC_ENABLE_SCAN=false`. After backend HTTPS is reviewed and configured and tested, flip to `true` in Render environment and redeploy, then connect Pages with `SET_PUBLIC_API_MAC.sh`.
* No `/api/revoke/*` endpoints; no public wallet signing. Public Revoke tab is an informational disabled panel.
* Public analytics disabled until durable consent-based storage is configured; no unique user-count claim. Local analytics works independently.
* Global per-worker scan cap 8/minute is a minimal stopgap; upgrade with provider-level/WAF controls before broad launch. Public RPCs and indexers can be incomplete or overloaded.
* Render Free may spin down and has ephemeral filesystem. Test costs, uptime, data durability and limits independently.

## ONE-TIME release from Mac

Run from this folder after verifying `gh auth status` is the intended account:

```bash
./PUBLISH_READONLY_MAC.sh
```

This safely clones the EXISTING VuBounty/guardian360 repo, updates release files and GitHub Pages config, pushes a commit to the current default branch, and reports Pages status. It does NOT deploy Render or enable public wallet signing.

## Deploy separate HTTPS API

1. Open https://render.com/deploy?repo=https://github.com/VuBounty/guardian360 and authorize Render to access GitHub and create the FREE web service from `render.yaml`.
2. Wait until the Render service is **Live**. Open `https://YOUR-RENDER-HOST/api/health` and ensure `mode=PUBLIC_READ_ONLY`, `scan_enabled=false`, `revoke_endpoints=false`, `wallet_signing=false`.
3. Turn on `GUARDIAN_PUBLIC_ENABLE_SCAN=true` in Render only after RPC/network QA and review. Redeploy. Verify scan outputs `INCOMPLETE` and `/api/revoke/verify` returns 404.
4. Connect Pages URL to the HTTPS API with `./SET_PUBLIC_API_MAC.sh https://YOUR-RENDER-HOST`. It refuses non-HTTPS, unverified mode, live revoke endpoints or disabled scans.

If the user has NOT granted Render authorization, nothing can create or operate the service under their account automatically. Never paste API, GitHub, Render or MetaMask secrets in chat.

## Testnet

Read `qa/TESTNET_REVOKE_GATE_EN.md`. No testnet revoke transaction has been performed; a read-only chain probe is included.

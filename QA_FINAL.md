# GUARDIAN 360 V2.4.2 — Consolidated QA / Release Gate
**2026-11-03 • English-first local beta • NOT INDEPENDENTLY AUDITED**

## Completed in the release build environment

| Check | Result | Evidence / limit |
|---|---|---|
| Backend unit/regression + opt-in analytics | **43/43 PASS** | `python -m pytest -q backend/tests qa/test_analytics_integration.py`; mocked RPC / TestClient where appropriate |
| Python compilation | **PASS** | `compileall` for FastAPI, forensic, revoke and analytics modules |
| Browser JavaScript parsing | **PASS** | `node --check` on all `docs/*.js` files |
| English UI verification | **PASS** | English HTML, JS prompts, errors, admin, revoke; `html lang=en` |
| Browser interaction / 1440×900 | **PASS** | Mocked API and wallet, read-only scan → verify → preflight, send disabled |
| Browser interaction / 390×844 | **PASS** | Same scenario, no horizontal overflow |
| Browser interaction / 320×700 | **PASS** | Same scenario, no horizontal overflow |
| Local CORS, allowed 127.0.0.1:5173 | **PASS** | Preflight 200 for trusted origin |
| Local CORS, unrelated website | **PASS (blocked)** | Preflight 400 for untrusted origin |
| MetaMask automatic connection on scan | **PASS (not called)** | Mock provider request history remains empty during scanning |
| `eth_sendTransaction` in local beta | **PASS (blocked)** | UI guard prevents send; even mocked provider would throw |
| Existing DOS design/font | **UNCHANGED** | byte-identical `docs/styles.css` from V2.4.1 |
| Private admin key/SQLite data in archive | **NOT INCLUDED** | archive manifest checked before release |

**Not tested / not certified:** real MetaMask testnet/mainnet revoke, live public backend, complete token/approval indexing, independent smart-contract review, public community analytics, production uptime/rate limits. These are release blockers for a working public security service. None of the checks above establishes wallet safety.

## Publication policy

A GitHub source repository may be public. A static Pages **UI preview** may be manually deployed, with all real scanning disabled unless a reviewed HTTPS API is configured. **Live public revoke remains HOLD**. Never publish `.local/`, admin keys, `.env`, SQLite databases, wallet reports or personal wallet addresses.

## One-pass local workflow

Run `./FINALIZE_AND_PUBLISH_MAC.sh` for the consolidated offline QA, local HTTP/CORS smoke, then publish source to `Vubounty/guardian360` only if the GitHub CLI session belongs to `Vubounty`. `./FINAL_LOCAL_MAC.sh` is the subsequent launch command without repeat QA.

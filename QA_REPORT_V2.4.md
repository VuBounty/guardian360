# QA/QC — GUARDIAN 360 V2.4

**Date:** 2026-11-03 · **Artifact:** guardian360-v2.4-secure-revoke.zip · **Status:** Local beta, mainnet safety sign-off NOT granted.

## Automated tests performed
- Existing V2.3 scanning backend regression tests: 26/26 pass.
- New revoke and privacy tests: 12/12 pass.
- Total backend `pytest`: **38/38 pass** (offline, fake onchain responses and HTTP TestClient).
- Node.js syntax checks: pass `docs/app.js`, `revoke.js`, `analytics.js`, `admin.js`, `config.js`.
- Browser smoke with injected fake MetaMask provider: 1440×900, 390×844, 320×700 pass; tests do not interact with real wallets.
- Browser negative flows: wrong MetaMask account prevented sending; server-substituted calldata detected and rejected without connecting wallet.
- Backend negative flows: wrong chain, zero allowance, transaction target mismatch, mined but still-active permission, large ERC721 token ID, unauthorized analytics admin access.
- Checksum and install package integrity validated during zip build.

## Not verified
- Live ERC20/721/1155/Permit2 revoke transaction on testnet or mainnet.
- Security of real malicious/nonstandard tokens and contracts.
- Independence/completeness of approval discovery indexers.
- Security review by third party.
- Production backend hosting, CORS/rate limits/abuse controls/persistent analytics.

## Release gate
- **LOCAL UI/UNIT QA: PASS**.
- **HIGH-VALUE MAINNET REVOKE: HOLD** until testnet, independent E2E audit and live provider tests.
- **PUBLIC COMMERCIAL LAUNCH: HOLD** until deployment security and privacy compliance are completed.

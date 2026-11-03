# GUARDIAN 360 V2.4.2 — English-first local beta release

## Changes
- English default (`html lang=en`), translating original Vietnamese text, validation errors, revoke prompts, participation analytics, owner admin portal and tab explanations.
- Existing Retro DOS look, monospace typography and CSS sizes preserved.
- No-cache local static server prevents stale V2.3/V2.4 browser assets.
- One-pass local setup, automated tests and API/UI start with controlled CORS for 5173 only.
- GitHub target `Vubounty/guardian360`, with protected publishing and no secrets.
- Public static source preview (if manually deployed) cannot scan; no fake data shown. Admin URL hidden.
- Transaction send disabled in this unvalidated release. Verification/preflight remain visible as local beta flows; **no live transaction release clearance**.
- Local analytics remains opt-in, with separate admin key and persistent per-install SQLite. Not global public usage metrics.

## Security caveats
No confirmed real-wallet revoke, incomplete approval discovery, and no independent security audit. Code is a beta development tool, not a wallet safety certification or a production-ready revoke platform.

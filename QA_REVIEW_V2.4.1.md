# GUARDIAN 360 V2.4.1 — QA / RELEASE-GATE REVIEW

**QA result: 43/43 backend and isolated analytics tests PASS; 3/3 offline layout tests PASS. Mainnet/testnet revoke remains UNVERIFIED.**

## Audit status

- Static + offline QA can validate code path, simulated wallet guards and analytics semantics.
- There is **no evidence of a successful real-wallet revoke**. `NOT MAINNET READY`.
- RPC/indexer approval discovery remains incomplete; `0 approvals found` does **not** imply safety.
- Browser-native translation is supported via page language metadata and bilingual help; full human-reviewed translations are **not** implemented.
- Font readability improvements do not change backend or revoke transaction ABI.

## Analytics metrics

| Indicator | Actual meaning |
| --- | --- |
| `all_scans_aggregate` | Total successful `/api/scan` operations; no deduplication / not people |
| `opted_in_unique_browsers` | Distinct opted-in browser IDs (HMAC); not distinct people |
| `consented_visits` | Opted-in visit events with dedup rules |
| `returning_browsers_last_14d` | Opted-in browser IDs with prior-period events that recur in last 14 days |

**Limitations:** only the backend currently running sees analytics data. Localhost does not measure public users. No analytics database contains wallet address by schema, but server RPC/indexer requests handle the supplied public address and host access logs may store IP. Persistent hosting, rate limits, access controls, privacy policy and bot filtering are needed before public launch.

## Revoke fee flow

- V2.4 has **no platform fee or payment receiver address**. `eth_sendTransaction` to token/NFT/Permit2 contract with `value=0`.
- Gas is paid to the blockchain ecosystem; on Ethereum, base fee is burned and priority fee goes to block proposer; exact distribution varies by chain.
- A transaction may consume gas even if reverted.
- Never claim post-revoke success without a matching receipt and fresh onchain allowance read.

## Release gate

`HOLD`: no real-wallet testnet E2E; no independent code review; approval discovery still bounded and may miss old allowances; no production anti-abuse or hosted public backend. Screens and UI are for local beta.

## UI / attribution acceptance

- Browser title advertises LOCAL BETA / NOT AUDITED.
- Header includes LOCAL BETA, NOT AUDITED and non-dismissible safety warning.
- Footer preserves existing technical labels and adds centered `© 2026 @SpaceAIFinance. All rights reserved.`.
- Browser translation help and local font-size toggle present; no auto-tracking.

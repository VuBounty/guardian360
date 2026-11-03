# UI Contract V2.3

**Source of truth:** FastAPI Security Engine V1.1.2, không chỉnh sửa backend.

## Input API

`POST /api/scan` với body `{ "address": "0x...", "chains": ["bsc", "ethereum"] }`.

Danh sách chain hợp lệ: bsc (56), ethereum (1), base (8453), arbitrum (42161). Chain roadmap chỉ hiển thị disabled. Empty selection chặn trước khi POST. Input phải là `0x` + 40 ký tự hexadecimal.

## Output mapping

- Scope: `report.chains`, `report.requested_chains`, `report.timestamp`.
- `native_status`, `native_balance`, `block` -> RPC/native balances.
- `tokens[]` / `classification` / `trusted_usd_eligible` -> token row / review / USD có giới hạn.
- `approvals[]` -> only found approval rows; `coverage.approvals_completeness` independently displayed.
- `delegation` -> EIP-7702 / known documented address, informational classification.
- `sweeper.status` -> heuristic signal; not proof of compromised private key.
- `quality.status`, `quality.unresolved[]`, `coverage.*` -> audit coverage, never green safety clearance.

## UI states

- INIT: API health waiting, no report shown.
- READY: backend health Online or Offline, scan available if address/chain valid; backend offline is a scan error not fake result.
- LOADING: disables scan; back end call in progress.
- REPORT: response `chains` exactly matches requested chain set, visible tabs and scope filter.
- STALE-SCOPE: selection changed since report; warn user the previous scan is unchanged.
- ERROR: display no fabricated report; user can retry.

## Security rendering

- No wallet SDK, no `window.ethereum`, no signing, no transaction actions.
- Escape all dynamic strings in HTML. External links restricted by hostname allowlist.
- `risk_level` and `coverage` separate, no score based on missing evidence.
- No automatic token interactions. Export raw JSON is only local browser Blob.
- System trace is a **client scan status summary**, never falsely presented as RPC transaction-level evidence.

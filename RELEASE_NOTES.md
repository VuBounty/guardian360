# GUARDIAN 360 V2.4 — RELEASE NOTES

**Status: Local beta, no mainnet security sign-off.**

### New: Secure Revoke Engine
- `04 / REVOKE` in DOS/Blacksite Terminal.
- Four supported permission classes: ERC20/BEP20 allowance, ERC721/1155 operator, single-token ERC721, Permit2 internal allowance.
- No MetaMask access during scan; separate owner-triggered onchain verify, wallet connect/preflight and final signing.
- Read-only backend constructs fixed ABI zero-permission transactions. Frontend independently encodes calldata and blocks mismatches.
- Preflight validates wallet owner/chain/permission, `eth_call` and `eth_estimateGas`. Not a full contract security simulation.
- MetaMask solely signs and broadcasts. Backend verifies receipt sender, target, input and rechecks current permission.
- EIP-7702 revocation excluded. Not a spyware scanner or seed phrase recovery system.

### New: Privacy-first Usage Analytics
- Count anonymous aggregate scan operations without collecting wallet/IP in analytics table.
- Opt-in approximate unique-browser, visit and returning metrics; user can request deletion.
- Owner-only `/admin.html` with 14-day counters and local generated admin secret.
- SQLite local persistence; deployer must add durable storage, abuse protections and privacy notice before public hosting.

### QA
- 26 old backend regression tests + 12 V2.4 tests = **38/38 passed**.
- Browser mock tests: desktop 1440×900, iPhone 390×844, mobile 320×700.
- Browser negative tests: wrong connected account and tampered calldata both blocked before signing.
- No real funds, no real MetaMask transaction or mainnet writes in testing.

### Release gate
- Local/source beta: **PASS**.
- Public mainnet revoke/signing: **HOLD** until real-provider testnet E2E, security audit, external review, RPC/indexer coverage repair and production throttling.

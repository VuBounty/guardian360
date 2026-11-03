# GUARDIAN 360 / Testnet revoke audit gate (NOT YET COMPLETE)

The public API has NO revoke endpoints. The public UI cannot connect a wallet or send a transaction.

## E2E conditions before any public-wallet feature

1. Use a newly generated, dedicated testnet-only wallet; no real assets and never share seed/private key.
2. Deploy a minimal ERC-20 test token on Sepolia or BSC testnet, test mint, approve an isolated spender, read current allowance.
3. Adapt the revoke verifier to a TESTNET-ONLY chain registry, with chain ID strictly pinned; never point the production service to testnet and mainnet keys at once.
4. Prove an exact approve(spender,0) calldata intent, show current allowance and estimated gas, and simulate without signing.
5. Connect the dedicated testnet MetaMask only after user confirmation; prove signer/chain match, reject mutated calldata, and show wallet confirmation.
6. Sign once on testnet; record transaction hash, receipt status, exact contract, final allowance=0, block and RPC timestamp.
7. Repeat for ERC-721 operator and token approvals and Permit2; include denial/mismatch/reorg and RPC failure cases.
8. Independent review of calldata, replay/staleness, CORS, rate limiting, DNS, dependency exposure and front-end supply chain.
9. Only after accepted E2E tests and security review may any future separate opt-in revoke service be considered. Never reuse the PUBLIC_READ_ONLY app for signing.

A READ-ONLY network probe is available: `GUARDIAN_TESTNET_RPC=https://... GUARDIAN_TESTNET_CHAIN_ID=97 python3 qa/testnet_rpc_probe.py`. No gas, wallet credentials or transactions are needed.

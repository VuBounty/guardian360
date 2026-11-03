# Guardian 360 V2.4 — SECURITY MODEL (Beta)

## User action boundaries
1. Address-only scan: no EIP-1193 provider discovery or connection called in application scan.
2. Backend verification: user action requests an independent RPC state read. No signature.
3. Opt-in wallet connection: `eth_requestAccounts` triggered only after separate user click.
4. Wallet-side preflight: matching owner, chain ID, local ABI encoding, live approval, `eth_call` and `eth_estimateGas`. It is **not** a full bytecode/state-diff simulation and does not guarantee outcome.
5. Final user confirmation: `eth_sendTransaction` called only after separate user click; wallet signs or rejects. Backend never holds private keys.
6. Post-check: actual tx sender/to/input, receipt.status==1, then onchain permission read. An unverified state MUST NOT be reported as cleared.

## Threat model and limits
- RPC can be malicious/unavailable: compare chain ID; reject malformed responses; browser independently constructs allowlisted ABI calls.
- Backend compromised: browser refuses any modified calldata/destination/chain relative to locally built intent, but cannot guarantee malicious JS delivery if the frontend itself is compromised.
- Unauthorized owner: wallet account must equal scanned owner. Wrong network is blocked unless wallet user agrees to switch.
- Revoke is **not** key-rotation, address-blacklisting, device-spyware detection, or phishing detection.
- ERC-20 allowance revocation only helps against that particular spender and token; a private-key compromise can always bypass it.
- Permit2 signature-based approvals that have not been broadcast may remain unobservable; a signed authorization can still be valid depending on nonce/expiry. Not all permit systems use Permit2.
- Approval discovery only covers found candidates; manual verify enables checking known spender/contract pairs but is not comprehensive discovery.
- Smart Account/EIP-7702 delegates are not treated as ERC-20 approvals; process inside compatible wallet.
- Contracts with nonstandard return data may be refused. A failed query/preflight never becomes a green or completed status.
- No browser-wallet signing flow has been exercised with a real wallet/chain; tests use a fake provider.

## Analytics privacy / integrity
- All-scans aggregate is a single daily integer count; it does not imply distinct humans.
- Opt-in browser metrics use random browser UUID -> server-side HMAC digest; raw UUID not stored by the analytics database.
- Visitor deletion deletes events with the same digest, assuming the server is online; if offline, the browser retains its UUID for a subsequent retry.
- Admin dashboard is protected by a random secret in an HTTP header. Do not deploy over HTTP publicly.
- Hosting logs may still process addresses, IPs and network metadata outside the analytics database; deployer must disclose real data handling.
- Bot traffic can inflate totals; not a robust public analytics service until abuse controls are added.

## References
- EIP-1193: https://eips.ethereum.org/EIPS/eip-1193
- ERC-721 and ERC-1155 methods: https://docs.openzeppelin.com/contracts/5.x/api/token/erc721
- Uniswap Permit2: https://developers.uniswap.org/docs/protocols/permit2/overview
- Permit2 allowance: https://developers.uniswap.org/docs/protocols/permit2/concepts/allowance-transfer

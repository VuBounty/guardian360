# GUARDIAN 360 — BETA PRIVACY NOTE

The wallet audit endpoint receives the public wallet address you choose to scan, then may query third-party RPC/indexer providers. It does **not** ask for seed phrases or wallet private keys. The onchain transaction is signed by your wallet extension only after explicit clicks.

To assess product adoption, the backend keeps a **daily aggregate count of scans**. This counter does not record wallet addresses or unique visitors. Optional analytics use a user-selected random browser ID transformed to a server-side keyed hash; only opted-in visits/completed scans are recorded with that hash. Turning off consent requests deletion of that browser's analytics events. If the server is unavailable, deletion may be deferred until the user retries.

Opt-in telemetry can undercount real users, while aggregate scans can overcount individual users. Neither metric is a census of distinct humans. The admin view does not expose wallet addresses.

Hosting providers and web servers can process IP addresses, user agents and request metadata in normal access logs. The deployer must publish a suitable full privacy policy, configure retention, access protection and comply with applicable laws before public deployment.

The code does not implement account analytics for X/Facebook/Google. GitHub Stars/Forks are separate metrics and not included in this dashboard.

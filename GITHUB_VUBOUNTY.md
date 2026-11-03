# Publish source to Vubounty / GitHub

**Intended repository:** `Vubounty/guardian360` (created only after GitHub authentication; not yet published by this ZIP).

**Single-pass command after extraction:** `./FINALIZE_AND_PUBLISH_MAC.sh`.

If GitHub CLI is not installed, run `brew install gh` once. If not authenticated, run `gh auth login` and then `./PUBLISH_TO_VUBOUNTY.sh`. Keep all credentials private. The publication script checks the owner and refuses to overwrite an existing repository.

The repository is MIT licensed with copyright attribution for `@SpaceAIFinance`. In GitHub repository → Settings → Pages, you may manually enable the workflow named **Deploy static SOURCE PREVIEW**, but that preview is deliberately not a working scanner. GitHub Pages cannot host FastAPI or SQLite. The live backend needs separate HTTPS infrastructure, threat model, safeguards and completed read-only release gates. The Revoke send path remains disabled in this version.

**Do not enable public transaction signing** without successful clean testnet E2E and independent security review. Dashboard statistics on `localhost` measure only local usage.

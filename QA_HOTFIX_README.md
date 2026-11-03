# GUARDIAN 360 V2.4.2 — QA Dependency Hotfix

Fixes `9 failed, 34 passed` on macOS when `pytest.mark.asyncio` was not understood.
Root cause: the original installation scripts installed `pytest` without `pytest-asyncio`.

## Fix
- Add both pytest and pytest-asyncio to `backend/requirements.txt`.
- Install required packages even when a virtual environment already exists.
- Run QA only from the finalization/first-run scripts, with the existing pass marker.
- Keep security scanning, revoke logic, interface and analytics unchanged.
- GitHub CI uses the same requirements and runs all 43 tests.

## Installation on Mac
1. Download this ZIP to Downloads.
2. `cd ~/Myproject/GUARDIAN360 && unzip -o ~/Downloads/guardian360-v2.4.2-qa-fixed.zip`
3. `cd guardian360-v2.4.2-english-final && chmod +x FINALIZE_AND_PUBLISH_MAC.sh && ./FINALIZE_AND_PUBLISH_MAC.sh`
4. On success: `./FINAL_LOCAL_MAC.sh` to keep UI/API running.

Stop previous GUARDIAN servers on ports 5173/8000 before starting.
No real MetaMask revoke transaction is enabled or validated by this patch.

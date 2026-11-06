from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from public_api import app, public_health

def test_live_public_route_boundary():
    assert {r.path for r in app.routes}=={'/api/health','/api/chains','/api/scan'}
    h=public_health()
    assert h['version']=='2.6.0-public-readonly'
    assert h['wallet_signing'] is False
    assert h['revoke_endpoints'] is False
    assert h['audit_coverage'].startswith('INCOMPLETE')
    assert h['release_id']

def test_ui_requires_exact_live_release():
    html=(ROOT/'docs/index.html').read_text()
    cfg=(ROOT/'docs/config.js').read_text()
    script=(ROOT/'docs/app.js').read_text()
    assert 'GUARDIAN_REQUIRED_RELEASE_ID' in cfg
    assert 'data.release_id!==window.GUARDIAN_REQUIRED_RELEASE_ID' in script
    assert 'state.backendOK' in script
    assert 'wallet_signing!==false' in script
    assert "GUARDIAN_PUBLIC_PREVIEW = false" in cfg
    assert "GUARDIAN_ENABLE_REVOKE_TRANSACTIONS = false" in cfg
    assert '<script src="analytics.js' not in html
    assert not (ROOT/'docs/revoke.js').exists()
    assert 'SYNTHETIC UI DEMO' not in html
    assert 'GUARDIAN360_PREMIUM_OFFLINE_DEMO' not in html

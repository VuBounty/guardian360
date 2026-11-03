"""Offline regression for independent BSC reconciliation (no RPC calls)."""
import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / 'qa' / 'run_live_bsc_qa.py'
spec = importlib.util.spec_from_file_location('bscqa', SCRIPT)
bscqa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bscqa)

WALLET='0x1111111111111111111111111111111111111111'


def report():
    return {
        'requested_chains':['bsc'],
        'chains':[{'chain':'bsc','native_balance':'0.00000614','native_status':'verified','block':100,
                   'tokens':[{'contract':bscqa.USDT, 'raw_balance':str(10**18)}],
                   'approvals':[],
                   'delegation':{'status':'eip7702_delegated','delegate':bscqa.MM_DELEGATOR},
                   'coverage':{'approvals_completeness':'partial_historical_discovery'},
                   'quality':{'status':'incomplete'}}],
        'summary':{'all_approvals_status':'UNKNOWN_INCOMPLETE','security_clearance':False}
    }


def independent():
    return {'chain_id':56,'block':100,'native_raw':6140000000000,
            'token_raw':{bscqa.USDT:10**18,bscqa.USDC:0},
            'code':'0xef0100'+bscqa.MM_DELEGATOR[2:]}


def test_read_only_scan_reconciles_all_known_fields():
    rows=bscqa.evaluate(report(), independent())
    assert not [r for r in rows if r['status']=='FAIL'],rows
    assert any(r['check']=='Zero discovered approvals semantics' and r['status']=='PASS' for r in rows)
    assert any(r['check']=='EIP-7702 designation' and r['status']=='PASS' for r in rows)


def test_invalid_chain_scope_fails_closed():
    r=report();r['requested_chains']=['ethereum']
    assert bscqa.evaluate(r,independent())[0]['status']=='FAIL'


def test_missing_nonzero_token_detected_as_discrepancy():
    r=report();r['chains'][0]['tokens']=[]
    rows=bscqa.evaluate(r,independent())
    assert any(row['status']=='FAIL' and row['check']=='USDT token detection' for row in rows)


def test_zero_discovered_approvals_is_not_verdict():
    r=report();r['summary']['all_approvals_status']='SAFE'
    rows=bscqa.evaluate(r,independent())
    assert any(row['status']=='FAIL' and row['check']=='Zero discovered approvals semantics' for row in rows)


def test_manual_revoke_reference_missing_approval_is_fail(tmp_path):
    ref=tmp_path/'revoke.csv';ref.write_text('kind,token_contract,spender\nerc20_allowance,0x55d398326f99059ff775485246999027b3197955,0x2222222222222222222222222222222222222222\n')
    rows=bscqa.manual_compare(report(),approvals_csv=str(ref))
    assert any(row['status']=='FAIL' and 'Revoke.cash' in row['check'] for row in rows)


def test_single_chain_external_benchmark_pin():
    source=(Path(__file__).resolve().parents[2]/'docs'/'app.js').read_text()
    assert 'revokeURL(state.report.address, c.chain)' in source
    assert '?chainId=${chainId}' in source
    assert "['etherscan.io','bscscan.com','basescan.org','arbiscan.io'" in source

"""Regression suite using synthetic examples; user wallet report is not bundled."""
import asyncio
import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import forensic as f
import main as g


def test_huge_uint256_balance_remains_exact():
    raw = 45954714265146517498662594223355353967174749256715476674843372019207431587448
    val = f.exact_balance(raw, 18)
    assert val == str(raw // 10**18) + '.' + str(raw % 10**18).zfill(18)
    assert Decimal(val) > Decimal('1e50')
    assert '10^' not in val  # exact raw record, UI uses compact scientific


def test_fake_eth_ticker_is_not_native_eth():
    item = {'symbol': 'ETH', 'contract': '0x7bfEB542E7312196Ce0D120a9Ff0A81A1973213A',
            'balance': '45954714265146517498662594223355353967174749256715476674843372',
            'usd_value': '999999999', 'source': 'blockscout-indexer'}
    flagged = f.classify_token(item, 'ethereum')
    assert flagged['source_type'] == 'token_contract'
    assert flagged['classification'] == 'review'
    assert not flagged['trusted_usd_eligible']
    assert any('native' in reason for reason in flagged['review_reasons'])
    assert 'E+' in flagged['display_balance']


def test_recognized_usdc_is_in_trusted_partial_total_only_with_price():
    legit = f.classify_token({'symbol': 'USDC', 'contract': '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48',
                              'balance': '10', 'usd_value': '10.05'}, 'ethereum')
    unknown = f.classify_token({'symbol': 'FOMO', 'contract': '0x1111111111111111111111111111111111111111',
                                'balance': '200', 'usd_value': '700'}, 'ethereum')
    out = f.summarize_forensic([{'native_usd': '0.3', 'native_balance': '0.0001', 'tokens': [legit, unknown]}])
    assert out['recognized_usd_partial'] == '10.35'
    assert out['excluded_unverified_usd_quotes'] == '700'
    assert not unknown['trusted_usd_eligible']
    assert out['all_approvals_status'] == 'UNKNOWN_INCOMPLETE'


def test_known_metamask_delegate_is_informational_not_risk_label():
    d = f.classify_delegation({'status':'eip7702_delegated','delegate': f.METAMASK_EIP7702}, 'bsc')
    assert d['identity_status'] == 'known_documented_address'
    assert d['review_priority'] == 'informational'
    assert d['references']
    x = f.classify_delegation({'status':'eip7702_delegated','delegate': '0x'+'1'*40}, 'bsc')
    assert x['identity_status'] == 'unknown' and x['review_priority'] == 'review'


def test_0_approvals_with_401_403_must_be_unverified():
    for code in ('401 Unauthorized', '403 Forbidden'):
        c = {'native_status': 'verified', 'approvals': [], 'coverage': {
            'token_index': 'unavailable: HTTP ' + code,
            'transactions': 'unavailable: HTTP ' + code,
            'approval_event_logs': {'status': 'partial'},
            'permit2_internal': {'status': 'partial'},
            'approvals_completeness':'partial_historical_discovery'
        }}
        r = f.evaluate_coverage(c)
        assert r['status'] == 'incomplete' and not r['approval_discovery_complete']
        assert r['approval_status'] == 'unknown'
        assert any('historical' in msg for msg in r['unresolved'])


def test_known_token_nonspoof_unpriced():
    t = f.classify_token({'symbol':'USDT','contract':'0x55d398326f99059fF775485246999027B3197955',
                          'balance':'0.00003651','usd_value':None}, 'bsc')
    assert t['classification'] == 'recognized_contract'
    assert t['trusted_usd_eligible'] is False


def test_read_only_source_contract_and_browser_guard():
    source = (Path(__file__).resolve().parents[1] / 'main.py').read_text()
    browser = (Path(__file__).resolve().parents[2] / 'docs' / 'app.js').read_text()
    assert 'eth_sendTransaction' not in source
    assert 'wallet_requestPermissions' not in browser
    assert 'eth_requestAccounts' not in browser
    assert 'new URLSearchParams(location.search)' not in browser
    assert 'Zero discovered approvals do not establish zero actual approvals.' in browser


def test_api_version_and_direct_permit2_probes(monkeypatch):
    monkeypatch.setattr(g,'LOG_LOOKBACK',0)
    import httpx, json
    wallet = '0x1111111111111111111111111111111111111111'
    def handler(req):
        if req.method == 'POST':
            body=json.loads(req.content)
            method=body['method']
            if method=='eth_chainId': result=hex(56)
            elif method=='eth_blockNumber': result=hex(2500)
            elif method=='eth_getBalance': result='0x0'
            elif method=='eth_getCode': result='0xef0100'+f.METAMASK_EIP7702[2:]
            elif method=='eth_call': result='0x0'
            else: raise AssertionError(method)
            return httpx.Response(200,json={'result':result})
        return httpx.Response(401, json={'error':'missing API key'})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await g.scan_chain(client,'bsc',g.CHAINS['bsc'], wallet)
    c=asyncio.run(run())
    assert c['native_status']=='verified'
    assert c['delegation']['identity_status']=='known_documented_address'
    assert c['quality']['approval_status']=='unknown'
    assert c['coverage']['known_token_permit2_direct_probes'] == len(g.KNOWN_TOKENS['bsc'])
    assert c['approvals']==[]


def test_live_allowance_rpc_error_is_not_silently_counted():
    import httpx
    wallet = '0x1111111111111111111111111111111111111111'
    spender = '0x2222222222222222222222222222222222222222'
    token = '0x3333333333333333333333333333333333333333'
    errors = []
    async def run():
        def handler(request):
            return httpx.Response(429, json={'message': 'Rate limited'})
        candidate = {'kind': 'erc20', 'contract': token, 'spender': spender, 'discovery': 'synthetic'}
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await g.check_candidate(client, 'https://rpc.example', wallet, candidate, {}, 'https://bscscan.com', errors)
    assert asyncio.run(run()) is None
    assert len(errors) == 1 and errors[0]['kind'] == 'erc20'
    quality = f.evaluate_coverage({'native_status': 'verified', 'coverage': {'allowance_probe_errors': {'count': 1}}})
    assert any('probes failed' in t for t in quality['unresolved'])

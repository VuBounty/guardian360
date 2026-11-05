"""P0.4 regression: fully synthetic Ethereum/BSC RPC + quote service, no real wallets."""
import asyncio
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import asset_valuation as av
import forensic as f
import main
import public_api

WALLET = '0x' + '1' * 40  # synthetic only
ETH_AXS = '0xbb0e17ef65f82ab018d8edd776e8dd940327b28b'
FAKE_AXS = '0x' + '9' * 40
ETH_RAW = 600772852 * 10**12  # 600.772852 AXS, ERC-20 with 18 decimals
ETH_PRICE = Decimal('0.8767')
BSC_NATIVE_RAW = 10**16  # 0.01 BNB
BSC_NATIVE_PRICE = Decimal('715')


def transport(*, price='0.8767', decimals=18, fail_axs=False, candidate_symbol=False):
    calls = []
    def handle(req):
        if req.method == 'POST':
            body=json.loads(req.content)
            method=body['method']
            calls.append((method,body.get('params')))
            is_eth='ethereum' in req.url.host
            if method=='eth_chainId': result=hex(1 if is_eth else 56)
            elif method=='eth_blockNumber': result=hex(20000000 if is_eth else 50000000)
            elif method=='eth_getBalance': result=hex(0 if is_eth else BSC_NATIVE_RAW)
            elif method=='eth_getCode': result='0x'
            elif method=='eth_getLogs': result=[]
            elif method=='eth_call':
                contract=body['params'][0]['to'].lower()
                selector=body['params'][0]['data'][:10]
                if is_eth and contract==ETH_AXS and selector=='0x70a08231':
                    if fail_axs: return httpx.Response(502,text='simulated RPC failure')
                    result=hex(ETH_RAW)
                elif is_eth and contract==ETH_AXS and selector=='0x313ce567': result=hex(decimals)
                elif is_eth and contract==FAKE_AXS and selector=='0x70a08231': result=hex(999*10**18)
                elif is_eth and contract==FAKE_AXS and selector=='0x313ce567': result=hex(18)
                else: result='0x0'
            else: raise AssertionError('Unexpected RPC method '+method)
            return httpx.Response(200,json={'jsonrpc':'2.0','id':body['id'],'result':result})
        if req.url.host=='coins.llama.fi':
            now=int(time.time())
            body={'coingecko:binancecoin': {'price':str(BSC_NATIVE_PRICE),'timestamp':now,'confidence':0.99},
                  'coingecko:ethereum':{'price':3000,'timestamp':now,'confidence':0.99}}
            if price is not None:
                body['ethereum:'+ETH_AXS]={'price':price,'timestamp':now,'confidence':0.99}
                body['ethereum:'+FAKE_AXS]={'price':'80','timestamp':now,'confidence':0.99}
            return httpx.Response(200,json={'coins':body})
        if req.url.host=='api.coingecko.com': return httpx.Response(200,json={})
        raise AssertionError('Unexpected indexer/network: '+str(req.url))
    return httpx.MockTransport(handle),calls


async def scan_both(mock_transport, monkeypatch):
    monkeypatch.setattr(main,'LOG_LOOKBACK',0)
    monkeypatch.delenv('MORALIS_API_KEY',raising=False)
    monkeypatch.setenv('INDEXER_ETHEREUM','')
    monkeypatch.setenv('INDEXER_BSC','')
    async with httpx.AsyncClient(transport=mock_transport) as client:
        return await asyncio.gather(
            main.scan_chain(client,'bsc',main.CHAINS['bsc'],WALLET),
            main.scan_chain(client,'ethereum',main.CHAINS['ethereum'],WALLET),
        )


def test_ethereum_axs_catalog_identity_and_decimals():
    assert av.ETHEREUM_AXS_CONTRACT==ETH_AXS
    assert ('AXS',ETH_AXS,18) in av.ETHEREUM_CATALOG
    assert ('AXS',ETH_AXS,18) in main.KNOWN_TOKENS['ethereum']
    assert f.RECOGNIZED_TOKENS['ethereum'][ETH_AXS]=='AXS'
    assert len({x[1].lower() for x in main.KNOWN_TOKENS['ethereum']})==len(main.KNOWN_TOKENS['ethereum'])


def test_axs_ethereum_direct_discovery_and_per_chain_exact_totals(monkeypatch):
    mock,calls=transport()
    bsc,eth=asyncio.run(scan_both(mock,monkeypatch))
    axs=next(t for t in eth['tokens'] if t['contract'].lower()==ETH_AXS)
    assert axs['raw_balance']==str(ETH_RAW)
    assert Decimal(axs['balance'])==Decimal('600.772852')
    assert axs['balance_verification']=='verified' and axs['decimals']==18
    assert axs['block']==20000000 and axs['balance_source']=='onchain_at_block'
    assert axs['trusted_usd_eligible'] is True and axs['contract_recognized'] is True
    assert axs['price_source']=='defillama_by_chain_and_contract'
    assert axs['price_timestamp']>0
    expected=Decimal('600.772852')*ETH_PRICE
    assert Decimal(axs['usd_value'])==expected
    assert not any(x['symbol']=='AXS' for x in bsc['tokens'])
    val=f.summarize_forensic([bsc,eth])
    assert Decimal(val['priced_usd_by_chain']['bsc']['usd_priced_partial'])==Decimal('7.15')
    assert Decimal(val['priced_usd_by_chain']['ethereum']['usd_priced_partial'])==expected
    assert Decimal(val['recognized_usd_partial'])==expected+Decimal('7.15')
    assert val['usd_completeness']=='partial_or_unknown'
    assert bsc['quality']['status']=='incomplete' and eth['quality']['status']=='incomplete'
    assert any(method=='eth_call' and params[0].get('to','').lower()==ETH_AXS and params[0]['data'].startswith('0x70a08231') and params[1]==hex(20000000)
               for method,params in calls)
    assert any(method=='eth_getBalance' and params[1]==hex(50000000)
               for method,params in calls)
    assert any(method=='eth_getBalance' and params[1]==hex(20000000)
               for method,params in calls)


def test_selected_network_scope_not_global_wallet_value(monkeypatch):
    bsc,eth=asyncio.run(scan_both(transport()[0],monkeypatch))
    assert f.summarize_forensic([bsc])['recognized_usd_partial']=='7.15'
    expected=Decimal('600.772852')*ETH_PRICE
    assert Decimal(f.summarize_forensic([eth])['recognized_usd_partial'])==expected
    assert Decimal(f.summarize_forensic([eth,bsc])['recognized_usd_partial'])==expected+Decimal('7.15')


def test_ethereum_axs_unpriced_is_not_zero(monkeypatch):
    _,eth=asyncio.run(scan_both(transport(price=None)[0],monkeypatch))
    axs=next(t for t in eth['tokens'] if t['contract'].lower()==ETH_AXS)
    assert Decimal(axs['balance'])>0
    assert axs['usd_value'] is None and not axs['trusted_usd_eligible']
    s=f.summarize_forensic([eth])
    assert s['recognized_usd_partial'] is None
    assert s['priced_usd_by_chain']['ethereum']['unpriced_or_excluded_assets']>=1


def test_ethereum_axs_rpc_error_is_not_zero(monkeypatch):
    _,eth=asyncio.run(scan_both(transport(fail_axs=True)[0],monkeypatch))
    assert eth['coverage']['asset_valuation']['balance_verification_failures']>=1
    assert not any(t['contract'].lower()==ETH_AXS for t in eth['tokens'])
    assert eth['quality']['status']=='incomplete'


def test_ethereum_axs_wrong_decimals_excluded(monkeypatch):
    _,eth=asyncio.run(scan_both(transport(decimals=8)[0],monkeypatch))
    axs=next(t for t in eth['tokens'] if t['contract'].lower()==ETH_AXS)
    assert axs['balance_verification']=='decimals_mismatch'
    assert axs['usd_value'] is None
    assert not f.classify_token(axs,'ethereum')['trusted_usd_eligible']


def test_fake_symbol_not_recognized_and_never_added(monkeypatch):
    index=[{'contract':FAKE_AXS,'symbol':'AXS','name':'AXS fake'}]
    async def probe():
        async with httpx.AsyncClient(transport=transport()[0]) as client:
            return await av.reconcile_assets(client,main.rpc,main.CHAINS['ethereum']['rpc'],WALLET,'ethereum',20000000,
                                              index,main.KNOWN_TOKENS['ethereum'],main.CHAINS['ethereum']['explorer'])
    tokens,_=asyncio.run(probe())
    fake=next(t for t in tokens if t['contract'].lower()==FAKE_AXS)
    assert fake['usd_value'] is not None
    flagged=f.classify_token(fake,'ethereum')
    assert flagged['classification']=='review' and not flagged['trusted_usd_eligible']
    assert 'Ticker resembles' in ' '.join(flagged['review_reasons'])
    valued=f.summarize_forensic([{'chain':'ethereum','tokens':[flagged]}])
    assert valued['recognized_usd_partial'] is None
    assert Decimal(valued['excluded_unverified_usd_quotes'])>0


def test_duplicate_contract_never_double_counted():
    t={'contract':ETH_AXS, 'balance':'600.772852','usd_value':'526.7','trusted_usd_eligible':True}
    totals=f.summarize_forensic([{'chain':'ethereum','tokens':[t,dict(t)]}])
    assert totals['recognized_usd_partial']=='526.7'


def test_duplicate_chain_fails_closed():
    with pytest.raises(ValueError,match='Duplicate chain'):
        f.summarize_forensic([{'chain':'ethereum'},{'chain':'ethereum'}])


def test_partial_valuation_never_uses_negative_or_nonfinite():
    t={'contract':ETH_AXS,'balance':'1','usd_value':'NaN','trusted_usd_eligible':True}
    assert f.summarize_forensic([{'chain':'ethereum','tokens':[t]}])['recognized_usd_partial'] is None
    t['usd_value']='-10'
    assert f.summarize_forensic([{'chain':'ethereum','tokens':[t]}])['recognized_usd_partial'] is None


def test_api_multichain_response_has_consistent_value_by_chain(monkeypatch):
    bsc,eth=asyncio.run(scan_both(transport()[0],monkeypatch))
    reports={'bsc':bsc,'ethereum':eth}
    async def fake_chain(client,key,cfg,address):
        return reports[key]
    monkeypatch.setattr(main,'scan_chain',fake_chain)
    monkeypatch.setattr(main,'record_aggregate_scan',lambda:None)
    monkeypatch.setattr(public_api,'internal_scan',main.scan)
    monkeypatch.setenv('GUARDIAN_PUBLIC_ENABLE_SCAN','true')
    public_api._hits.clear()
    response=TestClient(public_api.app).post('/api/scan',json={'address':WALLET,'chains':['bsc','ethereum']})
    assert response.status_code==200,response.text
    data=response.json()
    assert data['requested_chains']==['bsc','ethereum']
    assert data['summary']['valuation_scope'].startswith('only_requested_scanned_chains')
    for c in data['chains']:
        assert c['priced_usd_partial']==data['summary']['priced_usd_by_chain'][c['chain']]['usd_priced_partial']
    expected=Decimal('7.15')+Decimal('600.772852')*ETH_PRICE
    assert Decimal(data['summary']['usd_known_sum'])==expected
    assert data['summary']['audit_quality']=='INCOMPLETE'
    assert data['summary']['security_clearance'] is False
    assert data['summary']['all_approvals_status']=='UNKNOWN_INCOMPLETE'
    assert set(route.path for route in public_api.app.routes)=={'/api/health','/api/chains','/api/scan'}


def test_p04_attestation_conservative_go_gate():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    import P04_VERIFY_MAC as audit
    value=format(Decimal('600.772852')*ETH_PRICE,'f')
    report={
        'address':WALLET,
        'chains':[
            {'chain':'bsc','block':50000000,'native_status':'verified','priced_usd_partial':'7.15'},
            {'chain':'ethereum','block':20000000,'native_status':'verified',
             'priced_usd_partial':value,
             'tokens':[{'contract':ETH_AXS,'symbol':'AXS','balance':'600.772852',
                        'raw_balance':str(ETH_RAW),'usd_value':value,
                        'balance_verification':'verified','contract_recognized':True,
                        'trusted_usd_eligible':True}]}
        ],
        'summary':{'usd_known_sum':str(Decimal('7.15')+Decimal(value)),
                   'priced_usd_by_chain':{
                       'bsc':{'usd_priced_partial':'7.15'},
                       'ethereum':{'usd_priced_partial':value}},
                   'audit_quality':'INCOMPLETE','security_clearance':False,
                   'all_approvals_status':'UNKNOWN_INCOMPLETE'},
    }
    ok=audit.reconcile(report,WALLET)
    assert ok['status'].startswith('TECHNICAL_RC1_LIVE_VALIDATION_PASS')
    assert ok['partial_sum_matches']
    assert 'NO_DEPLOYMENT' in ok['status']
    report['chains'][1]['tokens'][0]['trusted_usd_eligible']=False
    assert audit.reconcile(report,WALLET)['status']=='HOLD'
    report['chains'][1]['tokens'][0]['trusted_usd_eligible']=True
    report['summary']['usd_known_sum']='99999999'
    assert audit.reconcile(report,WALLET)['status']=='HOLD'

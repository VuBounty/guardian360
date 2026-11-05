"""V2.5 regression tests: all data synthetic; no external wallet or live network."""
import asyncio
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import asset_valuation as av
import forensic as f
import main

WALLET = '0x' + '1' * 40  # synthetic test account; not a real user's wallet
AXS = av.BSC_CATALOG[3][1]
UNKNOWN = '0x' + '9' * 40


def network(balance=500 * 10**18, decimals=18, price='1.05', age=60,
            confidence=0.99, indexed_price=None, fail_balance=False):
    calls=[]
    def handle(req):
        calls.append(str(req.url))
        if req.method == 'POST':
            j=json.loads(req.content)
            if j['method'] != 'eth_call':
                return httpx.Response(200, json={'result': '0x0'})
            contract=j['params'][0]['to'].lower()
            selector=j['params'][0]['data'][:10]
            if fail_balance and contract == AXS.lower() and selector == '0x70a08231':
                return httpx.Response(502, text='provider unavailable')
            if selector == '0x70a08231':
                result=balance if contract == AXS.lower() else (999*10**18 if contract == UNKNOWN.lower() else 0)
            elif selector == '0x313ce567':
                result=decimals if contract == AXS.lower() else 18
            else:
                result=0
            return httpx.Response(200,json={'result':hex(result)})
        if req.url.host == 'coins.llama.fi':
            payload={}
            if price is not None:
                payload['bsc:'+AXS.lower()] = {'price': price, 'timestamp': int(time.time())-age, 'confidence':confidence}
                payload['bsc:'+UNKNOWN.lower()] = {'price': 450, 'timestamp':int(time.time())-age,'confidence': 0.99}
            return httpx.Response(200,json={'coins':payload})
        raise AssertionError('Unexpected request '+str(req.url))
    return httpx.MockTransport(handle), calls


async def perform(transport, indexed=None):
    async with httpx.AsyncClient(transport=transport) as c:
        return await av.reconcile_assets(c, main.rpc, 'https://rpc.example', WALLET, 'bsc', 12345,
                                  indexed or [], list(av.BSC_CATALOG), 'https://bscscan.com')


def test_axs_verified_known_contract_500_usd_not_hardcoded():
    transport, calls=network(price='1.05')
    tokens, cov=asyncio.run(perform(transport))
    axs=next(t for t in tokens if t['contract'].lower()==AXS.lower())
    assert axs['raw_balance']==str(500*10**18)
    assert Decimal(axs['balance'])==Decimal('500')
    assert Decimal(axs['usd_value'])==Decimal('525.00')
    assert axs['price_timestamp'] and axs['block']==12345
    assert axs['balance_verification']=='verified'
    assert axs['price_source']=='defillama_by_chain_and_contract'
    assert cov['verified_positive_balances']==1 and cov['priced_verified_contracts']==1
    assert any('0x70a08231' in url for url in calls) is False # selector belongs to JSON request body
    classified=f.classify_token(axs,'bsc')
    assert classified['trusted_usd_eligible']
    assert f.summarize_forensic([{'tokens':[classified]}])['recognized_usd_partial']=='525.00'


def test_price_uses_live_balance_not_stale_indexed_balance():
    index=[{'contract':AXS, 'symbol':'AXS','raw_balance':str(2500*10**18),
            'balance':'2500', 'usd_value':'999999', 'usd_price':'399'}]
    tokens, _=asyncio.run(perform(network(balance=10*10**18, price='1')[0], index))
    axs=next(t for t in tokens if t['contract'].lower()==AXS.lower())
    assert axs['balance']=='10' and axs['usd_value']=='10' and axs['balance_source']=='onchain_at_block'


def test_zero_onchain_supersedes_positive_indexer():
    index=[{'contract':AXS, 'symbol':'AXS','balance':'3333','raw_balance':str(3333*10**18),
            'usd_value':'90000'}]
    tokens,_=asyncio.run(perform(network(balance=0)[0], index))
    assert not any(t['contract'].lower()==AXS.lower() for t in tokens)


def test_stale_price_is_excluded():
    tokens,_=asyncio.run(perform(network(age=3600)[0]))
    axs=next(t for t in tokens if t['contract'].lower()==AXS.lower())
    assert axs['usd_value'] is None and axs['price_status']=='unavailable_or_stale'
    assert not f.classify_token(axs,'bsc')['trusted_usd_eligible']


def test_low_confidence_price_is_excluded():
    tokens,_=asyncio.run(perform(network(confidence=0.2)[0]))
    assert next(t for t in tokens if t['contract'].lower()==AXS.lower())['usd_value'] is None


def test_wrong_contract_decimals_is_excluded_and_marked_review():
    tokens,cov=asyncio.run(perform(network(decimals=8)[0]))
    axs=next(t for t in tokens if t['contract'].lower()==AXS.lower())
    assert axs['balance_verification']=='decimals_mismatch' and axs['usd_value'] is None
    assert cov['decimals_verification_failures']==1
    classified=f.classify_token(axs,'bsc')
    assert classified['classification']=='review' and not classified['trusted_usd_eligible']


def test_rpc_failure_is_not_silently_zero_or_priced():
    index=[{'contract':AXS,'symbol':'AXS','balance':'500','raw_balance':str(500*10**18),'usd_value':'50000'}]
    tokens,cov=asyncio.run(perform(network(fail_balance=True)[0],index))
    axs=next(t for t in tokens if t['contract'].lower()==AXS.lower())
    assert axs['balance_verification'].startswith('rpc_failed')
    assert axs['usd_value'] is None
    assert cov['balance_verification_failures']>=1
    assert not f.classify_token(axs,'bsc')['trusted_usd_eligible']


def test_fake_axs_symbol_has_no_trusted_value_even_when_priced():
    index=[{'contract':UNKNOWN,'symbol':'AXS','name':'Fake AXS','balance':'999','raw_balance':str(999*10**18)}]
    tokens,_=asyncio.run(perform(network()[0],index))
    fake=next(t for t in tokens if t['contract'].lower()==UNKNOWN.lower())
    flagged=f.classify_token(fake,'bsc')
    assert flagged['classification']=='review'
    assert flagged['trusted_usd_eligible'] is False
    assert 'Ticker resembles' in ' '.join(flagged['review_reasons'])


def test_malformed_quote_and_future_timestamp_rejected():
    assert av.validate_quote({'price':'NaN','timestamp':int(time.time())}) is None
    assert av.validate_quote({'price':'Infinity','timestamp':int(time.time())}) is None
    assert av.validate_quote({'price':1.0,'timestamp':int(time.time())+100}) is None
    assert av.validate_quote({'price':1.0,'timestamp':int(time.time())-2000}) is None
    assert av.validate_quote({'price':0,'timestamp':int(time.time())}) is None
    assert av.validate_quote({'price':1.0,'timestamp':int(time.time())-15, 'confidence':0.95})


def test_uint256_balance_precision_with_no_price():
    raw=(2**256)-9
    tokens,cov=asyncio.run(perform(network(balance=raw,price=None)[0]))
    axs=next(t for t in tokens if t['contract'].lower()==AXS.lower())
    assert axs['raw_balance']==str(raw)
    assert axs['usd_value'] is None
    assert Decimal(axs['balance']) > Decimal('1e50')
    assert f.classify_token(axs,'bsc')['classification']=='review'


def test_bounded_discovery_and_dedup():
    index=[{'contract':AXS,'symbol':'AXS','balance':'500'}, {'contract':AXS.upper().replace('0X','0x'),'symbol':'AXS','balance':'3'}]
    tokens,cov=asyncio.run(perform(network()[0],index))
    assert sum(t['contract'].lower()==AXS.lower() for t in tokens)==1
    assert cov['known_contract_candidates']==len(av.BSC_CATALOG)


def test_public_api_still_excludes_revoke_and_signing():
    import public_api
    routes={route.path for route in public_api.app.routes}
    assert routes=={'/api/health','/api/chains','/api/scan'}
    assert 'revoke' not in ' '.join(routes)


def test_coingecko_contract_fallback_only_after_primary_price_missing():
    def handler(req):
        if req.method=='POST':
            request=json.loads(req.content)
            contract=request['params'][0]['to'].lower()
            selector=request['params'][0]['data'][:10]
            raw=(50*10**18) if contract==AXS.lower() and selector=='0x70a08231' else (18 if contract==AXS.lower() and selector=='0x313ce567' else 0)
            return httpx.Response(200,json={'result':hex(raw)})
        if req.url.host=='coins.llama.fi':
            return httpx.Response(200,json={'coins':{}})
        if req.url.host=='api.coingecko.com':
            return httpx.Response(200,json={AXS.lower():{'usd':2.5,'last_updated_at':int(time.time())-30}})
        raise AssertionError(str(req.url))
    transport=httpx.MockTransport(handler)
    tokens,cov=asyncio.run(perform(transport))
    axs=next(t for t in tokens if t['contract'].lower()==AXS.lower())
    assert axs['usd_value']=='125.0'
    assert axs['price_source']=='coingecko_by_chain_and_contract'
    assert f.classify_token(axs,'bsc')['trusted_usd_eligible']
    assert 'coingecko_fallback' in cov['price_service']


def test_coingecko_stale_fallback_never_summed():
    def handler(req):
        if req.method=='POST':
            reqj=json.loads(req.content)
            c=reqj['params'][0]['to'].lower()
            sel=reqj['params'][0]['data'][:10]
            val=(10**18) if c==AXS.lower() and sel=='0x70a08231' else (18 if c==AXS.lower() and sel=='0x313ce567' else 0)
            return httpx.Response(200,json={'result':hex(val)})
        if req.url.host=='coins.llama.fi':return httpx.Response(200,json={'coins':{}})
        if req.url.host=='api.coingecko.com':return httpx.Response(200,json={AXS.lower():{'usd':90,'last_updated_at':int(time.time())-86400}})
        raise AssertionError(str(req.url))
    tokens,_=asyncio.run(perform(httpx.MockTransport(handler)))
    axs=next(t for t in tokens if t['contract'].lower()==AXS.lower())
    assert axs['usd_value'] is None
    assert not f.classify_token(axs,'bsc')['trusted_usd_eligible']


def test_bsc_scan_chain_integration_axs_valued_without_indexer(monkeypatch):
    monkeypatch.setattr(main,'LOG_LOOKBACK',0)
    monkeypatch.delenv('MORALIS_API_KEY',raising=False)
    monkeypatch.delenv('BLOCKSCOUT_API_KEY',raising=False)
    def handler(req):
        if req.method=='POST':
            body=json.loads(req.content)
            method=body['method']
            if method=='eth_chainId': val=hex(56)
            elif method=='eth_blockNumber': val=hex(50000)
            elif method=='eth_getBalance': val=hex(10**18)
            elif method=='eth_getCode': val='0x'
            elif method=='eth_call':
                c=body['params'][0]['to'].lower()
                selector=body['params'][0]['data'][:10]
                if c == AXS.lower() and selector=='0x70a08231':val=hex(500*10**18)
                elif c == AXS.lower() and selector=='0x313ce567':val=hex(18)
                else:val='0x0'
            else:raise AssertionError(method)
            return httpx.Response(200,json={'result':val})
        if req.url.host=='coins.llama.fi':
            now=int(time.time())
            return httpx.Response(200,json={'coins':{
                'bsc:'+AXS.lower():{'price':1.1,'timestamp':now,'confidence':0.98},
                'coingecko:binancecoin':{'price':600,'timestamp':now,'confidence':0.97}}})
        raise AssertionError('Unexpected indexed API use: '+str(req.url))
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await main.scan_chain(c,'bsc',main.CHAINS['bsc'],WALLET)
    report=asyncio.run(go())
    assert report['native_status']=='verified'
    axs=next(t for t in report['tokens'] if t['symbol']=='AXS')
    assert axs['usd_value']=='550.0'
    assert axs['trusted_usd_eligible']
    assert report['native_usd']=='600'
    total=f.summarize_forensic([report])['recognized_usd_partial']
    assert Decimal(total)==Decimal('1150')
    assert report['quality']['status']=='incomplete'
    assert not report['quality']['approval_discovery_complete']

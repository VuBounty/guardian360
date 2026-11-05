"""Deterministic offline tests: no fabricated blockchain results or live network dependencies."""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
import main as g

WALLET = '0x1111111111111111111111111111111111111111'
SPENDER = '0x2222222222222222222222222222222222222222'
USDC = '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48'


def test_address_and_precision():
    assert g.encode_address(WALLET).endswith('1'*40)
    assert g.numeric_string(10**18+12, 18) == '1.000000000000000012'
    assert g.as_decimal('NaN') is None
    assert g.as_decimal('Infinity') is None


def test_direct_approval_candidate():
    tx = {'from': {'hash': WALLET}, 'to': {'hash': USDC}, 'status': 'ok',
          'raw_input': '0x095ea7b3' + g.encode_address(SPENDER) + f'{g.MAX_UINT256:064x}', 'hash': '0x'+'a'*64}
    c = g.candidate_from_tx(tx, WALLET)
    assert c['contract'] == USDC
    assert c['spender'].lower() == SPENDER.lower()
    assert c['kind'] == 'erc20'
    tx['status'] = 'error'
    assert g.candidate_from_tx(tx, WALLET) is None


def test_token_parsing_never_invents_market_price():
    row = {'token': {'type': 'ERC-20','address_hash': USDC,'decimals':'6','symbol':'USDC','exchange_rate':'1'},'value':'1300000'}
    t = g.parse_token(row, 'ethereum', 'https://etherscan.io')
    assert t['balance'] == '1.3' and t['usd_value'] == '1.3'
    row['token'].pop('exchange_rate')
    assert g.parse_token(row,'ethereum','https://etherscan.io')['usd_value'] is None


def test_sweeper_requires_repeat():
    def tx(src, dest, v, t, nonce):
        return {'from':{'hash':src},'to':{'hash':dest},'value':str(v),'timestamp':t,'status':'ok','hash':'0x'+f'{nonce:064x}'}
    other='0x3333333333333333333333333333333333333333'
    txs=[tx(other,WALLET,1000,'2026-11-03T09:00:00Z',1),tx(WALLET,SPENDER,900,'2026-11-03T09:00:05Z',2),tx(other,WALLET,1000,'2026-11-03T10:00:00Z',3),tx(WALLET,SPENDER,900,'2026-11-03T10:00:04Z',4)]
    report=g.find_sweeper_pattern(txs,WALLET,'https://etherscan.io')
    assert report['status']=='pattern_detected' and len(report['incidents'])==2
    assert g.find_sweeper_pattern(txs[:2],WALLET,'https://etherscan.io')['status']=='no_pattern_in_sample'


def test_rpc_and_indexer_mocked_end_to_end(monkeypatch):
    monkeypatch.setattr(g,'LOG_LOOKBACK',0)  # RPC log behavior covered separately
    raw='0x095ea7b3'+g.encode_address(SPENDER)+f'{g.MAX_UINT256:064x}'
    calls=[]
    def handler(request):
        if request.method=='POST':
            payload=__import__('json').loads(request.content)
            method=payload['method'];calls.append(method)
            if method=='eth_chainId': val=hex(1)
            elif method=='eth_blockNumber': val=hex(20_000_000)
            elif method=='eth_getBalance': val=hex(1234000000000000)
            elif method=='eth_getCode': val='0x'
            elif method=='eth_call':
                data=payload['params'][0]['data']
                if data.startswith('0xdd62ed3e') and data.endswith(g.encode_address(SPENDER)):
                    val=hex(g.MAX_UINT256)
                elif data.startswith('0x70a08231') and payload['params'][0]['to'].lower() == USDC.lower():
                    val=hex(1300000)
                elif data.startswith('0x313ce567') and payload['params'][0]['to'].lower() == USDC.lower():
                    val=hex(6)
                else: val='0x0'
            elif method=='eth_getLogs': val=[]
            else: raise AssertionError(method)
            return httpx.Response(200,json={'jsonrpc':'2.0','id':7,'result':val})
        path=request.url.path
        if 'coins.llama.fi' in request.url.host:
            import time
            return httpx.Response(200, json={'coins': {'ethereum:'+USDC.lower(): {'price': 1, 'timestamp': int(time.time()), 'confidence': 0.99}, 'coingecko:ethereum': {'price': 2500, 'timestamp': int(time.time()), 'confidence': 0.99}}})
        if path.endswith('/tokens'):
            if 'ERC-721' in str(request.url): obj={'items':[],'next_page_params':None}
            else: obj={'items':[{'token':{'type':'ERC-20','address_hash':USDC,'decimals':'6','symbol':'USDC','exchange_rate':'1'},'value':'1300000'}],'next_page_params':None}
        elif path.endswith('/transactions'):
            obj={'items':[{'from':{'hash':WALLET},'to':{'hash':USDC},'status':'ok','raw_input':raw,'hash':'0x'+'f'*64,'value':'0'}],'next_page_params':None}
        elif path.endswith('/stats'): obj={'coin_price':'2500.00'}
        else: raise AssertionError(path)
        return httpx.Response(200,json=obj)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await g.scan_chain(client,'ethereum',g.CHAINS['ethereum'],WALLET)
    result=asyncio.run(run())
    assert result['native_status']=='verified' and result['native_balance']=='0.001234'
    assert result['tokens'][0]['usd_value']=='1.3'
    assert result['tokens'][0]['balance_verification']=='verified'
    assert result['tokens'][0]['price_source']=='defillama_by_chain_and_contract'
    assert len(result['approvals'])==1
    assert result['approvals'][0]['unlimited'] is True
    assert result['coverage']['approvals_completeness']=='partial_historical_discovery'
    assert 'eth_call' in calls


def test_wrong_rpc_chain_id_rejected():
    def handler(request):
        body=__import__('json').loads(request.content)
        value='0x38' if body['method']=='eth_chainId' else '0x1'
        return httpx.Response(200,json={'result':value})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await g.scan_chain(client,'ethereum',g.CHAINS['ethereum'],WALLET)
    result=asyncio.run(run())
    assert result['native_status']=='unverified'
    assert 'mismatch' in result['error']
    assert result['approvals']==[]


def test_rpc_event_candidate_and_revoked_approval():
    log={'address':USDC,'topics':[g.APPROVAL_TOPIC,'0x'+g.encode_address(WALLET),'0x'+g.encode_address(SPENDER)],'data':'0x'+'f'*64,'transactionHash':'0x'+'a'*64}
    c=g.decode_log_candidate(log,WALLET,g.APPROVAL_TOPIC,'erc20')
    assert c['spender'].lower()==SPENDER.lower()
    async def run():
        def handler(request):
            return httpx.Response(200,json={'result':'0x0'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await g.check_candidate(client,'https://rpc.invalid',WALLET,c,{},'https://etherscan.io')
    assert asyncio.run(run()) is None  # history is not a live authorization


def test_permit2_recent_permission_is_expiry_aware(monkeypatch):
    monkeypatch.setattr(g,'LOG_LOOKBACK',10)
    topic='0x'+'f'*64
    log={'topics':[topic,'0x'+g.encode_address(WALLET),'0x'+g.encode_address(USDC),'0x'+g.encode_address(SPENDER)],'transactionHash':'0x'+'e'*64}
    def handler(req):
        body=__import__('json').loads(req.content)
        if body['method']=='eth_getLogs':value=[log]
        else:
            amount=42
            expiry=2_100_000_000
            value='0x'+f'{amount:064x}{expiry:064x}{1:064x}'
        return httpx.Response(200,json={'result':value})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await g.scan_permit2(client,'https://rpc.invalid',100,WALLET,{USDC.lower():{'symbol':'USDC','decimals':6}},'https://etherscan.io')
    result,coverage=asyncio.run(run())
    assert coverage['status']=='bounded'
    assert len(result)==1 and result[0]['kind']=='permit2_spender'
    assert result[0]['allowance']=='0.000042'
    assert result[0]['expiration']==2_100_000_000

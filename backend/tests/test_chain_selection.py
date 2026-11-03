"""No external network. Verify API *actually* scans only the user's chosen chains."""
import asyncio
import sys
from pathlib import Path
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main

WALLET='0x1111111111111111111111111111111111111111'


def test_one_chain_skips_others(monkeypatch):
    calls=[]
    async def fake_scan(client,key,cfg,address):
        calls.append(key)
        return {'chain':key,'name':cfg['name'],'native_status':'verified',
                'native_balance':'0','native_usd':None,'tokens':[],'approvals':[],
                'sweeper':{'status':'not_checked'},'delegation':{'status':'none_detected'},
                'quality':{'status':'incomplete'},'coverage':{'approvals_completeness':'partial_historical_discovery'}}
    monkeypatch.setattr(main,'scan_chain',fake_scan)
    async def check(payload):
        transport=httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport,base_url='http://test') as c:
            return await c.post('/api/scan',json=payload)
    result=asyncio.run(check({'address':WALLET,'chains':['bsc']}))
    assert result.status_code==200,result.text
    assert calls==['bsc']
    assert [x['chain'] for x in result.json()['chains']]==['bsc']
    assert result.json()['summary']['never_a_safety_clearance'] is True
    assert result.json()['summary']['all_approvals_status']=='UNKNOWN_INCOMPLETE'


def test_invalid_chains_rejected_without_scan(monkeypatch):
    async def fake_scan(*_):
        raise AssertionError('invalid selection must never start RPC')
    monkeypatch.setattr(main,'scan_chain',fake_scan)
    async def check(payload):
        transport=httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport,base_url='http://test') as c:
            return await c.post('/api/scan',json=payload)
    for chains in ([],['solana'],['bsc','bsc'],['bsc','__proto__'],['bsc']*5):
        response=asyncio.run(check({'address':WALLET,'chains':chains}))
        assert response.status_code==422,(chains,response.text)


def test_chains_metadata():
    async def check():
        transport=httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport,base_url='http://test') as c:
            return await c.get('/api/chains')
    response=asyncio.run(check())
    assert response.status_code==200
    assert set(x['key'] for x in response.json()['chains'])=={'bsc','ethereum','base','arbitrum'}

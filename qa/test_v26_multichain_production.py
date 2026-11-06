"""Four-chain production-candidate offline invariants and failure injection."""
import asyncio
import json
import sys
from pathlib import Path
from copy import deepcopy
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from inventory_sources import union_token_candidates, inventory_status, asset_register
import main

W='0x'+'1'*40
TOKEN='0x'+'2'*40
NFT='0x'+'3'*40


def test_provider_union_retains_spam_and_provenance_and_conflicts():
    a={'contract':TOKEN,'source':'blockscout-indexer','raw_balance':'3','symbol':'S','possible_spam':False}
    b={'contract':TOKEN,'source':'moralis-indexer','raw_balance':'4','symbol':'S','possible_spam':True}
    rows, report=union_token_candidates([a],[b])
    assert len(rows)==1 and report['unique_contracts']==1
    assert report['provider_balance_conflicts']==1
    assert rows[0]['provider_balance_conflict'] is True
    assert rows[0]['possible_spam'] is True
    assert set(rows[0]['discovered_by'])=={'moralis-indexer','blockscout-indexer'}
    assert not rows[0].get('usd_value')


def test_one_provider_down_is_not_reported_as_complete():
    assert inventory_status([{'state':'exhausted'},{'state':'unavailable'}]) == 'PARTIAL_SOURCE_COVERAGE'
    assert inventory_status([{'state':'unavailable'}]) == 'SOURCE_UNAVAILABLE'
    assert inventory_status([{'state':'exhausted'}]) == 'SOURCE_PAGES_EXHAUSTED_NOT_GLOBAL'


def test_four_chain_keys_and_review_spam_nft_no_fake_usd():
    chains=[]
    for key,cfg in main.CHAINS.items():
        chains.append({'chain':key,'chain_id':cfg['id'],'symbol':cfg['symbol'],
                       'native_status':'verified','native_balance':'0.001','native_usd':None,
                       'tokens':[{'contract':TOKEN,'symbol':'FREE','balance_verification':'not_checked_rpc_budget',
                                 'asset_category':'suspected_spam','raw_balance':'999','usd_value':'1000000',
                                 'trusted_usd_eligible':False,'source':'indexer'}],
                       'nft_assets':[{'standard':'ERC-721','contract':NFT,'token_id':'7','symbol':'NFT','balance':'1'}],
                       'coverage':{'inventory_sources':[{'name':'blockscout','state':'partial'}]}})
    out=asset_register(chains)
    assert out['discovered_assets']==12
    assert len({a['id'] for a in out['assets']})==12
    assert all(a['value_usd'] is None for a in out['assets'])
    assert all(c['source_status']=='PARTIAL_SOURCE_COVERAGE' for c in out['chains'])
    assert out['revoke_enabled'] is False


def test_unchanged_provider_list_is_not_lost_when_second_page_fails(monkeypatch):
    n=0
    async def mock_get(client,base,path,params=None):
        nonlocal n
        n+=1
        if n==1:return {'items':[{'marker':'page-one'}], 'next_page_params':{'cursor':'again'}}
        raise ConnectionError('simulated page two failure')
    monkeypatch.setattr(main,'indexer_get',mock_get)
    rows,complete=asyncio.run(main.indexer_pages(None,'https://api.example','/token',5))
    assert rows==[{'marker':'page-one'}] and complete is False


def test_looping_cursor_does_not_mark_complete(monkeypatch):
    async def mock_get(client,base,path,params=None):
        return {'items':[{'marker':'page'}], 'next_page_params':{'cursor':'loop'}}
    monkeypatch.setattr(main,'indexer_get',mock_get)
    rows,complete=asyncio.run(main.indexer_pages(None,'https://api.example','/token',8))
    assert len(rows)==2 and complete is False


def test_missing_decimals_is_unpriced_and_not_fabricated():
    item={'token':{'type':'ERC-20','address_hash':TOKEN,'symbol':'UNK'},'value':'12345'}
    row=main.parse_token(item,'base','https://basescan.org')
    assert row['raw_balance']=='12345'
    assert row['decimals'] is None and row['balance'] is None


def test_revoke_public_boundaries_explicitly_off():
    from public_api import app as public
    methods={(getattr(route,'path',None), m) for route in public.routes for m in (getattr(route,'methods',set()) or set())}
    assert not any('revoke' in (path or '').lower() or 'sign' in (path or '').lower() for path,_ in methods)
    assert ('/api/scan','POST') in methods
    from public_api import public_health
    health=public_health()
    assert health['wallet_signing'] is False and health['revoke_endpoints'] is False

@pytest.mark.parametrize('key',list(main.CHAINS))
def test_chain_discovery_ledger_each_network(monkeypatch,key):
    cfg=main.CHAINS[key]
    monkeypatch.setenv('INDEXER_'+key.upper(),'https://mock-indexer.example/api/v2')
    monkeypatch.delenv('MORALIS_API_KEY',raising=False)
    async def rpc(client,url,method,params):
        return {'eth_chainId':hex(cfg['id']),'eth_blockNumber':hex(123),'eth_getBalance':hex(10**18),'eth_getCode':'0x'}[method]
    async def pages(client,base,path,limit,params=None):
        if path.endswith('/tokens'):
            return ([{'token':{'type':'ERC-20','address_hash':TOKEN,'symbol':'AIR','decimals':18,'reputation':'spam'},'value':str(10**18)}], False)
        return ([],True)
    async def get(client,base,path,params=None):
        if path.endswith('/token-balances'):return []
        if path.endswith('/stats'):return {'coin_price':None}
        raise RuntimeError('no indexer endpoint')
    async def assets(client,rpc_call,rpc_url,wallet,chain,block,tokens,known,explorer):
        assert len(tokens)==1
        return [{**tokens[0],'balance_verification':'verified','balance_source':'onchain_at_block','usd_value':None}], {
            'balance_verification_failures':0, 'price_service':'no_quote', 'candidates_not_checked':0}
    async def native(client,key):return None,'unavailable'
    async def logs(*args,**kwargs):return [],{'status':'not_checked'}
    async def permit(*args,**kwargs):return [],{'status':'not_checked'}
    async def check(*args,**kwargs):return None
    for n,v in [('rpc',rpc),('indexer_pages',pages),('indexer_get',get),('reconcile_assets',assets),('native_usd_quote',native),('fetch_rpc_logs',logs),('scan_permit2',permit),('check_candidate',check)]:
        monkeypatch.setattr(main,n,v)
    out=asyncio.run(main.scan_chain(None,key,cfg,W))
    assert out['coverage']['inventory_status']=='PARTIAL_SOURCE_COVERAGE'
    assert out['coverage']['provider_merge']['unique_contracts']==1
    assert len(out['tokens'])==1 and out['tokens'][0]['asset_category']=='suspected_spam'

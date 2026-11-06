"""V2.6 inventory integration: Blockscout/Routescan token balances + NFT listings."""
import asyncio
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import main

OWNER='0x'+'1'*40
T1='0x'+'2'*40
T2='0x'+'3'*40
NFT='0x'+'4'*40


def test_combined_token_balances_preserve_spam_and_nft(monkeypatch):
    # Mock a functional Blockscout-compatible BSC provider; real Routescan requires configured credentials.
    monkeypatch.setenv("INDEXER_BSC", "https://mock-indexer.example/api/v2")
    async def rpc(client,url,method,params):
        return {'eth_chainId':hex(56),'eth_blockNumber':hex(123),'eth_getBalance':hex(10**17),'eth_getCode':'0x'}[method]
    async def pages(client,base,path,limit,params=None):
        if path.endswith('/tokens'):
            return ([{'token':{'type':'ERC-20','address_hash':T1,'symbol':'GOOD','decimals':'18'},'value':str(10**18)}],True)
        if path.endswith('/nft'):
            return ([{'token':{'type':'ERC-721','address_hash':NFT,'symbol':'NFT','name':'My NFT'},'id':'5','value':'1'},
                     {'token':{'type':'ERC-1155','address_hash':NFT},'token_instance':'bad_string','value':'1'}],True)
        if path.endswith('/transactions'):return ([],True)
        raise AssertionError(path)
    async def get(client,base,path,params=None):
        if path.endswith('/token-balances'):
            return [{'token':{'type':'ERC-20','address_hash':T2,'symbol':'CLAIM','decimals':'18','reputation':'spam'},'value':str(10**18)}]
        if path.endswith('/stats'):return {'coin_price':'300'}
        raise AssertionError(path)
    async def assets(client,rpc_call,rpc_url,wallet,chain,block,tokens,known,explorer):
        assert len(tokens)==2, 'Inventory must include both token API and token-balances endpoint'
        result=[]
        for t in tokens:
            t=dict(t,balance_verification='verified',balance_source='onchain_at_block',price_status='unavailable_or_stale',usd_value=None)
            result.append(t)
        return result,{'balance_verification_failures':0,'price_service':'unavailable','candidates_not_checked':0}
    async def quote(client,key):return None,'unavailable'
    async def logs(*args,**kwargs):return [],{'status':'not_checked'}
    async def permit(*args,**kwargs):return [],{'status':'not_checked'}
    async def check(*args,**kwargs):return None
    monkeypatch.setattr(main,'rpc',rpc)
    monkeypatch.setattr(main,'indexer_pages',pages)
    monkeypatch.setattr(main,'indexer_get',get)
    monkeypatch.setattr(main,'native_usd_quote',quote)
    monkeypatch.setattr(main,'reconcile_assets',assets)
    monkeypatch.setattr(main,'fetch_rpc_logs',logs)
    monkeypatch.setattr(main,'scan_permit2',permit)
    monkeypatch.setattr(main,'check_candidate',check)
    r=asyncio.run(main.scan_chain(None,'bsc',main.CHAINS['bsc'],OWNER))
    assert {t['contract'].lower() for t in r['tokens']}=={T1.lower(),T2.lower()}
    assert len(r['nft_assets'])==1
    assert r['nft_assets'][0]['token_id']=='5'
    assert r['nft_assets'][0]['verification_status']=='INDEXER_REPORTED_NOT_ONCHAIN_RECHECKED'
    assert r['coverage']['token_balance_endpoint'].startswith('returned_1_entries')
    assert any(t['asset_category']=='suspected_spam' for t in r['tokens'])


def test_bsc_unconfigured_routescan_is_reported_as_partial(monkeypatch):
    monkeypatch.delenv('BLOCKSCOUT_API_KEY',raising=False)
    monkeypatch.delenv('INDEXER_BSC',raising=False)
    async def rpc(client,url,method,params):
        return {'eth_chainId':hex(56),'eth_blockNumber':hex(123),'eth_getBalance':hex(10**17),'eth_getCode':'0x'}[method]
    async def quote(client,key):return None,'unavailable'
    async def assets(client,rpc_call,rpc_url,wallet,chain,block,tokens,known,explorer):
        return [],{'balance_verification_failures':0,'price_service':'unavailable','candidates_not_checked':0}
    async def logs(*args,**kwargs):return [],{'status':'not_checked'}
    async def permit(*args,**kwargs):return [],{'status':'not_checked'}
    async def check(*args,**kwargs):return None
    monkeypatch.setattr(main,'rpc',rpc)
    monkeypatch.setattr(main,'native_usd_quote',quote)
    monkeypatch.setattr(main,'reconcile_assets',assets)
    monkeypatch.setattr(main,'fetch_rpc_logs',logs)
    monkeypatch.setattr(main,'scan_permit2',permit)
    monkeypatch.setattr(main,'check_candidate',check)
    result=asyncio.run(main.scan_chain(None,'bsc',main.CHAINS['bsc'],OWNER))
    assert result['coverage']['bsc_indexer_auth']=='ROUTESCAN_PAID_KEY_MISSING__INDEXER_DISCOVERY_DISABLED'
    assert result['coverage']['token_index'].startswith('unavailable:')

"""V2.6 evidence-preserving token discovery regression tests."""
from pathlib import Path
import asyncio
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import asset_valuation as av
from forensic import classify_token

ADDR='0x'+'1'*40

def contract(i: int) -> str:
    return '0x'+format(i+10,'040x')

def test_all_indexer_candidates_preserved_even_when_budget_exceeded(monkeypatch):
    n=av.MAX_INDEXED_CANDIDATES+9
    tokens=[{'contract':contract(i),'symbol':('SCAM' if i==0 else f'UNK{i}'),
             'name':f'Test {i}', 'balance':'1.0','raw_balance':'1000000000000000000',
             'decimals':18,'possible_spam':i==0,'source':'indexer'} for i in range(n)]
    calls=[]
    async def mock_rpc(client,url,method,params):
        calls.append(method)
        if params[0]['data'].startswith('0x70a08231'):
            return hex(10**18)
        return hex(18)
    async def mock_quotes(client,chain,contracts):
        return {},'provider_unavailable'
    async def mock_coingecko(client,chain,contracts):
        return {}
    monkeypatch.setattr(av,'contract_quotes',mock_quotes)
    monkeypatch.setattr(av,'coingecko_token_quotes',mock_coingecko)
    result,stats=asyncio.run(av.reconcile_assets(None,mock_rpc,'https://rpc.invalid',ADDR,'ethereum',123,tokens,[], 'https://etherscan.io'))
    assert len(result)==n
    assert len(set(t['contract'] for t in result))==n
    assert stats['preserved_unverified_due_to_rpc_budget']==9
    assert stats['candidates_not_checked']==9
    assert len([x for x in result if x['balance_verification']=='not_checked_rpc_budget'])==9
    assert all(x['usd_value'] is None for x in result)
    assert all(not classify_token(x,'ethereum')['trusted_usd_eligible'] for x in result)
    assert classify_token(result[0],'ethereum')['asset_category']=='suspected_spam'


def test_explicit_spam_is_not_trusted_even_with_a_quote():
    item={'contract':contract(101),'symbol':'AXS','balance':'50000','balance_verification':'verified',
          'usd_value':'1000000000','price_source':'defillama_by_chain_and_contract','possible_spam':True}
    result=classify_token(item,'ethereum')
    assert result['asset_category']=='suspected_spam'
    assert not result['trusted_usd_eligible']


def test_unverified_indexer_but_positive_balance_not_marked_zero():
    item={'contract':contract(222),'symbol':'DUST','balance':'10','balance_verification':'not_checked_rpc_budget'}
    result=classify_token(item,'base')
    assert result['asset_category']=='not_verified'
    assert result['balance']=='10'
    assert result['display_balance']=='10'

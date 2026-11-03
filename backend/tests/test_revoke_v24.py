"""No real blockchain calls or signatures are made in these tests."""
import os
import sys
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from revoke_engine import (verify_request, inspect_receipt, normalize_request,
                           UnsafeIntent, expected_transaction, PERMIT2)
from main import app, CHAINS

OWNER='0x'+'11'*20
TOKEN='0x'+'22'*20
SPENDER='0x'+'33'*20
TX='0x'+'aa'*32


def word(value): return '0x'+format(value,'064x')
def req(kind='erc20', token_id=None):
    return normalize_request(OWNER,'bsc',kind,TOKEN,SPENDER,token_id,CHAINS)


@pytest.mark.asyncio
async def test_erc20_live_allowance_prepares_only_zero_approval():
    calls=[]
    async def fake(method, params):
        calls.append((method,params))
        return {'eth_chainId':'0x38','eth_getCode':'0x60016000','eth_call':word(12)}[method]
    data=await verify_request(req(),fake,56)
    assert data['to']==TOKEN
    assert data['data']=='0x095ea7b3'+SPENDER[2:].rjust(64,'0')+'0'*64
    assert data['current_permission']=='12'
    assert not any(method in ('eth_sendTransaction','eth_sign','personal_sign') for method,_ in calls)


@pytest.mark.asyncio
async def test_zero_allowance_fails_closed():
    async def fake(method, params):
        return {'eth_chainId':'0x38','eth_getCode':'0x6060','eth_call':word(0)}[method]
    with pytest.raises(UnsafeIntent,match='already zero'):
        await verify_request(req(),fake,56)


@pytest.mark.asyncio
async def test_wrong_chain_fails_closed():
    async def fake(method, params): return '0x1'
    with pytest.raises(UnsafeIntent,match='chain ID mismatch'):
        await verify_request(req(),fake,56)


@pytest.mark.asyncio
async def test_nft_operator_revoke_bool_false():
    async def fake(method, params):
        return {'eth_chainId':'0x38','eth_getCode':'0x6000','eth_call':word(1)}[method]
    data=await verify_request(req('nft_operator'),fake,56)
    assert data['data']=='0xa22cb465'+SPENDER[2:].rjust(64,'0')+'0'*64


@pytest.mark.asyncio
async def test_permit2_revoke_zero_amount_and_expiry():
    async def fake(method, params):
        if method=='eth_getCode':
            assert params[0].lower()==PERMIT2.lower()
            return '0x6000'
        if method=='eth_call': return '0x'+format(800,'064x')+format(int(time.time())+400,'064x')+'0'*64
        return '0x38'
    data=await verify_request(req('permit2'),fake,56)
    assert data['to'].lower()==PERMIT2.lower()
    assert data['data'].startswith('0x87517c45')
    assert data['data'].endswith('0'*128)


@pytest.mark.asyncio
async def test_erc721_single_token_owner_checked_even_large_id():
    large='1234567891011121314151617181920212223242'
    async def fake(method,params):
        if method=='eth_chainId':return '0x38'
        if method=='eth_getCode':return '0x6000'
        if method=='eth_call':
            return '0x'+(SPENDER[2:] if params[0]['data'].startswith('0x081812fc') else OWNER[2:]).rjust(64,'0')
    data=await verify_request(req('nft_token',large),fake,56)
    assert data['token_id']==large
    assert data['data'].startswith('0x095ea7b3'+'0'*64)
    assert int(data['data'][-64:],16)==int(large)


@pytest.mark.asyncio
async def test_receipt_rejects_wrong_target():
    async def fake(method,params):
        if method=='eth_chainId':return '0x38'
        if method=='eth_getTransactionReceipt':return {'status':'0x1'}
        if method=='eth_getTransactionByHash':return {'from':OWNER,'to':SPENDER,'input':'0x095ea7b3'}
    with pytest.raises(UnsafeIntent,match='does not match'):
        await inspect_receipt(req(),TX,fake,56)


@pytest.mark.asyncio
async def test_receipt_confirm_requires_state_cleared():
    to,data=expected_transaction(req())
    async def fake(method,params):
        if method=='eth_chainId':return '0x38'
        if method=='eth_getTransactionReceipt':return {'status':'0x1'}
        if method=='eth_getTransactionByHash':return {'from':OWNER,'to':to,'input':data}
        if method=='eth_call':return word(0)
    out=await inspect_receipt(req(),TX,fake,56)
    assert out['status']=='VERIFIED_REVOKED' and out['cleared']


@pytest.mark.asyncio
async def test_receipt_not_verified_while_permission_active():
    to,data=expected_transaction(req())
    async def fake(method,params):
        if method=='eth_chainId':return '0x38'
        if method=='eth_getTransactionReceipt':return {'status':'0x1'}
        if method=='eth_getTransactionByHash':return {'from':OWNER,'to':to,'input':data}
        if method=='eth_call':return word(1)
    out=await inspect_receipt(req(),TX,fake,56)
    assert out['status']=='MINED_PERMISSION_STILL_ACTIVE'


def test_invalid_inputs_rejected():
    with pytest.raises(UnsafeIntent):normalize_request(OWNER,'bsc','erc20',OWNER,'0x'+'00'*20,None,CHAINS)
    with pytest.raises(UnsafeIntent):normalize_request(OWNER,'arbitrum','nft_token',TOKEN,SPENDER,'hello',CHAINS)
    with pytest.raises(UnsafeIntent):normalize_request(OWNER,'unknown','erc20',TOKEN,SPENDER,None,CHAINS)


def test_analytics_consent_admin_and_erasure(tmp_path,monkeypatch):
    monkeypatch.setenv('GUARDIAN_ANALYTICS_DB',str(tmp_path/'counts.db'))
    monkeypatch.setenv('GUARDIAN_ANALYTICS_SECRET_FILE',str(tmp_path/'salt'))
    monkeypatch.setenv('GUARDIAN_ANALYTICS_ADMIN_KEY','this_is_a_long_random_owner_test_key_123456')
    visitor='30308d9a-eaab-4d19-9905-22e33a75bb20'
    with TestClient(app) as client:
        assert client.get('/api/analytics/summary').status_code==401
        assert client.post('/api/analytics/event',json={'visitor_id':visitor,'event':'wallet_address'}).status_code==422
        assert client.post('/api/analytics/event',json={'visitor_id':visitor,'event':'visit'}).json()['counted']
        assert not client.post('/api/analytics/event',json={'visitor_id':visitor,'event':'visit'}).json()['counted']
        assert client.post('/api/analytics/event',json={'visitor_id':visitor,'event':'scan_complete'}).json()['counted']
        stats=client.get('/api/analytics/summary',headers={'X-Guardian-Admin':os.environ['GUARDIAN_ANALYTICS_ADMIN_KEY']}).json()
        assert stats['opted_in_unique_browsers']==1 and stats['completed_scans_reported']==1
        assert client.post('/api/analytics/erase',json={'visitor_id':visitor}).json()['erased']
        stats=client.get('/api/analytics/summary',headers={'X-Guardian-Admin':os.environ['GUARDIAN_ANALYTICS_ADMIN_KEY']}).json()
        assert stats['opted_in_unique_browsers']==0
        raw=(tmp_path/'counts.db').read_bytes()
        assert OWNER.encode() not in raw and visitor.encode() not in raw


def test_aggregate_scan_count_privacy(tmp_path,monkeypatch):
    from analytics import record_aggregate_scan
    monkeypatch.setenv('GUARDIAN_ANALYTICS_DB',str(tmp_path/'counts.db'))
    monkeypatch.setenv('GUARDIAN_ANALYTICS_SECRET_FILE',str(tmp_path/'secret'))
    monkeypatch.setenv('GUARDIAN_ANALYTICS_ADMIN_KEY','this_is_a_long_random_owner_test_key_123456')
    record_aggregate_scan(); record_aggregate_scan()
    with TestClient(app) as c:
        d=c.get('/api/analytics/summary',headers={'X-Guardian-Admin':os.environ['GUARDIAN_ANALYTICS_ADMIN_KEY']}).json()
        assert d['all_scans_aggregate']==2
        assert d['opted_in_unique_browsers']==0
        assert d['history_14d'][-1]['all_scans']==2
    raw=(tmp_path/'counts.db').read_bytes()
    assert OWNER.encode() not in raw and TOKEN.encode() not in raw

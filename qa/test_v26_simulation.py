from pathlib import Path
import importlib.util
import pytest

FILE=Path(__file__).with_name('testnet_revoke_simulation.py')
spec=importlib.util.spec_from_file_location('v26_revoke_sim',FILE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

OWNER='0x'+'1'*40
TOKEN='0x'+'2'*40
SPENDER='0x'+'3'*40

def test_mainnet_hard_rejected():
    with pytest.raises(ValueError,match='TESTNET ONLY'):
        mod.plan('ethereum','erc20',OWNER,TOKEN,SPENDER)

def test_exact_erc20_calldata():
    p=mod.plan('sepolia','erc20',OWNER,TOKEN,SPENDER)
    assert p['tx']['data']=='0x095ea7b3'+mod.word(SPENDER)+mod.uint_word(0)
    assert p['tx']['to']==TOKEN and not p['broadcast']

def test_nft_operator_off():
    for kind in ['erc721_operator','erc1155_operator']:
        p=mod.plan('bsc-testnet',kind,OWNER,TOKEN,SPENDER)
        assert p['tx']['data']=='0xa22cb465'+mod.word(SPENDER)+mod.uint_word(0)

def test_nft_single_zero_address():
    p=mod.plan('base-sepolia','erc721_token',OWNER,TOKEN,SPENDER,'7')
    assert p['tx']['data']=='0x095ea7b3'+mod.uint_word(0)+mod.uint_word(7)

def test_permit2_offline_only():
    p=mod.plan('sepolia','permit2_allowance',OWNER,TOKEN,SPENDER)
    assert p['tx']['to']==mod.PERMIT2.lower()
    assert p['tx']['data'].startswith('0x87517c45')
    with pytest.raises(ValueError,match='deployment identity'):
        mod.simulate_live(p,'https://dummy.example')

def test_bad_address_and_big_token_id_blocked():
    with pytest.raises(ValueError):mod.plan('sepolia','erc20',OWNER,'0x'+'0'*40,SPENDER)
    with pytest.raises(ValueError):mod.plan('sepolia','erc721_token',OWNER,TOKEN,SPENDER,str(2**256))

def test_rpc_allowlist_rejects_send():
    with pytest.raises(ValueError,match='read-only'):
        mod.rpc_request('https://example.com','eth_sendTransaction',[])

def test_wrong_chain_blocks_before_simulation():
    p=mod.plan('sepolia','erc20',OWNER,TOKEN,SPENDER)
    called=[]
    def rpc(url,method,params):
        called.append(method)
        return '0x1'
    with pytest.raises(ValueError,match='chain ID mismatch'):
        mod.simulate_live(p,'https://dummy.example',request=rpc)
    assert called==['eth_chainId']

def test_safe_positive_rpc_simulated_never_sent():
    p=mod.plan('sepolia','erc20',OWNER,TOKEN,SPENDER)
    called=[]
    def rpc(url,method,params):
        called.append(method)
        if method=='eth_chainId':return hex(mod.TESTNETS['sepolia'])
        if method=='eth_getCode':return '0x6001'
        if method=='eth_call':return '0x'+'0'*63+'1'
        if method=='eth_estimateGas':return '0xc350'
        raise AssertionError(method)
    out=mod.simulate_live(p,'https://dummy.example',request=rpc)
    assert out['status']=='TESTNET_SIMULATED_NOT_SENT'
    assert out['estimated_gas']==50000 and not out['broadcast']
    assert not any(x.startswith('eth_send') or x.startswith('personal_') for x in called)

import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'benchmark'))
import compare_offline as b

def test_comparison_strictly_chain_scoped():
    t={'chain_id':56,'standard':'ERC-20','contract':'0x'+'a'*40}
    u={**t,'chain_id':8453}
    assert b.asset_key(t)!=b.asset_key(u)
    assert b.score({b.asset_key(t)}, {b.asset_key(u)})['recall']==0

def test_nft_id_matters():
    t={'chain_id':1,'standard':'ERC721','contract':'0x'+'b'*40,'token_id':'5'}
    assert b.asset_key(t)!=b.asset_key({**t,'token_id':'6'})

def test_approval_key_preserves_spender_and_permission_kind():
    a={'chain_id':56,'standard':'PERMIT2','contract':'0x'+'c'*40,'spender':'0x'+'d'*40}
    assert b.permission_key(a)!=b.permission_key({**a,'spender':'0x'+'e'*40})
    assert b.permission_key(a)!=b.permission_key({**a,'standard':'ERC20'})

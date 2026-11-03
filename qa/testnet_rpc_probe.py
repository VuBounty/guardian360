"""READ-ONLY testnet RPC connectivity probe. No keys, signatures, transactions."""
import json, os, sys, urllib.request
rpc=os.getenv('GUARDIAN_TESTNET_RPC','')
chain=int(os.getenv('GUARDIAN_TESTNET_CHAIN_ID','97'))
if not rpc.startswith('https://') or chain not in (97,11155111):
    sys.exit('Set GUARDIAN_TESTNET_RPC=https://... and GUARDIAN_TESTNET_CHAIN_ID=97 or 11155111')
def call(method,params=[]):
    body=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode()
    req=urllib.request.Request(rpc,body,{'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req, timeout=12) as res: data=json.load(res)
    if data.get('error'): raise RuntimeError(str(data['error'])[:160])
    return data['result']
actual=int(call('eth_chainId'),16)
assert actual==chain,f'Network mismatch: expected {chain}, got {actual}'
print(json.dumps({'testnet_chain_id':actual,'head_block':int(call('eth_blockNumber'),16),'readonly_probe':'PASS','signed_transaction':'NOT ATTEMPTED'},indent=2))

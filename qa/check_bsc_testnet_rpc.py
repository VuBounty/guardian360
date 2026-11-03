#!/usr/bin/env python3
"""Read-only BSC testnet connectivity check. No wallet, keys or send transaction."""
from urllib.request import Request, urlopen
import json, os, sys
RPC = os.getenv('BSC_TESTNET_RPC','https://bsc-testnet-dataseed.bnbchain.org')
def call(method):
    req=Request(RPC, data=json.dumps({'jsonrpc':'2.0','method':method,'params':[],'id':1}).encode(),headers={'Content-Type':'application/json','User-Agent':'Guardian360-Testnet-ReadOnly/1.0'},method='POST')
    with urlopen(req,timeout=12) as response: result=json.load(response)
    if 'error' in result: raise RuntimeError(result['error'])
    return result['result']
try:
    chain=call('eth_chainId'); block=call('eth_blockNumber')
    result={'network':'BSC TESTNET','rpc':RPC,'chain_id':int(chain,16),'latest_block':int(block,16),'chain_id_verified':int(chain,16)==97,'send_transaction_performed':False}
    print(json.dumps(result,indent=2))
    if not result['chain_id_verified']: sys.exit(2)
except Exception as exc:
    print(json.dumps({'status':'INCONCLUSIVE','error':str(exc)[:250],'send_transaction_performed':False},indent=2)); sys.exit(1)

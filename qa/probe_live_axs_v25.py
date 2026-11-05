#!/usr/bin/env python3
"""Independent BSC AXS balance witness, read-only; run on owner's Mac.

Never sends wallet connection, signature, transaction, API secret, or tracking
telemetry. This live witness is NOT proof of complete token discovery.
"""
import json
import re
import sys
import time
import urllib.request
from decimal import Decimal
from pathlib import Path

DEFAULT_WALLET = None
AXS = '0x715d400f88c167884bbcc41c5fea407ed4d2f8a0'
RPCS = ('https://bsc-dataseed.bnbchain.org',
        'https://bsc-dataseed-public.bnbchain.org',
        'https://bsc-rpc.publicnode.com')
ADDRESS = re.compile(r'^0x[0-9a-fA-F]{40}$')


def post_rpc(url, method, params):
    data=json.dumps({'jsonrpc':'2.0','id':25,'method':method,'params':params}).encode()
    req=urllib.request.Request(url,data=data,headers={'Content-Type':'application/json','User-Agent':'Guardian360-asset-witness/2.5'},method='POST')
    with urllib.request.urlopen(req,timeout=15) as response:
        obj=json.load(response)
    if obj.get('error') or not isinstance(obj.get('result'),str):
        raise RuntimeError('RPC returned error / missing result')
    return obj['result']


def get_price():
    key='bsc:'+AXS.lower()
    req=urllib.request.Request('https://coins.llama.fi/prices/current/'+key,
            headers={'User-Agent':'Guardian360-asset-witness/2.5'})
    with urllib.request.urlopen(req,timeout=15) as response:
        obj=json.load(response)
    rec=(obj.get('coins') or {}).get(key)
    if not isinstance(rec,dict):
        return None
    price=Decimal(str(rec['price']))
    updated=int(rec['timestamp'])
    confidence=rec.get('confidence')
    if not price.is_finite() or price<=0 or not 0 <= int(time.time())-updated <= 1800:
        return None
    if confidence is not None and Decimal(str(confidence)) < Decimal('0.8'):
        return None
    return {'usd_price':format(price,'f'),'timestamp':updated,
            'confidence':confidence,'source':'DefiLlama: BSC contract address'}


def main():
    wallet=sys.argv[1] if len(sys.argv)>1 else DEFAULT_WALLET
    out=Path(sys.argv[2]).expanduser() if len(sys.argv)>2 else Path.home()/'Myproject/GUARDIAN360/guardian360-v2.5-asset-evidence.local.json'
    if not ADDRESS.fullmatch(wallet):
        raise SystemExit('Invalid wallet; supply a public EVM address only')
    witness={'wallet':wallet,'network':'BNB Smart Chain','chain_id':56,
             'token_contract':AXS, 'token_symbol':'AXS','read_only':True,
             'verified':False, 'rpc_errors':[],'verified_at':int(time.time())}
    for endpoint in RPCS:
        try:
            cid=int(post_rpc(endpoint,'eth_chainId',[]),16)
            if cid!=56:
                raise RuntimeError('wrong network chain ID')
            block=int(post_rpc(endpoint,'eth_blockNumber',[]),16)
            h=hex(block)
            raw=int(post_rpc(endpoint,'eth_call',[{'to':AXS,'data':'0x70a08231'+wallet[2:].lower().zfill(64)},h]),16)
            dec=int(post_rpc(endpoint,'eth_call',[{'to':AXS,'data':'0x313ce567'},h]),16)
            if dec!=18 or raw<0:
                raise RuntimeError('unexpected AXS decimals / balance')
            qty=Decimal(raw)/Decimal(10**dec)
            witness.update(verified=True,endpoint=endpoint,block=block,
                raw_balance=str(raw),decimals=dec,axs_balance=format(qty,'f'))
            break
        except Exception as exc:
            witness['rpc_errors'].append(type(exc).__name__+': '+str(exc)[:130])
    if not witness['verified']:
        print('AXS LIVE VERIFICATION: UNAVAILABLE; no balance assertion made.',file=sys.stderr)
        print('RPC errors:',witness['rpc_errors'],file=sys.stderr)
        raise SystemExit(3)
    try:
        price=get_price()
        if price is not None:
            witness['price']=price
            witness['axs_estimated_usd']=format(Decimal(price['usd_price'])*Decimal(witness['axs_balance']),'f')
        else:
            witness['price_status']='UNPRICED_OR_STALE'
    except Exception as exc:
        witness['price_status']='PRICE_SOURCE_UNAVAILABLE: '+type(exc).__name__
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(witness,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print('ONCHAIN AXS BALANCE VERIFIED @ BSC BLOCK',witness['block'])
    print('WALLET:',wallet)
    print('AXS BALANCE:',witness['axs_balance'])
    print('AXS USD VALUE:',witness.get('axs_estimated_usd','UNPRICED — no invented USD total'))
    print('RELEASE EVIDENCE (LOCAL ONLY):',out)
    if Decimal(witness['axs_balance'])==0:
        print('NOTE: Zero AXS on this BSC contract. Check whether funds are on Ronin/another chain or a different wallet.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())

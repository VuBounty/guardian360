"""Offline controlled-wallet benchmark for portfolio assets and active permissions.

The inputs must be authorized exports / verified chain state. Does NOT access
third-party APIs and cannot prove superiority without measured samples.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

CHAIN_NAMES={'bsc':56,'ethereum':1,'eth':1,'base':8453,'arbitrum':42161,'arb':42161}


def _chain(x):
    v=x.get('chain_id',x.get('chain'))
    if isinstance(v,str) and not v.isdigit():
        v=CHAIN_NAMES.get(v.lower(),v)
    return int(v)


def asset_key(x):
    chain=_chain(x)
    standard=str(x.get('standard') or '').upper().replace('-','')
    if standard=='NATIVE':return f'{chain}:native'
    contract=str(x['contract']).lower()
    if not contract.startswith('0x') or len(contract)!=42:
        raise ValueError('Bad contract in benchmark input')
    if standard in ('ERC721','ERC1155'):
        return f'{chain}:{standard.lower()}:{contract}:{int(x["token_id"])}'
    if standard=='ERC20':return f'{chain}:erc20:{contract}'
    raise ValueError(f'Unknown standard: {standard}')


def permission_key(x):
    chain=_chain(x)
    standard=str(x['standard']).upper().replace('-','')
    token=str(x['contract']).lower()
    spender=str(x['spender']).lower()
    if standard not in ('ERC20','ERC721','ERC1155','PERMIT2'):
        raise ValueError('Unsupported permission kind')
    token_id=f':{int(x["token_id"])}' if standard=='ERC721' and x.get('token_id') is not None else ''
    return f'{chain}:{standard.lower()}:{token}:{spender}{token_id}'


def load(path):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(data,dict):raise ValueError('Expected JSON object')
    return data


def score(truth, candidate):
    tp=len(truth&candidate);fp=len(candidate-truth);fn=len(truth-candidate)
    return {'truth_count':len(truth),'reported_count':len(candidate),
            'matched':tp,'false_positives':fp,'missed':fn,
            'recall':round(tp/len(truth),4) if truth else None,
            'precision':round(tp/len(candidate),4) if candidate else None}


def compare(truth_file, **candidate_files):
    truth=load(truth_file)
    gt_assets={asset_key(x) for x in truth.get('assets',[])}
    gt_permissions={permission_key(x) for x in truth.get('permissions',[])}
    results={}
    for label, path in candidate_files.items():
        if not path:
            results[label]={'status':'NOT_MEASURED'}
            continue
        d=load(path)
        results[label]={'status':'OFFLINE_COMPARISON',
                        'assets':score(gt_assets,{asset_key(x) for x in d.get('assets',[])}),
                        'permissions':score(gt_permissions,{permission_key(x) for x in d.get('permissions',[])})}
    return {'method':'OFFLINE_CONTROLLED_WALLET_GROUND_TRUTH',
            'note':'No claims of superiority without controlled live exports, fixed block/time, comparable support and adequate samples.',
            'results':results}


if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--truth',required=True)
    ap.add_argument('--guardian')
    ap.add_argument('--debank')
    ap.add_argument('--revoke-cash')
    args=ap.parse_args()
    print(json.dumps(compare(args.truth,GUARDIAN_360=args.guardian,DEBANK=args.debank,REVOKE_CASH=args.revoke_cash),indent=2))

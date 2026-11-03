#!/usr/bin/env python3
"""GUARDIAN 360 — independent read-only BSC live QA from user's own Mac.

Runs a BSC-only scan against localhost FastAPI and independently checks it against
an unrelated public BSC RPC. Does NOT connect a wallet, sign, modify state, or
scrape private DeBank/Revoke.cash account data. Third-party approval/token
comparisons require a user-provided reference CSV.
"""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

ADDRESS = re.compile(r'^0x[0-9a-fA-F]{40}$')
RPC_CANDIDATES = [
    'https://bsc-rpc.publicnode.com',
    'https://bsc-dataseed1.binance.org',
    'https://bsc-dataseed.binance.org',
]
USDT = '0x55d398326f99059ff775485246999027b3197955'
USDC = '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d'
MM_DELEGATOR = '0x63c0c19a282a1b52b07dd5a65b58948a07dae32b'


def post_json(url, payload, timeout=40):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json','User-Agent':'Guardian360 BSC QA 1.0'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def rpc(endpoint, method, params):
    data = post_json(endpoint, {'jsonrpc':'2.0','id':1,'method':method,'params':params}, timeout=18)
    if 'error' in data:
        raise RuntimeError(f'{method}: {data["error"]}')
    if 'result' not in data:
        raise RuntimeError(f'{method}: missing RPC result')
    return data['result']


def pad_address(address):
    if not ADDRESS.fullmatch(address):
        raise ValueError('Address must be 20-byte hex with 0x prefix')
    return address[2:].lower().zfill(64)


def decimal_raw(raw, decimals):
    return Decimal(raw) / Decimal(10 ** decimals)


def check(status, title, detail, data=None):
    entry = {'status':status,'check':title,'detail':detail}
    if data is not None:
        entry['data'] = data
    return entry


def compare_raw_amount(label, expected_raw, observed_raw, report_block, observed_block):
    if expected_raw == observed_raw:
        return check('PASS',label,'Matched independent RPC exactly',{'raw':str(observed_raw)})
    # No state proof if nodes are at different blocks: report discrepancy, not compromise.
    status = 'FAIL' if report_block == observed_block else 'INCONCLUSIVE'
    return check(status,label,'Different balances; compare at matching blocks and inspect recent transfers',
                 {'backend_raw':str(expected_raw),'independent_raw':str(observed_raw),
                  'backend_block':report_block,'independent_block':observed_block})


def evaluate(report, independent, baseline=None):
    """Pure reconciliation: never decide wallet is safe from an empty approvals list."""
    rows = []
    chainlist = report.get('chains') or []
    scoped = len(chainlist) == 1 and chainlist[0].get('chain') == 'bsc' and report.get('requested_chains') == ['bsc']
    rows.append(check('PASS' if scoped else 'FAIL','BSC-only scope','Expected chains/requested_chains to be [bsc]'))
    if not scoped:
        return rows
    chain = chainlist[0]
    rows.append(check('PASS' if independent['chain_id']==56 else 'FAIL','Independent RPC chain ID',f'Expected 56, got {independent["chain_id"]}'))
    rows.append(check('PASS' if chain.get('native_status')=='verified' else 'FAIL','Backend RPC result',str(chain.get('native_status'))))
    raw_report = int(Decimal(chain.get('native_balance') or 0) * (10 ** 18))
    rows.append(compare_raw_amount('Native BNB balance', raw_report, independent['native_raw'], chain.get('block'), independent['block']))

    by_contract = {str(t.get('contract','')).lower():t for t in chain.get('tokens',[])}
    for name, contract, decimals in [('USDT',USDT,18),('USDC',USDC,18)]:
        known = independent.get('token_raw',{}).get(contract)
        if known is None:
            rows.append(check('INCONCLUSIVE',f'{name} ERC-20 balance','Independent eth_call unavailable; no balance assertion'))
            continue
        token = by_contract.get(contract)
        if token is None:
            rows.append(check('FAIL' if known>0 else 'PASS',f'{name} token detection',
                              'Nonzero token missing from backend' if known>0 else 'Zero-balance token need not appear'))
        else:
            rows.append(compare_raw_amount(f'{name} ERC-20 balance',int(token.get('raw_balance') or 0),known,
                                           chain.get('block'),independent['block']))
        if name=='USDT' and known is not None:
            rows.append(check('INFO','Independent USDT quantity',str(decimal_raw(known,decimals))))

    designation = independent.get('code')
    if designation is None:
        rows.append(check('INCONCLUSIVE','EIP-7702 designation','Could not independently read eth_getCode'))
    else:
        code = designation.lower()
        actual = ('0x' + code[8:48]) if code.startswith('0xef0100') and len(code)==48 else None
        backend = chain.get('delegation') or {}
        backend_delegate = str(backend.get('delegate') or '').lower() if backend.get('status')=='eip7702_delegated' else None
        if actual == backend_delegate:
            rows.append(check('PASS','EIP-7702 designation','Independent RPC agrees with backend',{'delegate':actual or 'none'}))
        else:
            rows.append(check('INCONCLUSIVE' if chain.get('block') != independent['block'] else 'FAIL',
                              'EIP-7702 designation','Different wallet code/delegate; inspect at same block',
                              {'backend_delegate':backend_delegate,'independent_delegate':actual}))
        if actual == MM_DELEGATOR:
            rows.append(check('INFO','MetaMask delegate identity','Matches bundled publicly documented MetaMask address; not a proof of safety'))

    cover = chain.get('coverage') or {}
    quality = chain.get('quality') or {}
    if not chain.get('approvals'):
        unknown = report.get('summary',{}).get('all_approvals_status') == 'UNKNOWN_INCOMPLETE'
        still_partial = cover.get('approvals_completeness') != 'complete_all_history_verified'
        rows.append(check('PASS' if unknown and still_partial else 'FAIL','Zero discovered approvals semantics',
                          '0 found != 0 existing; historical discovery is incomplete'))
    else:
        rows.append(check('INFO','Approvals discovered',f'{len(chain["approvals"])} found; not full enumeration'))
    if quality.get('status')!='incomplete' or report.get('summary',{}).get('security_clearance') is not False:
        rows.append(check('FAIL','Fail-closed security labels','Missing explicit INCOMPLETE / no security clearance'))
    else:
        rows.append(check('PASS','Fail-closed security labels','Incomplete dataset is not declared safe'))
    if not cover.get('token_index','').startswith('indexer_pages_complete') and \
       cover.get('moralis_token_index') != 'complete_pages':
        rows.append(check('INCONCLUSIVE','Complete token inventory','Indexer not comprehensive; missing tokens are possible'))
    if baseline:
        old = next((c for c in baseline.get('chains',[]) if c.get('chain')=='bsc'), None)
        if old:
            rows.append(check('INFO','Historical reference',
                              'Previous JSON is an older snapshot, not a live proof',
                              {'old_block':old.get('block'),'new_block':chain.get('block')}))
    return rows


def read_ref_csv(path, required):
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        if not set(required).issubset(reader.fieldnames or []):
            raise ValueError(f'{path} must contain: {", ".join(required)}')
        return list(reader)


def manual_compare(report, token_csv=None, approvals_csv=None):
    rows=[]
    chain = next((c for c in report.get('chains',[]) if c.get('chain')=='bsc'), None)
    if not chain:
        return [check('FAIL','Manual benchmark','BSC result unavailable')]
    if token_csv:
        refs = read_ref_csv(token_csv,['contract','raw_balance','decimals'])
        tokens = {t['contract'].lower():t for t in chain.get('tokens',[]) if ADDRESS.fullmatch(t.get('contract',''))}
        for item in refs:
            contract=item['contract'].strip().lower()
            if not ADDRESS.fullmatch(contract):
                continue
            try: raw=int(item['raw_balance'])
            except ValueError: continue
            token=tokens.get(contract)
            status='PASS' if token and int(token['raw_balance'])==raw else 'FAIL'
            rows.append(check(status,'DeBank manually captured token '+contract,
                              'Match by contract and raw balance' if status=='PASS' else 'Missing/different quantity; reconcile block/time and DeBank dust filters'))
        if not refs: rows.append(check('INCONCLUSIVE','DeBank benchmark','Provided reference CSV is empty'))
    else:
        rows.append(check('INCONCLUSIVE','DeBank external benchmark','No verified DeBank token reference supplied'))
    if approvals_csv:
        refs=read_ref_csv(approvals_csv,['kind','token_contract','spender'])
        found={(str(x.get('kind','')).lower(),str(x.get('token_contract','')).lower(),str(x.get('spender','')).lower())
               for x in chain.get('approvals',[])}
        for item in refs:
            k=(item['kind'].lower().strip(),item['token_contract'].lower().strip(),item['spender'].lower().strip())
            rows.append(check('PASS' if k in found else 'FAIL','Revoke.cash manual approval '+k[1][:12]+'…',
                              'Active approval listed in reference matched' if k in found else 'ACTIVE APPROVAL MISSING in Guardian; must investigate before release'))
        if not refs: rows.append(check('INCONCLUSIVE','Revoke.cash benchmark','Reference CSV is empty; 0 listed does not prove 0 approvals'))
    else:
        rows.append(check('INCONCLUSIVE','Revoke.cash approvals benchmark','No verified Revoke.cash Approvals reference supplied'))
    return rows


def run(args):
    if not ADDRESS.fullmatch(args.address):
        raise ValueError('Invalid wallet address; provide 0x + 40 hexadecimal characters')
    base = args.backend.rstrip('/')
    if base not in ('http://127.0.0.1:8000','http://localhost:8000'):
        raise ValueError('QA accepts only a local backend to avoid accidental data leaks')
    try:
        report = post_json(base+'/api/scan',{'address':args.address,'chains':['bsc']},timeout=180)
    except Exception as e:
        raise RuntimeError('Local FastAPI backend unavailable or scan failed: '+str(e)) from e

    independent=None
    errors=[]
    candidates=[args.rpc] if args.rpc else RPC_CANDIDATES
    for endpoint in candidates:
        try:
            cid=int(rpc(endpoint,'eth_chainId',[]),16)
            if cid !=56: raise ValueError('RPC wrong chain ID: '+str(cid))
            blk=int(rpc(endpoint,'eth_blockNumber',[]),16)
            bal=int(rpc(endpoint,'eth_getBalance',[args.address,'latest']),16)
            independent={'url':endpoint,'chain_id':cid,'block':blk,'native_raw':bal,'token_raw':{},'code':None}
            break
        except Exception as e: errors.append(f'{endpoint}: {type(e).__name__}: {e}')
    if independent:
        try: independent['code'] = rpc(independent['url'],'eth_getCode',[args.address,'latest'])
        except Exception as e: errors.append('eth_getCode: '+str(e))
        for name, contract in [('USDT',USDT),('USDC',USDC)]:
            try:
                encoded = '0x70a08231' + pad_address(args.address)
                independent['token_raw'][contract]=int(rpc(independent['url'],'eth_call',[{'to':contract,'data':encoded},'latest']),16)
            except Exception as e:
                independent['token_raw'][contract] = None
                errors.append(f'{name} eth_call: {str(e)}')
        checks=evaluate(report,independent)
    else:
        checks=[check('PASS' if len(report.get('chains',[]))==1 and report['chains'][0].get('chain')=='bsc' else 'FAIL',
                      'BSC-only scope','Only BSC must be returned'),
                check('INCONCLUSIVE','Independent BSC RPC','All independent endpoints unavailable; cannot verify live balances')]
    baseline=None
    if args.baseline:
        baseline=json.loads(Path(args.baseline).read_text())
        if independent:
            checks=evaluate(report,independent,baseline)
    checks.extend(manual_compare(report,args.debank_csv,args.revoke_csv))
    if independent is None: checks.append(check('INCONCLUSIVE','RPC independent reconciliation','Not performed due to network errors'))
    outcome='FAIL' if any(c['status']=='FAIL' for c in checks) else 'CONDITIONAL' if any(c['status']=='INCONCLUSIVE' for c in checks) else 'PASS_FOR_TESTED_SCOPE'
    document={
        'product':'GUARDIAN 360', 'qa_version':'1.1.2-bsc-qa',
        'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
        'wallet':args.address,'scope':'BSC (chainId=56) ONLY',
        'overall':outcome, 'checks':checks, 'errors':errors,
        'source':{'guardian_local_backend':base,'independent_rpc':independent['url'] if independent else None,
                  'debank_reference':args.debank_csv,'revoke_reference':args.revoke_csv},
        'limitations':['No complete historical approval discovery',
                       'DeBank/Revoke benchmark is INCONCLUSIVE without manually supplied results',
                       'RPC calls may resolve at different blocks',
                       'No malware/spyware detection from wallet address',
                       'No wallet interaction, no signing, no revocation'],
        'report_excerpt':{'requested_chains':report.get('requested_chains'),
                          'native_balance':report.get('chains',[{}])[0].get('native_balance'),
                          'token_count':len(report.get('chains',[{}])[0].get('tokens',[])),
                          'approvals_discovered':len(report.get('chains',[{}])[0].get('approvals',[])),
                          'approval_quality':report.get('chains',[{}])[0].get('quality')}
    }
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(document,ensure_ascii=False,indent=2))
    if args.save_full:
        target.with_name(target.stem+'-raw-scan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('\nGUARDIAN 360 — BSC LIVE QA')
    print('Wallet:',args.address,'| Network: BSC only')
    for row in checks:
        print(f"[{row['status']:12s}] {row['check']}: {row['detail']}")
    print('RESULT:',outcome,'| QA saved:',target)
    return 2 if outcome=='FAIL' else 0


def cli():
    p=argparse.ArgumentParser(description='Read-only live QA for selected BSC scan')
    p.add_argument('--address',required=True,help='Public EVM address; NEVER a seed phrase')
    p.add_argument('--backend',default='http://127.0.0.1:8000')
    p.add_argument('--rpc',default=None,help='Optional independent BSC public RPC HTTPS URL')
    p.add_argument('--baseline',default=None,help='Previous Guardian JSON file (historical only)')
    p.add_argument('--debank-csv',default=None,help='Optional manually verified DeBank token reference CSV')
    p.add_argument('--revoke-csv',default=None,help='Optional manually verified Revoke.cash approvals reference CSV')
    p.add_argument('--output',default='qa/bsc-live-results.json')
    p.add_argument('--save-full',action='store_true',help='Also save full wallet scan JSON locally')
    return p.parse_args()


if __name__=='__main__':
    try:sys.exit(run(cli()))
    except Exception as e:
        print('QA ERROR:',type(e).__name__+': '+str(e),file=sys.stderr)
        sys.exit(3)

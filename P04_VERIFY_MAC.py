#!/usr/bin/env python3
"""One local RC1 live read-only BSC+Ethereum scan; no GitHub or Render writes.

Synthetic QA is run separately by VERIFY_RC1_MAC.sh first. The script scans
using this extracted RC1 source, not the deployed service, so the running
production V2.4.2 remains unchanged. All wallet addresses are public only.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'backend'))
import main
import public_api
from asset_valuation import ETHEREUM_AXS_CONTRACT

ADDR=re.compile(r'^0x[0-9a-fA-F]{40}$')
DEFAULT_WALLET='0x' + '1'*40  # synthetic default; pass --wallet for local live use


def decimal(value):
    try:
        if value is None or isinstance(value,bool):return None
        out=Decimal(str(value))
        return out if out.is_finite() else None
    except (InvalidOperation,ValueError,TypeError):return None


def write_private(folder: Path, value: dict) -> Path:
    folder.mkdir(parents=True,exist_ok=True)
    os.chmod(folder,0o700)
    stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    name=folder / ('P04-'+stamp+'.json')
    # mode 0600; never upload automatically.
    fd=os.open(name,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,default=str)
    return name


def reconcile(report: dict, wallet: str) -> dict:
    result={'status':'HOLD','scope':'ethereum+bsc / sampled live scan, not full wallet valuation',
            'limits':['Price and block timestamps differ between chains.',
                      'Token discovery and approval history are bounded.',
                      'No result certifies wallet safety.']}
    if not isinstance(report,dict) or str(report.get('address','')).lower()!=wallet.lower():
        result['reason']='Invalid/mismatched API response'
        return result
    chains=report.get('chains')
    if not isinstance(chains,list) or {c.get('chain') for c in chains if isinstance(c,dict)}!={'ethereum','bsc'} or len(chains)!=2:
        result['reason']='Expected exactly Ethereum and BSC'
        return result
    by={c['chain']:c for c in chains}
    summary=report.get('summary',{})
    axi=[t for t in by['ethereum'].get('tokens',[]) if str(t.get('contract','')).lower()==ETHEREUM_AXS_CONTRACT]
    holdings={'contract':ETHEREUM_AXS_CONTRACT,'detected':len(axi)==1,
              'matches':len(axi)}
    if len(axi)==1:
        t=axi[0]
        for key in ['raw_balance','balance','usd_price','usd_value','decimals','block',
                    'price_source','price_timestamp','balance_verification',
                    'contract_recognized','trusted_usd_eligible','price_status']:
            holdings[key]=t.get(key)
    result['ethereum_axs']=holdings
    result['by_chain']={}
    observed=Decimal(0)
    n=0
    for chain,c in by.items():
        live=c.get('priced_usd_partial')
        expected=(summary.get('priced_usd_by_chain') or {}).get(chain,{}).get('usd_priced_partial')
        result['by_chain'][chain]={'block':c.get('block'),'rpc_status':c.get('native_status'),
                                   'priced_usd_partial':live,'summary_agrees':live==expected,
                                   'asset_coverage':c.get('coverage',{}).get('asset_valuation')}
        v=decimal(live)
        if v is not None:
            observed+=v
            n+=1
    total=decimal(summary.get('usd_known_sum'))
    result['server_total_partial']=str(total) if total is not None else None
    result['reconciled_total_partial']=str(observed) if n else None
    result['partial_sum_matches']=(total==observed) if n else total is None
    result['incomplete_coverage_advertised']=(summary.get('audit_quality')=='INCOMPLETE' and
        summary.get('security_clearance') is False and
        summary.get('all_approvals_status')=='UNKNOWN_INCOMPLETE')
    ok=all([
        len(axi)==1,
        holdings.get('balance_verification')=='verified',
        holdings.get('contract_recognized') is True,
        holdings.get('trusted_usd_eligible') is True,
        decimal(holdings.get('balance')) is not None,
        decimal(holdings.get('usd_value')) is not None,
        result['partial_sum_matches'],
        result['incomplete_coverage_advertised'],
        all(x.get('summary_agrees') for x in result['by_chain'].values()),
    ])
    if ok:
        result['status']='TECHNICAL_RC1_LIVE_VALIDATION_PASS / NO_DEPLOYMENT'
        result['reason']='Live local RC1 scanned Ethereum AXS and reconciled selected-chain USD values. Production release still requires UI/rollback review.'
    else:
        result['reason']='Local RC1 evidence incomplete; inspect token and chain coverage, do not publish.'
    return result


async def run_live(wallet: str):
    # Disable analytics DB creation in this read-only verification session.
    main.record_aggregate_scan=lambda:None
    request=main.ScanRequest(address=wallet,chains=['bsc','ethereum'])
    return await asyncio.wait_for(main.scan(request),timeout=185)


def main_cli():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wallet',default=DEFAULT_WALLET,help='Public EVM wallet address')
    args=parser.parse_args()
    wallet=args.wallet.strip()
    if not ADDR.fullmatch(wallet):parser.error('Invalid public wallet address')
    routes={x.path for x in public_api.app.routes}
    if routes!={'/api/health','/api/chains','/api/scan'}:
        raise SystemExit('FAIL: unexpected public API route; scan aborted')
    h=public_api.public_health()
    if h['wallet_signing'] or h['revoke_endpoints']:
        raise SystemExit('FAIL: public revoke/signing must remain off')
    evidence={'gate':'P0.4','mode':'READ_ONLY_LOCAL_SOURCE','wallet':wallet,
              'checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
              'backend_version':h['version'],'public_routes':sorted(routes),
              'assert_wallet_ownership':False, 'github_push':False,'cloud_deployment':False,'transaction':False,
              'axs_contract':ETHEREUM_AXS_CONTRACT,
              'source_sha256':hashlib.sha256((ROOT/'backend/asset_valuation.py').read_bytes()).hexdigest()}
    print('=== GUARDIAN 360 / P0.4 LIVE RC1 VALIDATION ===')
    print('Scanning with extracted RC1 code, read-only:',wallet)
    try:
        report=asyncio.run(run_live(wallet))
        evidence['result']=reconcile(report,wallet)
        # Evidence contains public data only, but keep the full report private.
        evidence['scan_report']=report
    except Exception as exc:
        evidence['result']={'status':'HOLD','error':type(exc).__name__+': '+str(exc)[:250]}
    result=evidence['result']
    print('Result:',result['status'])
    if result.get('ethereum_axs'):
        print('Ethereum AXS:',result['ethereum_axs'].get('balance'),'AXS')
        print('Ethereum AXS priced USD:',result['ethereum_axs'].get('usd_value'))
    print('BSC/Ethereum partial USD:',{k:v['priced_usd_partial'] for k,v in result.get('by_chain',{}).items()})
    print('Cross-network precise sum agrees:',result.get('partial_sum_matches'))
    print('No safety clearance:',result.get('incomplete_coverage_advertised'))
    path=write_private(Path.home()/'Myproject'/'GUARDIAN360'/'.local'/'p04-evidence',evidence)
    print('Private evidence:',path)
    print('NO PUSH. NO DEPLOY. NO SIGNING.')
    if result['status'].startswith('HOLD'):
        print('RC1: HOLD; reason:',result.get('reason') or result.get('error'))
        sys.exit(2)
    print('LOCAL RC1 LIVE VALIDATION: PASS; PRODUCTION RELEASE NOT AUTHORIZED')

if __name__=='__main__':main_cli()

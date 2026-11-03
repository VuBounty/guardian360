#!/usr/bin/env python3
"""Offline QA of a GUARDIAN 360 JSON report; no external access.

Usage:
    python3 benchmark/audit_report.py /path/to/guardian360-report.json
The report is read locally and not stored or transmitted by this script.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from forensic import classify_token, classify_delegation, summarize_forensic, evaluate_coverage, exact_balance


def audit(data):
    report = []
    chains = []
    for src in data.get('chains', []):
        c = dict(src)
        c['quality'] = evaluate_coverage(c)
        c['delegation'] = classify_delegation(c.get('delegation') or {}, c.get('chain', ''))
        tokens = []
        for t in c.get('tokens', []):
            t = dict(t)
            try:
                if t.get('raw_balance') is not None:
                    t['balance'] = exact_balance(int(t['raw_balance']), int(t['decimals']))
            except (ValueError, TypeError):
                pass
            tokens.append(classify_token(t, c.get('chain', '')))
        c['tokens'] = tokens
        chains.append(c)
        tag = c.get('chain', '?').upper()
        if c['native_status'] != 'verified': report.append(f'{tag} native coin balance: NOT VERIFIED')
        issues = [t for t in tokens if t['classification'] == 'review']
        if issues:
            report.append(f'{tag} tokens requiring review: {len(issues)}')
            for t in issues[:5]: report.append(f'  {t["symbol"]} [{t["contract"][:10]}...] — {"; ".join(t["review_reasons"])}')
        d = c['delegation']
        if d.get('status') == 'eip7702_delegated':
            report.append(f'{tag} EIP-7702 delegate: {d.get("identity_status")}; not proof of compromise')
        report.append(f'{tag} live approvals FOUND: {len(c.get("approvals", []))} (TOTAL UNKNOWN, HISTORIC COVERAGE INCOMPLETE)')
        report.append(f'{tag} indexer: {str(c.get("coverage", {}).get("token_index", "unknown"))[:85]}')
    summary = summarize_forensic(chains)
    report.append('Recognized partial USD sum: ' + str(summary['recognized_usd_partial']))
    report.append('Unverified quoted USD excluded: ' + str(summary['excluded_unverified_usd_quotes']))
    report.append('Verdict: INCOMPLETE — not a wallet safety certificate')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Offline forensic QA of Guardian 360 JSON reports.')
    parser.add_argument('report_file', type=Path, help='Path to locally saved Guardian JSON report')
    args = parser.parse_args()
    with args.report_file.open(encoding='utf-8') as f:
        payload = json.load(f)
    for line in audit(payload): print(line)

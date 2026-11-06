"""Deterministic multichain asset inventory presentation and provenance.

A source union is only as comprehensive as the upstream indexers. Never infer
an empty chain from an unavailable provider, a limited page budget or RPC only.
No RPC, wallet connection, transaction signing or outbound network IO here.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from collections import defaultdict
import re

ADDRESS = re.compile(r'^0x[0-9a-fA-F]{40}$')


def union_token_candidates(*provider_lists: list[dict]) -> tuple[list[dict], dict]:
    """Deduplicate by contract on one chain, retain provider-specific evidence.

    The RPC verifier in asset_valuation is the sole authority for live balances;
    conflicting indexer balances do not justify an unverified valuation.
    """
    merged: dict[str, dict] = {}
    invalid = 0
    for rows in provider_lists:
        for item in rows:
            if not isinstance(item, dict):
                invalid += 1
                continue
            contract = str(item.get('contract') or '')
            if not ADDRESS.fullmatch(contract):
                invalid += 1
                continue
            key = contract.lower()
            source = str(item.get('source') or 'unknown-indexer')[:80]
            raw = str(item.get('raw_balance') or '')
            if not raw.isdigit() or int(raw) == 0:
                invalid += 1
                continue
            if key not in merged:
                merged[key] = {**item, 'contract': key,
                               'discovered_by': [source],
                               'source_balances': {source: raw},
                               'provider_balance_conflict': False}
            else:
                current = merged[key]
                if source not in current['discovered_by']:
                    current['discovered_by'].append(source)
                if any(prev != raw for prev in current['source_balances'].values()):
                    current['provider_balance_conflict'] = True
                current['source_balances'][source] = raw
                current['possible_spam'] = bool(current.get('possible_spam') or item.get('possible_spam'))
                if str(item.get('reputation') or '').lower() in {'spam', 'scam', 'malicious'}:
                    current['reputation'] = item['reputation']
                # Prefer present metadata to absent metadata, not USD quote claims.
                for field in ('symbol', 'name', 'decimals', 'balance'):
                    if current.get(field) in (None, '', 'UNKNOWN', 'Token') and item.get(field) not in (None, ''):
                        current[field] = item[field]
    return list(merged.values()), {
        'unique_contracts': len(merged),
        'rejected_or_zero_observations': invalid,
        'provider_balance_conflicts': sum(bool(x['provider_balance_conflict']) for x in merged.values()),
    }


def inventory_status(sources: list[dict]) -> str:
    """Completeness of contacted source pagination, NOT the entire chain."""
    if not sources or all(x.get('state') in ('unavailable', 'not_configured') for x in sources):
        return 'SOURCE_UNAVAILABLE'
    if any(x.get('state') != 'exhausted' for x in sources):
        return 'PARTIAL_SOURCE_COVERAGE'
    return 'SOURCE_PAGES_EXHAUSTED_NOT_GLOBAL'


def asset_register(chains: list[dict]) -> dict:
    """Compile real scan-chain output into a first-class, chain-scoped ledger.

    Zero native balances are legitimate but do not increase positive-holdings
    count. NFT inventory is explicitly unverified. No implicit price of zero.
    """
    assets: list[dict] = []
    per_chain = []
    for c in chains:
        chain_id = int(c.get('chain_id') or {'bsc':56,'ethereum':1,'base':8453,'arbitrum':42161}[c['chain']])
        key = c['chain']
        start = len(assets)
        if c.get('native_status') == 'verified':
            balance = str(c.get('native_balance') or '0')
            try:
                positive = Decimal(balance) > 0
            except InvalidOperation:
                positive = False
            if positive:
                assets.append({'id': f'{chain_id}:NATIVE', 'chain_id': chain_id,
                               'chain': key, 'standard': 'NATIVE', 'symbol': c['symbol'],
                               'balance': balance, 'verification': 'VERIFIED',
                               'category': 'native', 'value_usd': c.get('native_usd'),
                               'source': 'rpc', 'contract': None})
        for t in c.get('tokens') or []:
            contract = str(t.get('contract') or '').lower()
            if not ADDRESS.fullmatch(contract):
                continue
            assets.append({'id': f'{chain_id}:ERC20:{contract}', 'chain_id': chain_id,
                           'chain': key, 'standard': 'ERC20', 'symbol': str(t.get('symbol') or 'UNKNOWN'),
                           'name': str(t.get('name') or ''), 'contract': contract,
                           'balance_raw': t.get('raw_balance'), 'balance': t.get('balance'),
                           'verification': 'VERIFIED' if t.get('balance_verification') == 'verified' else 'NOT_VERIFIED',
                           'category': t.get('asset_category') or 'unverified_identity',
                           'value_usd': t.get('usd_value') if t.get('trusted_usd_eligible') else None,
                           'source': t.get('discovered_by') or [t.get('source')],
                           'provider_balance_conflict': bool(t.get('provider_balance_conflict')),
                           'reasons': t.get('review_reasons') or []})
        for nft in c.get('nft_assets') or []:
            contract = str(nft.get('contract') or '').lower()
            token_id = str(nft.get('token_id') or '')
            standard = str(nft.get('standard') or '').replace('-', '').upper()
            if not ADDRESS.fullmatch(contract) or not token_id.isdigit() or standard not in ('ERC721', 'ERC1155'):
                continue
            assets.append({'id': f'{chain_id}:{standard}:{contract}:{int(token_id)}',
                           'chain_id': chain_id, 'chain': key, 'standard': standard,
                           'symbol': str(nft.get('symbol') or 'NFT'), 'name': str(nft.get('name') or ''),
                           'contract': contract, 'token_id': token_id, 'balance': nft.get('balance'),
                           'verification': 'INDEXER_ONLY', 'category': 'nft_unverified',
                           'value_usd': None, 'source': [nft.get('source') or 'unknown']})
        coverage = c.get('coverage') or {}
        sources = coverage.get('inventory_sources') or []
        per_chain.append({'chain_id': chain_id, 'chain': key, 'discovered_assets': len(assets)-start,
                          'source_status': inventory_status(sources),
                          'sources': sources, 'snapshot_block': c.get('block')})
    return {'schema': 'guardian360.asset-register.v2.6.rc',
            'discovered_assets': len(assets), 'assets': assets, 'chains': per_chain,
            'global_completeness': 'NOT_ESTABLISHED', 'revoke_enabled': False}

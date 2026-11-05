"""GUARDIAN 360 V2.5: fail-closed EVM asset balance & USD valuation.

Public read-only methods only. Token discovery is BOUNDED, not a full catalog.
Addresses in the curated catalog are identified contracts, not safety ratings.
A price is only trusted if balance, decimals and contract-addressed quote are
independently verified, with a bounded quote age.
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from decimal import Decimal, localcontext
from typing import Any, Callable

from forensic import exact_balance

ADDRESS = re.compile(r'^0x[0-9a-fA-F]{40}$')
MAX_QUOTE_AGE_SECONDS = 1800
MIN_PRICE_CONFIDENCE = Decimal('0.80')
# An empty token index is not proof that the wallet has no other tokens.
MAX_INDEXED_CANDIDATES = 16

# Curated public contract identities. Listing here does NOT certify token safety.
ETHEREUM_AXS_CONTRACT = '0xbb0e17ef65f82ab018d8edd776e8dd940327b28b'
ETHEREUM_CATALOG = (
    ('USDT', '0xdAC17F958D2ee523a2206206994597C13D831ec7', 6),
    ('USDC', '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', 6),
    ('AXS', ETHEREUM_AXS_CONTRACT, 18),
)

BSC_CATALOG = (
    ('USDT', '0x55d398326f99059fF775485246999027B3197955', 18),
    ('USDC', '0x8ac76a51cc950d9822D68b83fE1Ad97B32CD580d', 18),
    ('WBNB', '0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c', 18),
    ('AXS', '0x715d400f88c167884bbcc41c5fea407ed4d2f8a0', 18),
    ('TWT', '0x4B0F1812e5Df2A09796481Ff14017e6005508003', 18),
    ('CAKE', '0x0e09FaBB73Bd3Ade0a17ECC321fD13a19e81cE82', 18),
)


def safe_price(raw: Any) -> Decimal | None:
    try:
        n = Decimal(str(raw))
        return n if n.is_finite() and n > 0 and n <= Decimal('1e9') else None
    except (ValueError, TypeError, ArithmeticError):
        return None


def validate_quote(entry: dict | None, now: int | None = None) -> dict | None:
    """Accept prices only for current, confidence-qualified contract quotes."""
    if not isinstance(entry, dict):
        return None
    n = safe_price(entry.get('price'))
    if n is None:
        return None
    now = int(time.time()) if now is None else now
    try:
        ts = int(entry['timestamp'])
        if not (0 <= now - ts <= MAX_QUOTE_AGE_SECONDS):
            return None
        conf = entry.get('confidence')
        if conf is not None and Decimal(str(conf)) < MIN_PRICE_CONFIDENCE:
            return None
    except (ValueError, TypeError, ArithmeticError, KeyError):
        return None
    return {'price': n, 'timestamp': ts, 'confidence': entry.get('confidence'),
            'source': entry.get('_source', 'defillama_by_chain_and_contract')}


def quote_key(chain: str, contract: str) -> str:
    return f'{chain}:{contract.lower()}'


async def contract_quotes(client, chain: str, contracts: list[str]) -> tuple[dict[str, dict], str]:
    """DefiLlama by-contract quotes. No symbol-only price substitution."""
    if not contracts:
        return {}, 'no_positive_verified_tokens'
    # HTTP query length and output are bounded; only caller-vetted addresses pass.
    unique = sorted({c.lower() for c in contracts if isinstance(c, str) and ADDRESS.fullmatch(c)})[:40]
    if not unique:
        return {}, 'no_contracts'
    keys = [quote_key(chain, c) for c in unique]
    url = 'https://coins.llama.fi/prices/current/' + ','.join(keys)
    try:
        response = await client.get(url, timeout=12)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or not isinstance(body.get('coins'), dict):
            raise ValueError('unexpected price response')
        # Preserve exactly-addressed entries. Never fall back to ticker symbols.
        quotes = {str(k).lower(): v for k, v in body['coins'].items() if isinstance(v, dict)}
        return quotes, 'contract_quotes_received'
    except Exception as exc:
        return {}, 'price_service_unavailable:' + type(exc).__name__


async def coingecko_token_quotes(client, chain: str, contracts: list[str]) -> dict[str, dict]:
    """Secondary by-contract source if DefiLlama is unavailable/stale.

    Uses only exact chain+contract identities. Key is optional and server-side;
    unauthenticated/demo rate limits may cause no quote, which fails closed.
    """
    networks = {'bsc': 'binance-smart-chain', 'ethereum': 'ethereum',
                'base': 'base', 'arbitrum': 'arbitrum-one'}
    network = networks.get(chain)
    vetted = sorted({c.lower() for c in contracts if ADDRESS.fullmatch(c)})[:30]
    if not network or not vetted:
        return {}
    headers = {}
    key = os.getenv('COINGECKO_DEMO_API_KEY')
    if key:
        headers['x-cg-demo-api-key'] = key
    try:
        response = await client.get(
            'https://api.coingecko.com/api/v3/simple/token_price/' + network,
            params={'contract_addresses': ','.join(vetted), 'vs_currencies':'usd',
                    'include_last_updated_at':'true'},
            headers=headers, timeout=12)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            return {}
        result = {}
        for contract in vetted:
            row = data.get(contract) or data.get(contract.lower())
            if not isinstance(row, dict) or 'last_updated_at' not in row:
                continue
            # Validate staleness with same rule as primary provider.
            candidate = {'price':row.get('usd'),'timestamp':row['last_updated_at'],
                         '_source':'coingecko_by_chain_and_contract'}
            if validate_quote(candidate) is not None:
                result[quote_key(chain,contract)]=candidate
        return result
    except Exception:
        return {}


NATIVE_COINS = {
    'bsc': 'coingecko:binancecoin',
    'ethereum': 'coingecko:ethereum',
    'base': 'coingecko:ethereum',
    'arbitrum': 'coingecko:ethereum',
}

async def native_usd_quote(client, chain: str) -> tuple[dict | None, str]:
    """Fresh native coin quote; legacy indexer stats are NOT trusted by default."""
    key = NATIVE_COINS.get(chain)
    if not key:
        return None, 'native_chain_not_supported'
    try:
        response = await client.get('https://coins.llama.fi/prices/current/' + key, timeout=12)
        response.raise_for_status()
        body = response.json()
        data = body.get('coins') if isinstance(body, dict) else None
        entries = {str(k).lower(): v for k, v in data.items()} if isinstance(data, dict) else {}
        quote = validate_quote(entries.get(key))
        return (quote, 'fresh_provider_quote') if quote else (None, 'native_price_missing_or_stale')
    except Exception as exc:
        return None, 'native_price_provider_unavailable:' + type(exc).__name__


async def reconcile_assets(client, rpc_call: Callable, rpc_url: str,
                           wallet: str, chain: str, block: int,
                           indexed_tokens: list[dict], known_tokens: list[tuple],
                           explorer: str) -> tuple[list[dict], dict]:
    """Revalidate every eligible token candidate with eth_call at a fixed block.

    rpc_call has signature (client, url, method, params). A failed request is
    UNVERIFIED, never interpreted as zero. Quotes are not copied from indexers.
    """
    curated = {addr.lower(): (symbol, addr, decimals) for symbol, addr, decimals in known_tokens}
    by_contract: dict[str, dict] = {}
    for item in indexed_tokens:
        c = str(item.get('contract') or '').lower()
        if ADDRESS.fullmatch(c) and c not in by_contract:
            by_contract[c] = dict(item)
    # Curated candidates are ALWAYS probed even when the indexer missed them.
    seen = set(curated)
    secondary = [x for x in sorted(by_contract) if x not in seen]
    selected = list(curated) + secondary[:MAX_INDEXED_CANDIDATES]
    stats = {'candidate_count': len(curated) + len(secondary),
             'known_contract_candidates': len(curated),
             'indexer_candidates_rechecked': min(len(secondary), MAX_INDEXED_CANDIDATES),
             'candidates_not_checked': max(0, len(secondary) - MAX_INDEXED_CANDIDATES),
             'balance_verification_failures': 0, 'decimals_verification_failures': 0,
             'verified_positive_balances': 0, 'priced_verified_contracts': 0,
             'price_service': 'not_checked', 'scope': 'bounded_curated_plus_indexer'}
    semaphore = asyncio.Semaphore(6)

    async def probe(c: str):
        base = by_contract.get(c, {})
        identified = curated.get(c)
        symbol = identified[0] if identified else str(base.get('symbol') or 'UNKNOWN')[:24]
        contract = identified[1] if identified else c
        decimals_expected = identified[2] if identified else None
        item = {**base, 'symbol': symbol, 'contract': contract,
                'name': (base.get('name') or symbol)[:70],
                'usd_price': None, 'usd_value': None,
                'price_source': None, 'price_timestamp': None,
                'balance_verification': 'not_checked',
                'source': 'rpc-contract-probe' if c not in by_contract else 'indexer-candidate+rpc-recheck',
                'explorer_url': explorer + '/token/' + contract}
        async with semaphore:
            try:
                raw_hex = await rpc_call(client, rpc_url, 'eth_call', [
                    {'to': contract, 'data': '0x70a08231' + wallet[2:].lower().zfill(64)}, hex(block)])
                if not isinstance(raw_hex, str) or not raw_hex.startswith('0x'):
                    raise ValueError('bad balance response')
                raw = int(raw_hex, 16)
                if raw < 0 or raw >= (1 << 256):
                    raise ValueError('invalid uint256 balance')
            except Exception as exc:
                item['balance_verification'] = 'rpc_failed:' + type(exc).__name__
                # Display indexer-reported candidate as UNVERIFIED with no trusted price.
                if base:
                    item['raw_balance'] = base.get('raw_balance')
                    item['balance'] = base.get('balance')
                    item['balance_source'] = 'indexer_unverified'
                return item if base else None, 'balance_error'
            # Current onchain zero supersedes any stale indexer-reported balance.
            if raw == 0:
                return None, 'zero_verified'
            try:
                # Always read decimals() from the same contract and block as balance.
                dec_hex = await rpc_call(client, rpc_url, 'eth_call', [
                    {'to': contract, 'data': '0x313ce567'}, hex(block)])
                if not isinstance(dec_hex, str) or not dec_hex.startswith('0x'):
                    raise ValueError('bad decimals response')
                dec = int(dec_hex, 16)
                if not 0 <= dec <= 36:
                    raise ValueError('unreasonable decimals')
            except Exception:
                item['balance_verification'] = 'balance_verified_decimals_unavailable'
                item['raw_balance'] = str(raw)
                item['balance'] = None
                item['balance_source'] = 'onchain_at_block'
                item['block'] = block
                return item, 'decimals_error'
            item.update(raw_balance=str(raw), decimals=dec, balance=exact_balance(raw, dec),
                        balance_source='onchain_at_block', block=block,
                        balance_verification='verified',
                        expected_decimals_match=(decimals_expected is None or dec == decimals_expected))
            if decimals_expected is not None and dec != decimals_expected:
                item['balance_verification'] = 'decimals_mismatch'
                return item, 'decimals_error'
            return item, 'verified'

    examined = await asyncio.gather(*(probe(c) for c in selected))
    result = [row for row, _ in examined if row]
    stats['balance_verification_failures'] = sum(status == 'balance_error' for _, status in examined)
    stats['decimals_verification_failures'] = sum(status == 'decimals_error' for _, status in examined)
    stats['verified_positive_balances'] = sum(status == 'verified' for _, status in examined)
    pricable = [t['contract'] for t in result if t['balance_verification'] == 'verified']
    quotes, price_state = await contract_quotes(client, chain, pricable)
    stats['price_service'] = price_state
    missing = [t['contract'] for t in result
               if t['balance_verification'] == 'verified'
               and validate_quote(quotes.get(quote_key(chain, t['contract']))) is None]
    if missing:
        secondary = await coingecko_token_quotes(client, chain, missing)
        for address, q in secondary.items():
            quotes[address] = q
        if secondary:
            stats['price_service'] += '+coingecko_fallback'
    for t in result:
        if t['balance_verification'] != 'verified':
            continue
        accepted = validate_quote(quotes.get(quote_key(chain, t['contract'])))
        if accepted is None:
            t['price_status'] = 'unavailable_or_stale'
            continue
        t['usd_price'] = format(accepted['price'], 'f')
        t['price_source'] = accepted['source']
        t['price_timestamp'] = accepted['timestamp']
        t['price_status'] = 'current_contract_quote'
        with localcontext() as ctx:
            ctx.prec = 115
            t['usd_value'] = format(Decimal(t['balance']) * accepted['price'], 'f')
        stats['priced_verified_contracts'] += 1
    return result, stats

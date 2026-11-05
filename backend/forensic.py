"""Conservative, read-only evidence classification for GUARDIAN 360.

Never equate absence of indexed data with absence of risk. All identities below
refer to published contract *addresses*, not verified code hashes or approvals.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, localcontext
from typing import Any

METAMASK_EIP7702 = '0x63c0c19a282a1b52b07dd5a65b58948a07dae32b'
METAMASK_REFERENCE = 'https://support.metamask.io/configure/accounts/what-is-a-smart-account'
METAMASK_DEPLOYMENTS = 'https://ethereum.org/roadmap/pectra/7702/'

# Minimal explicitly-maintained allowlist; do not infer that other tokens are scams.
RECOGNIZED_TOKENS = {
    'ethereum': {
        '0xdac17f958d2ee523a2206206994597c13d831ec7': 'USDT',
        '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48': 'USDC',
        '0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2': 'WETH',
        '0xbb0e17ef65f82ab018d8edd776e8dd940327b28b': 'AXS',
    },
    'bsc': {
        '0x55d398326f99059ff775485246999027b3197955': 'USDT',
        '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d': 'USDC',
        '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c': 'WBNB',
        '0x715d400f88c167884bbcc41c5fea407ed4d2f8a0': 'AXS',
        '0x4b0f1812e5df2a09796481ff14017e6005508003': 'TWT',
        '0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82': 'CAKE',
    },
    'base': {
        '0x833589fc d6edb6e08f4c7c32d4f71b54bda02913'.replace(' ', ''): 'USDC',
        '0x4200000000000000000000000000000000000006': 'WETH',
    },
    'arbitrum': {
        '0xaf88d065e77c8cc2239327c5edb3a432268e5831': 'USDC',
        '0x82af49447d8a07e3bd95bd0d56f35241523fbab1': 'WETH',
    },
}
NATIVE_SYMBOLS = {'bsc': 'BNB', 'ethereum': 'ETH', 'base': 'ETH', 'arbitrum': 'ETH'}
PROTECTED_SYMBOLS = {'ETH', 'BNB', 'USDT', 'USDC', 'WETH', 'WBNB', 'AXS', 'TWT', 'CAKE'}
# This threshold is deliberately heuristic: it flags an absurd token quantity for
# investigation but is not proof of malicious behavior.
REVIEW_BALANCE_THRESHOLD = Decimal('1e18')


def to_decimal(value: Any) -> Decimal | None:
    try:
        if value is None or value == '':
            return None
        n = Decimal(str(value))
        return n if n.is_finite() else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def exact_balance(raw: int, decimals: int) -> str:
    if not isinstance(raw, int) or raw < 0 or not isinstance(decimals, int) or not 0 <= decimals <= 36:
        raise ValueError('invalid balance inputs')
    # A uint256 can have up to 78 decimal digits; Decimal's default context of
    # 28 digits causes silent rounding for giant spam balances.
    with localcontext() as context:
        context.prec = max(110, len(str(raw)) + 5)
        return format(Decimal(raw) / (Decimal(10) ** decimals), 'f')


def concise_quantity(value: Any) -> str:
    """Human-oriented display, never substitute it for raw evidence."""
    n = to_decimal(value)
    if n is None:
        return '—'
    if n == 0:
        return '0'
    if abs(n) >= Decimal('1e12') or abs(n) < Decimal('0.000001'):
        return f'{n:.3E}'
    text = format(n, 'f')
    if '.' in text:
        whole, fractional = text.split('.', 1)
        return whole + ('.' + fractional[:8].rstrip('0') if fractional[:8].rstrip('0') else '')
    return text


def classify_token(token: dict, chain: str) -> dict:
    """Preserve all balances, but prohibit suspicious unverified token value summing."""
    t = dict(token)
    symbol = str(t.get('symbol', '')).strip().upper()
    contract = str(t.get('contract', '')).lower()
    recognized_symbol = RECOGNIZED_TOKENS.get(chain, {}).get(contract)
    reasons: list[str] = []
    if t.get('possible_spam') is True:
        reasons.append('Indexer marks token as possible spam')
    reputation = str(t.get('reputation') or '').lower()
    if reputation in ('scam', 'spam', 'malicious'):
        reasons.append('Indexer reputation flag: ' + reputation)
    if symbol == NATIVE_SYMBOLS.get(chain) and not recognized_symbol:
        reasons.append('ERC-20 symbol impersonates the network native asset; it is NOT native coin')
    elif symbol in PROTECTED_SYMBOLS and not recognized_symbol:
        reasons.append('Ticker resembles a widely used asset; token contract is not in the small recognized allowlist')
    balance = to_decimal(t.get('balance'))
    if balance is not None and balance >= REVIEW_BALANCE_THRESHOLD:
        reasons.append('Extremely large token quantity; may be spam/airdrop dust; not a USD value')
    if recognized_symbol is not None and symbol != recognized_symbol:
        reasons.append('Returned token symbol differs from recognized contract metadata')
    verification = t.get('balance_verification')
    if verification is not None and verification != 'verified':
        reasons.append('Live token balance or decimals not fully verified: ' + str(verification)[:70])
    t['review_reasons'] = reasons
    t['classification'] = 'review' if reasons else ('recognized_contract' if recognized_symbol else 'unverified')
    t['contract_recognized'] = recognized_symbol is not None
    t['trusted_usd_eligible'] = bool(recognized_symbol is not None and not reasons and (t.get('balance_verification') in (None, 'verified')) and (t.get('price_source') is None or t.get('price_source') in ('defillama_by_chain_and_contract', 'coingecko_by_chain_and_contract')) and to_decimal(t.get('usd_value')) is not None and to_decimal(t.get('usd_value')) >= 0)
    t['display_balance'] = concise_quantity(t.get('balance'))
    t['source_type'] = 'token_contract'  # never merge with native coin balance
    return t


def classify_delegation(value: dict, chain: str) -> dict:
    d = dict(value)
    if d.get('status') != 'eip7702_delegated':
        return d
    delegate = str(d.get('delegate') or '').lower()
    if delegate == METAMASK_EIP7702:
        d.update(identity='MetaMask EIP-7702 Stateless Delegator (publicly documented address)',
                 identity_status='known_documented_address',
                 review_priority='informational',
                 trust_note='Address matches a published MetaMask delegation deployment. Does not independently verify bytecode, permissions, or wallet safety.',
                 references=[METAMASK_REFERENCE, METAMASK_DEPLOYMENTS])
    else:
        d.update(identity='Unidentified EIP-7702 delegate', identity_status='unknown',
                 review_priority='review', trust_note='Not in bundled allowlist; check explorer and wallet before acting.', references=[])
    return d


def evaluate_coverage(chain_report: dict) -> dict:
    """An explicit fail-closed quality signal; NOT a verdict about wallet safety."""
    cover = chain_report.get('coverage') or {}
    native = chain_report.get('native_status') == 'verified'
    idx = str(cover.get('token_index') or '')
    mor = str(cover.get('moralis_token_index') or '')
    tx = str(cover.get('transactions') or '')
    tok_discovery = idx == 'indexer_pages_complete' or mor == 'complete_pages'
    tx_discovery = tx == 'recent_history_complete'
    approvals = str(cover.get('approvals_completeness'))
    failed_probes = cover.get('allowance_probe_errors') or {}
    events = cover.get('approval_event_logs') or {}
    permit = cover.get('permit2_internal') or {}
    errors = []
    if not native:
        errors.append('RPC native-balance unavailable')
    if not tok_discovery:
        errors.append('ERC-20 token catalog not fully indexed')
    if not tx_discovery:
        errors.append('Recent wallet transaction history unavailable or truncated')
    if events.get('status') != 'bounded':
        errors.append('ERC-20 event discovery missing or incomplete')
    if permit.get('status') != 'bounded':
        errors.append('Permit2 event inspection missing or incomplete')
    if failed_probes.get('count', 0):
        errors.append(f"{failed_probes['count']} live allowance RPC probes failed")
    if cover.get('allowance_candidates_unchecked_due_to_cap', 0):
        errors.append('Some discovered permission candidates exceeded the scan cap')
    # Historical approval completeness is never achievable from a bounded scan.
    errors.append('Full historical allowance discovery not established')
    return {
        'status': 'incomplete',
        'native_balance_verified': native,
        'token_index_complete_pages': tok_discovery,
        'recent_transactions_index_complete_pages': tx_discovery,
        'approval_discovery_complete': False,
        'approval_status': 'unknown' if approvals != 'complete_all_history_verified' else 'bounded_candidates_only',
        'unresolved': errors,
        'meaning': '0 approvals discovered is NOT evidence that 0 approvals exist',
    }


def summarize_forensic(chains: list[dict]) -> dict:
    """Partial prices for SCANNED networks only, using Decimal with no float math.

    Distinct chain keys prevent the same network being silently counted twice.
    A missing/failed price stays None; it never becomes an artificial $0.
    Token identity is (chain, contract), not symbol.
    """
    recognized_usd = Decimal(0)
    unverified_usd = Decimal(0)
    recognized_entries = 0
    flagged = 0
    missing_native_price = 0
    by_chain: dict[str, dict] = {}
    for index, chain in enumerate(chains):
        key = str(chain.get('chain') or f'unspecified_{index}')
        if key in by_chain:
            raise ValueError('Duplicate chain in partial-valuation summary')
        subtotal = Decimal(0)
        count = 0
        unpriced = 0
        native = to_decimal(chain.get('native_usd'))
        # A verified zero native balance adds no priced holding. In particular,
        # it must not disguise an unpriced positive ERC-20 as a $0 wallet.
        native_balance = to_decimal(chain.get('native_balance'))
        if native is not None and native >= 0 and (native > 0 or (native_balance is not None and native_balance > 0)):
            subtotal += native
            count += 1
        elif native_balance not in (None, Decimal(0)):
            missing_native_price += 1
            unpriced += 1
        seen_contracts: set[str] = set()
        for token in chain.get('tokens', []):
            contract = str(token.get('contract') or '').lower()
            if contract and contract in seen_contracts:
                # Duplicate indexer entries are never double-counted.
                continue
            if contract:
                seen_contracts.add(contract)
            val = to_decimal(token.get('usd_value'))
            if token.get('classification') == 'review':
                flagged += 1
            if val is None or val < 0:
                if to_decimal(token.get('balance')) not in (None, Decimal(0)):
                    unpriced += 1
                continue
            if token.get('trusted_usd_eligible'):
                subtotal += val
                count += 1
            else:
                unverified_usd += val
                unpriced += 1
        by_chain[key] = {
            'usd_priced_partial': format(subtotal, 'f') if count else None,
            'priced_entries': count,
            'unpriced_or_excluded_assets': unpriced,
            'scope': 'selected_chain_only; may omit undiscovered assets',
        }
        if count:
            recognized_usd += subtotal
            recognized_entries += count
    return {
        'recognized_usd_partial': format(recognized_usd, 'f') if recognized_entries else None,
        'priced_usd_by_chain': by_chain,
        'excluded_unverified_usd_quotes': format(unverified_usd, 'f'),
        'token_review_count': flagged,
        'missing_native_usd_chains': missing_native_price,
        'usd_completeness': 'partial_or_unknown',
        'all_approvals_status': 'UNKNOWN_INCOMPLETE',
    }

"""Guardian 360 V2.4 — backend read-only transaction-intent verifier.

This module NEVER has a private key and NEVER sends blockchain transactions.
The wallet extension performs all signing, after explicit user approval.
Every supported calldata is derived from fixed audited ABI selectors, not
supplied by the browser. The client must independently verify it again.
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Awaitable

ADDRESS = re.compile(r'^0x[0-9a-fA-F]{40}$')
TX_HASH = re.compile(r'^0x[0-9a-fA-F]{64}$')
ZERO = '0x' + '0' * 40
PERMIT2 = '0x000000000022D473030F116dDEE9F6B43aC78BA3'
SUPPORTED_KINDS = {'erc20', 'nft_operator', 'nft_token', 'permit2'}


class UnsafeIntent(ValueError):
    pass


def check_address(value: str, field: str) -> str:
    if not isinstance(value, str) or not ADDRESS.fullmatch(value):
        raise UnsafeIntent(f'{field} must be a valid EVM address')
    if value.lower() == ZERO:
        raise UnsafeIntent(f'{field} cannot be zero address')
    return value


def word_address(value: str) -> str:
    return check_address(value, 'ABI address')[2:].lower().zfill(64)


def word_uint(value: int) -> str:
    if type(value) is not int or not 0 <= value < 2**256:
        raise UnsafeIntent('Invalid unsigned ABI integer')
    return format(value, '064x')


def word_bool(value: bool) -> str:
    if type(value) is not bool:
        raise UnsafeIntent('Invalid boolean')
    return word_uint(int(value))


def encode_call(selector: str, *words: str) -> str:
    return selector + ''.join(words)


def decode_words(hex_value: Any, n: int) -> tuple[int, ...]:
    if not isinstance(hex_value, str) or not hex_value.startswith('0x') or len(hex_value) < 2 + 64 * n:
        raise UnsafeIntent('Invalid RPC response to approval check')
    try:
        return tuple(int(hex_value[2 + i * 64:2 + (i + 1) * 64], 16) for i in range(n))
    except ValueError:
        raise UnsafeIntent('Invalid ABI response') from None


def decode_address(hex_value: Any) -> str:
    word = decode_words(hex_value, 1)[0]
    if word >= (1 << 160):
        raise UnsafeIntent('Invalid address returned from RPC')
    return '0x' + format(word, '040x')


def normalize_request(address: str, chain: str, kind: str, token: str, spender: str, token_id: int | None, chains: dict) -> dict:
    if chain not in chains:
        raise UnsafeIntent('Unsupported chain')
    if kind not in SUPPORTED_KINDS:
        raise UnsafeIntent('Unsupported revoke kind')
    owner = check_address(address, 'owner')
    token = check_address(token, 'contract')
    spender = check_address(spender, 'spender')
    if kind == 'permit2' and token.lower() == PERMIT2.lower():
        raise UnsafeIntent('Permit2 token is not the Permit2 contract itself')
    if kind == 'nft_token':
        if not isinstance(token_id, (str, int)) or type(token_id) is bool or not str(token_id).isdigit() or not 0 <= int(token_id) < 2**256:
            raise UnsafeIntent('ERC-721 token ID required')
    elif token_id is not None:
        raise UnsafeIntent('Token ID only allowed for ERC-721 single token')
    return {'address': owner, 'chain': chain, 'kind': kind, 'token_contract': token, 'spender': spender, 'token_id': str(token_id) if token_id is not None else None}


async def verify_request(req: dict, rpc_call: Callable[[str, list], Awaitable[Any]], chain_id: int) -> dict:
    """Use authoritative chain RPC only. Raises UnsafeIntent on RPC failure/mismatch.

    rpc_call(method, params) is injected to allow independent deterministic tests.
    """
    owner, token, spender, kind = [req[k] for k in ('address', 'token_contract', 'spender', 'kind')]
    remote_chain = await rpc_call('eth_chainId', [])
    if int(remote_chain, 16) != chain_id:
        raise UnsafeIntent('RPC chain ID mismatch: refusing verification')
    to_check = token if kind != 'permit2' else PERMIT2
    code = await rpc_call('eth_getCode', [to_check, 'latest'])
    if not isinstance(code, str) or code.lower() in ('0x', '0x0', '0x00'):
        raise UnsafeIntent('Target is not a deployed contract')

    active_value: str
    preflight_method: str
    calldata: str
    if kind == 'erc20':
        preflight_method = 'allowance(address,address)'
        query = encode_call('0xdd62ed3e', word_address(owner), word_address(spender))
        amount = decode_words(await rpc_call('eth_call', [{'to': token, 'data': query}, 'latest']), 1)[0]
        if amount == 0:
            raise UnsafeIntent('ERC-20 allowance already zero; no revoke needed')
        active_value = str(amount)
        calldata = encode_call('0x095ea7b3', word_address(spender), word_uint(0))
    elif kind == 'nft_operator':
        preflight_method = 'isApprovedForAll(address,address)'
        query = encode_call('0xe985e9c5', word_address(owner), word_address(spender))
        approved = decode_words(await rpc_call('eth_call', [{'to': token, 'data': query}, 'latest']), 1)[0]
        if approved != 1:
            raise UnsafeIntent('NFT operator permission is not currently active')
        active_value = 'true'
        calldata = encode_call('0xa22cb465', word_address(spender), word_bool(False))
    elif kind == 'nft_token':
        token_id = req['token_id']
        preflight_method = 'getApproved(uint256) / ownerOf(uint256)'
        query = encode_call('0x081812fc', word_uint(int(token_id)))
        approved = decode_address(await rpc_call('eth_call', [{'to': token, 'data': query}, 'latest']))
        owner_query = encode_call('0x6352211e', word_uint(int(token_id)))
        owner_at_chain = decode_address(await rpc_call('eth_call', [{'to': token, 'data': owner_query}, 'latest']))
        if owner_at_chain.lower() != owner.lower():
            raise UnsafeIntent('Wallet does not own this NFT at latest block')
        if approved.lower() != spender.lower():
            raise UnsafeIntent('Spender is not the current approved address for this NFT')
        active_value = approved
        calldata = encode_call('0x095ea7b3', ZERO[2:].zfill(64), word_uint(int(token_id)))
    else:
        preflight_method = 'Permit2.allowance(owner,token,spender)'
        query = encode_call('0x927da105', word_address(owner), word_address(token), word_address(spender))
        amount, expires, _ = decode_words(await rpc_call('eth_call', [{'to': PERMIT2, 'data': query}, 'latest']), 3)
        if amount == 0 or expires <= int(time.time()):
            raise UnsafeIntent('Permit2 allowance is zero or expired')
        active_value = str(amount)
        # Permit2.approve(token,spender,uint160 amount,uint48 expiration) with zero amount and expiry
        calldata = encode_call('0x87517c45', word_address(token), word_address(spender), word_uint(0), word_uint(0))

    return {
        'verified': True,
        'status': 'LIVE_ACTIVE',
        'from': owner,
        'chain': req['chain'],
        'chain_id': chain_id,
        'kind': kind,
        'token_contract': token,
        'spender': spender,
        'token_id': req['token_id'],
        'current_permission': active_value,
        'read_method': preflight_method,
        'to': to_check,
        'data': calldata,
        'verified_at': int(time.time()),
        'expires_at': int(time.time()) + 120,
        'simulation_level': 'eth_call + eth_estimateGas (wallet side); not full security simulation',
        'warning': 'Current approval was verified onchain but spender trust is not established. Only user-controlled wallet can authorize a transaction.'
    }


async def check_cleared(req: dict, rpc_call: Callable[[str, list], Awaitable[Any]]) -> bool:
    owner, token, spender, kind = [req[k] for k in ('address', 'token_contract', 'spender', 'kind')]
    if kind == 'erc20':
        query = encode_call('0xdd62ed3e', word_address(owner), word_address(spender))
        return decode_words(await rpc_call('eth_call', [{'to': token, 'data': query}, 'latest']), 1)[0] == 0
    if kind == 'nft_operator':
        query = encode_call('0xe985e9c5', word_address(owner), word_address(spender))
        return decode_words(await rpc_call('eth_call', [{'to': token, 'data': query}, 'latest']), 1)[0] == 0
    if kind == 'nft_token':
        query = encode_call('0x081812fc', word_uint(int(req['token_id'])))
        return decode_address(await rpc_call('eth_call', [{'to': token, 'data': query}, 'latest'])).lower() == ZERO.lower()
    query = encode_call('0x927da105', word_address(owner), word_address(token), word_address(spender))
    amount, exp, _ = decode_words(await rpc_call('eth_call', [{'to': PERMIT2, 'data': query}, 'latest']), 3)
    return amount == 0 or exp <= int(time.time())


def expected_transaction(req: dict) -> tuple[str, str]:
    kind = req['kind']
    spender = req['spender']
    if kind == 'erc20':
        return req['token_contract'], encode_call('0x095ea7b3', word_address(spender), word_uint(0))
    if kind == 'nft_operator':
        return req['token_contract'], encode_call('0xa22cb465', word_address(spender), word_bool(False))
    if kind == 'nft_token':
        return req['token_contract'], encode_call('0x095ea7b3', ZERO[2:].zfill(64), word_uint(int(req['token_id'])))
    if kind == 'permit2':
        return PERMIT2, encode_call('0x87517c45', word_address(req['token_contract']), word_address(spender), word_uint(0), word_uint(0))
    raise UnsafeIntent('Unsupported intent kind')


async def inspect_receipt(req: dict, tx_hash: str, rpc_call: Callable[[str, list], Awaitable[Any]], chain_id: int) -> dict:
    if not TX_HASH.fullmatch(tx_hash):
        raise UnsafeIntent('Invalid transaction hash')
    if int(await rpc_call('eth_chainId', []), 16) != chain_id:
        raise UnsafeIntent('Wrong chain')
    receipt = await rpc_call('eth_getTransactionReceipt', [tx_hash])
    if receipt is None:
        return {'status': 'PENDING', 'cleared': False, 'tx_hash': tx_hash}
    tx = await rpc_call('eth_getTransactionByHash', [tx_hash])
    if not isinstance(tx, dict):
        raise UnsafeIntent('Cannot establish transaction origin')
    if str(tx.get('from', '')).lower() != req['address'].lower():
        raise UnsafeIntent('Transaction sender mismatch')
    expected_to, expected_data = expected_transaction(req)
    if str(tx.get('to', '')).lower() != expected_to.lower() or str(tx.get('input', '')).lower() != expected_data.lower():
        raise UnsafeIntent('Transaction does not match the exact revoke intent')
    if receipt.get('status') != '0x1':
        return {'status': 'REVERTED', 'cleared': False, 'tx_hash': tx_hash}
    try:
        cleared = await check_cleared(req, rpc_call)
    except Exception as exc:
        return {'status': 'MINED_UNVERIFIED', 'cleared': False, 'tx_hash': tx_hash, 'message': type(exc).__name__}
    return {'status': 'VERIFIED_REVOKED' if cleared else 'MINED_PERMISSION_STILL_ACTIVE', 'cleared': cleared, 'tx_hash': tx_hash}

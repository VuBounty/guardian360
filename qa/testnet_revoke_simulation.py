#!/usr/bin/env python3
"""GUARDIAN 360 V2.6: TESTNET-ONLY READ-ONLY REVOKE SIMULATOR.

No signing, wallet connection, broadcast, nonce manipulation, or secret inputs.
Designed for offline deterministic tests and optional TESTNET eth_call/eth_estimateGas.
Not a security audit and not authorization to enable a public Revoke button.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

ADDR = re.compile(r'^0x[a-fA-F0-9]{40}$')
TESTNETS = {'sepolia': 11155111, 'bsc-testnet': 97, 'base-sepolia': 84532}
PERMIT2 = '0x000000000022D473030F116dDEE9F6B43aC78BA3'
KINDS = ('erc20', 'erc721_operator', 'erc1155_operator', 'erc721_token', 'permit2_allowance')


def check_address(value: str, name: str) -> str:
    if not isinstance(value, str) or not ADDR.fullmatch(value) or int(value[2:], 16) == 0:
        raise ValueError(f'{name} must be a nonzero EVM address')
    return value.lower()


def word(value: str) -> str:
    return value[2:].lower().zfill(64)


def uint_word(value: int | str) -> str:
    raw = str(value)
    if not re.fullmatch(r'\d{1,78}', raw):
        raise ValueError('Token ID must be a nonnegative integer')
    n = int(raw)
    if n >= 2**256:
        raise ValueError('Token ID exceeds uint256')
    return format(n, '064x')


def plan(chain: str, kind: str, owner: str, token: str, spender: str, token_id: str | None = None) -> dict:
    if chain not in TESTNETS:
        raise ValueError('HARD STOP: TESTNET ONLY. Mainnet is not supported.')
    if kind not in KINDS:
        raise ValueError('Unsupported revoke type; EIP-7702 is not an approval')
    owner, token, spender = (check_address(v, k) for v, k in
                             [(owner, 'owner'), (token, 'token'), (spender, 'spender')])
    if kind == 'erc20':
        dest, data = token, '0x095ea7b3' + word(spender) + uint_word(0)
    elif kind in ('erc721_operator', 'erc1155_operator'):
        dest, data = token, '0xa22cb465' + word(spender) + uint_word(0)
    elif kind == 'erc721_token':
        if token_id is None:
            raise ValueError('ERC-721 single token needs token_id')
        dest, data = token, '0x095ea7b3' + uint_word(0) + uint_word(token_id)
    else:
        # Offline construction only. Do not call on an unverified Permit2 deployment.
        dest, data = PERMIT2.lower(), '0x87517c45' + word(token) + word(spender) + uint_word(0) + uint_word(0)
    return {
        'network': chain, 'chain_id': TESTNETS[chain], 'kind': kind, 'owner': owner,
        'token_contract': token, 'spender': spender, 'token_id': token_id,
        'tx': {'from': owner, 'to': dest, 'data': data, 'value': '0x0'},
        'status': 'OFFLINE_PLAN_ONLY', 'broadcast': False, 'wallet_signing': False,
        'permit2_requires_independent_deployment_verification': kind == 'permit2_allowance',
        'note': 'Candidate only. Must read live permission, simulate on testnet, and independently review before enabling any signing.',
    }


def rpc_request(url: str, method: str, params: list) -> object:
    if method not in ('eth_chainId', 'eth_blockNumber', 'eth_getCode', 'eth_call', 'eth_estimateGas'):
        raise ValueError('Only read-only RPC methods permitted')
    parts = urlsplit(url)
    if parts.scheme != 'https' and not (parts.scheme == 'http' and parts.hostname in ('localhost', '127.0.0.1')):
        raise ValueError('RPC must be HTTPS, or localhost for local testnet')
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': params}).encode()
    req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json', 'User-Agent': 'Guardian360-testnet-revoke-readonly/2.6'})
    with urllib.request.urlopen(req, timeout=20) as response:
        result = json.load(response)
    if 'error' in result:
        raise RuntimeError('Read-only RPC returned an error: ' + str(result['error'])[:220])
    if 'result' not in result:
        raise ValueError('Missing RPC result')
    return result['result']


def _read_word(result: object) -> int:
    if not isinstance(result, str) or not re.fullmatch(r'0x[0-9a-fA-F]{64,}', result):
        raise ValueError('Malformed eth_call result')
    return int(result[2:66], 16)


def simulate_live(p: dict, rpc_url: str, request=rpc_request) -> dict:
    """Checks a TESTNET's current permission and models transaction with no broadcast."""
    if p['chain_id'] not in TESTNETS.values() or p['status'] != 'OFFLINE_PLAN_ONLY' or p['tx']['value'] != '0x0':
        raise ValueError('Untrusted or non-testnet plan')
    if p['kind'] == 'permit2_allowance':
        raise ValueError('HOLD: Permit2 deployment identity has not been independently verified on this testnet')
    actual = request(rpc_url, 'eth_chainId', [])
    if int(actual, 16) != p['chain_id']:
        raise ValueError('HARD STOP: RPC chain ID mismatch')
    code = request(rpc_url, 'eth_getCode', [p['tx']['to'], 'latest'])
    if not isinstance(code, str) or code in ('0x', '0x0', '0x00'):
        raise ValueError('HARD STOP: contract code not found on testnet')
    owner, spender, token = p['owner'], p['spender'], p['token_contract']
    def read(data: str) -> int:
        value = request(rpc_url, 'eth_call', [{'to': token, 'from': owner, 'data': data}, 'latest'])
        return _read_word(value)
    if p['kind'] == 'erc20':
        active = read('0xdd62ed3e' + word(owner) + word(spender)) > 0
    elif p['kind'] in ('erc721_operator', 'erc1155_operator'):
        active = read('0xe985e9c5' + word(owner) + word(spender)) == 1
    else:
        tid = uint_word(p['token_id'])
        owner_now = read('0x6352211e' + tid)
        approved = read('0x081812fc' + tid)
        active = (owner_now == int(owner, 16) and approved == int(spender, 16))
    if not active:
        raise ValueError('No currently active matching permission; no revoke needed')
    # eth_call and eth_estimateGas are simulations, not transactions; they do not
    # guarantee real transaction success in a future block.
    request(rpc_url, 'eth_call', [p['tx'], 'latest'])
    gas = request(rpc_url, 'eth_estimateGas', [p['tx']])
    gas_int = int(gas, 16)
    if not 0 < gas_int <= 2_000_000:
        raise ValueError('Estimated gas exceeded review cap')
    return {'status': 'TESTNET_SIMULATED_NOT_SENT', 'network': p['network'],
            'chain_id': p['chain_id'], 'kind': p['kind'], 'estimated_gas': gas_int,
            'target': p['tx']['to'], 'selector': p['tx']['data'][:10],
            'broadcast': False, 'wallet_signing': False, 'onchain_revoked': False,
            'note': 'Preflight only. No transaction sent. Independent audit required before enabling public action.'}


def main() -> None:
    parser = argparse.ArgumentParser(description='GUARDIAN360: TESTNET-ONLY read-only revoke plan & simulation')
    parser.add_argument('--chain', choices=TESTNETS, required=True)
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--owner', required=True)
    parser.add_argument('--token', required=True)
    parser.add_argument('--spender', required=True)
    parser.add_argument('--token-id')
    parser.add_argument('--rpc', help='Optional TESTNET HTTPS RPC. Only eth_call/eth_estimateGas etc. No signing or broadcasting.')
    args = parser.parse_args()
    p = plan(args.chain, args.kind, args.owner, args.token, args.spender, args.token_id)
    print(json.dumps(p, indent=2))
    if args.rpc:
        print(json.dumps(simulate_live(p, args.rpc), indent=2))


if __name__ == '__main__':
    main()

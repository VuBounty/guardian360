"""GUARDIAN 360 V1.1 — read-only, evidence-first, bounded EVM wallet scanner.

No private keys, signing, wallet connection, or revoke transactions.  Incomplete
indexing is exposed as partial coverage, never confused with a clean security bill.
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException
from revoke_engine import normalize_request, verify_request, inspect_receipt, UnsafeIntent
from analytics import router as analytics_router, record_aggregate_scan
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from forensic import classify_token, classify_delegation, evaluate_coverage, summarize_forensic, exact_balance
from asset_valuation import BSC_CATALOG, ETHEREUM_CATALOG, reconcile_assets, native_usd_quote
from inventory_sources import union_token_candidates, asset_register, inventory_status

ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
APPROVAL_TOPIC = "0x8c5be1e5ebec7d5bd14f71427d1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"
NFT_OPERATOR_TOPIC = "0x17307eab39ab6107e8899845ad3d59bd9653f200f220920489ca2b5937696c31"
PERMIT2 = "0x000000000022D473030F116dDEE9F6B43aC78BA3"
MAX_UINT256 = 2**256 - 1
MAX_UINT160 = 2**160 - 1
# Only well-known contract identities as a fallback. These are NOT a token discovery API.
KNOWN_TOKENS = {
    "ethereum": list(ETHEREUM_CATALOG),
    "bsc": list(BSC_CATALOG),
    "base": [("USDC", "0x833589fCD6EDB6E08f4c7C32D4f71b54bdA02913", 6)],
    "arbitrum": [("USDC", "0xaf88d065e77c8cC2239327C5EDb3A432268e5831", 6)],
}
CHAINS = {
    "bsc": dict(name="BNB Smart Chain", id=56, symbol="BNB", rpc="https://bsc-dataseed.bnbchain.org", explorer="https://bscscan.com", indexer="https://blockscout.routescan.io/56/api/v2"),
    "ethereum": dict(name="Ethereum", id=1, symbol="ETH", rpc="https://ethereum-rpc.publicnode.com", explorer="https://etherscan.io", indexer="https://eth.blockscout.com/api/v2"),
    "base": dict(name="Base", id=8453, symbol="ETH", rpc="https://base-rpc.publicnode.com", explorer="https://basescan.org", indexer="https://base.blockscout.com/api/v2"),
    "arbitrum": dict(name="Arbitrum One", id=42161, symbol="ETH", rpc="https://arbitrum-one-rpc.publicnode.com", explorer="https://arbiscan.io", indexer="https://arbitrum.blockscout.com/api/v2"),
}
MAX_TOKEN_PAGES = max(1, min(20, int(os.getenv("MAX_TOKEN_PAGES", "8"))))
MAX_TX_PAGES = max(1, min(5, int(os.getenv("MAX_TX_PAGES", "2"))))
LOG_LOOKBACK = max(0, min(10000, int(os.getenv("APPROVAL_LOG_LOOKBACK_BLOCKS", "2500"))))
MAX_LOG_TOKEN_CONTRACTS = 12

app = FastAPI(title="Guardian 360 Wallet Security API", version="2.6.0-rc-hold")
app.include_router(analytics_router)
SCAN_SLOTS = asyncio.Semaphore(3)  # simple overload guard, not a public rate limiter
origins = [v.strip() for v in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173").split(",") if v.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Guardian-Admin"])


class ScanRequest(BaseModel):
    address: str = Field(min_length=42, max_length=42)
    # None keeps backwards compatibility with V1.1.1 clients.
    # Explicit empty/unknown lists are rejected: never silently scan all chains.
    chains: list[str] | None = Field(default=None, min_length=1, max_length=4)



def short_error(exc: Exception) -> str:
    return (type(exc).__name__ + ": " + str(exc))[:180]


def encode_address(address: str) -> str:
    if not ADDRESS.fullmatch(address):
        raise ValueError("Invalid address")
    return address[2:].lower().zfill(64)


def as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            return None
        return result
    except (ValueError, InvalidOperation, TypeError):
        return None


def numeric_string(raw: int, decimals: int) -> str:
    if decimals < 0 or decimals > 36:
        raise ValueError("Unsupported token decimals")
    return exact_balance(raw, decimals)


def val_to_int(raw: Any) -> int:
    if isinstance(raw, str) and raw.startswith("0x"):
        return int(raw, 16)
    return int(raw)


def hash_of(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("hash") or item.get("address_hash") or ""
    return ""


async def rpc(client: httpx.AsyncClient, url: str, method: str, params: list) -> Any:
    response = await client.post(url, json={"jsonrpc": "2.0", "id": 7, "method": method, "params": params}, timeout=7 if method == "eth_getLogs" else 13)
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise RuntimeError(str(data["error"])[:150])
    if "result" not in data:
        raise RuntimeError("RPC result missing")
    return data["result"]


async def eth_call(client: httpx.AsyncClient, url: str, contract: str, data: str) -> int:
    value = await rpc(client, url, "eth_call", [{"to": contract, "data": data}, "latest"])
    if not isinstance(value, str) or not value.startswith("0x") or len(value) < 3:
        raise RuntimeError("Invalid eth_call response")
    return int(value, 16)


async def indexer_get(client: httpx.AsyncClient, base: str, path: str, params: dict | None = None) -> Any:
    url = base.rstrip("/") + path
    query = dict(params or {})
    # Security boundary: Routescan paid credentials must never be forwarded to
    # arbitrary INDEXER_* overrides, or stored in query strings/access logs.
    parsed = urlsplit(base)
    headers: dict[str, str] = {}
    if parsed.scheme == "https" and parsed.hostname == "blockscout.routescan.io":
        key = os.getenv("BLOCKSCOUT_API_KEY")
        if not key:
            raise RuntimeError("Routescan Blockscout indexer requires a paid API key")
        headers["x-api-key"] = key
    response = await client.get(url, params=query, headers=headers, timeout=12)
    response.raise_for_status()
    return response.json()


async def indexer_pages(client: httpx.AsyncClient, base: str, path: str, limit: int, params: dict | None = None) -> tuple[list[dict], bool]:
    """Bounded cursor walk: preserve fetched pages if a later page fails.

    False means more pages may exist or a page failed; no implication that the
    network's asset catalog is exhaustive. Cycle detection prevents bad cursors.
    """
    items: list[dict] = []
    query = dict(params or {})
    seen_cursors: set[str] = set()
    for _ in range(limit):
        try:
            payload = await indexer_get(client, base, path, query)
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise ValueError("Indexer response format changed")
            items.extend(x for x in payload["items"] if isinstance(x, dict))
            nxt = payload.get("next_page_params")
            if not nxt:
                return items, True
            if not isinstance(nxt, dict):
                raise ValueError("Unsupported indexer pagination format")
            marker = repr(sorted(nxt.items()))
            if marker in seen_cursors:
                return items, False
            seen_cursors.add(marker)
            query = {**(params or {}), **nxt}
        except Exception:
            if not items:
                raise
            return items, False
    return items, False


def parse_token(item: dict, chain: str, explorer: str) -> dict | None:
    meta = item.get("token") or {}
    if not isinstance(meta, dict) or meta.get("type") not in ("ERC-20", "BEP-20", None):
        return None
    contract = hash_of(meta.get("address_hash") or meta.get("address") or "")
    if not isinstance(meta, dict) or not ADDRESS.fullmatch(contract):
        return None
    try:
        raw = val_to_int(item.get("value", 0))
        decimals = int(meta["decimals"]) if meta.get("decimals") not in (None, "") else None
        if raw <= 0:
            return None
        if decimals is not None and not 0 <= decimals <= 36:
            decimals = None
        with localcontext() as ctx:
            ctx.prec = 115
            balance = Decimal(exact_balance(raw, decimals)) if decimals is not None else None
            price = as_decimal(meta.get("exchange_rate"))
            usd = (balance * price) if balance is not None and price is not None and price >= 0 else None
        return {"reputation": meta.get("reputation"), "symbol": str(meta.get("symbol") or "UNKNOWN")[:24], "name": str(meta.get("name") or "Token")[:70], "contract": contract, "raw_balance": str(raw), "decimals": decimals, "balance": format(balance, "f") if balance is not None else None, "usd_price": format(price, "f") if price is not None else None, "usd_value": format(usd, "f") if usd is not None else None, "source": "blockscout-indexer", "explorer_url": explorer + "/token/" + contract}
    except (ValueError, InvalidOperation, TypeError):
        return None


async def moralis_token_index(client: httpx.AsyncClient, wallet: str, key: str, explorer: str) -> tuple[list[dict], bool]:
    """Optional authenticated wallet token indexer, with key kept server-side.

    Uses Moralis `wallets/{address}/tokens` (balances with optional pricing).
    A 2-page cap remains a partial scan if more pages exist.
    """
    api_key = os.getenv("MORALIS_API_KEY")
    if not api_key:
        raise RuntimeError("MORALIS_API_KEY not configured")
    query: dict = {"chain": hex(CHAINS[key]["id"]), "limit": 100}
    out: list[dict] = []
    complete = False
    seen_cursors = set()
    for _ in range(MAX_TOKEN_PAGES):
        try:
            response = await client.get("https://deep-index.moralis.io/api/v2.2/wallets/" + wallet + "/tokens", params=query, headers={"X-API-Key": api_key}, timeout=14)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("result"), list):
                raise ValueError("Moralis token index format changed")
        except Exception:
            if out:
                return out, False  # Partial rows are kept, never lost on later-page failure.
            raise
        for item in payload["result"]:
            contract = item.get("token_address", "")
            if not ADDRESS.fullmatch(contract):
                continue
            try:
                raw = val_to_int(item.get("balance", 0))
                dec = int(item["decimals"]) if item.get("decimals") not in (None, "") else None
                if raw <= 0:
                    continue
                if dec is not None and not 0 <= dec <= 36:
                    dec = None
                with localcontext() as ctx:
                    ctx.prec = 115
                    balance = Decimal(exact_balance(raw, dec)) if dec is not None else None
                    price = as_decimal(item.get("usd_price"))
                    usd = as_decimal(item.get("usd_value"))
                    if usd is None and balance is not None and price is not None:
                        usd = balance * price
                out.append({"symbol": str(item.get("symbol") or "UNKNOWN")[:24], "name": str(item.get("name") or "Token")[:70], "contract": contract, "raw_balance": str(raw), "decimals": dec, "balance": format(balance, "f") if balance is not None else None, "usd_price": format(price, "f") if price is not None else None, "usd_value": format(usd, "f") if usd is not None else None, "possible_spam": bool(item.get("possible_spam", False)), "source": "moralis-indexer", "explorer_url": explorer + "/token/" + contract})
            except (ValueError, TypeError, InvalidOperation):
                continue
        cursor = payload.get("cursor")
        if not cursor:
            complete = True
            break
        if cursor in seen_cursors:
            break
        seen_cursors.add(cursor)
        query["cursor"] = cursor
    return out, complete


def candidate_from_tx(tx: dict, owner: str) -> dict | None:
    if hash_of(tx.get("from")).lower() != owner.lower():
        return None
    status = str(tx.get("status", "")).lower()
    if status in ("error", "failed", "0"):
        return None
    destination = hash_of(tx.get("to"))
    raw = tx.get("raw_input") or tx.get("input") or ""
    if not ADDRESS.fullmatch(destination) or not isinstance(raw, str) or len(raw) < 138:
        return None
    selector = raw[:10].lower()
    if selector not in ("0x095ea7b3", "0x39509351", "0xa457c2d7", "0xa22cb465"):
        return None
    try:
        spender = "0x" + raw[10:74][-40:]
        if not ADDRESS.fullmatch(spender):
            return None
        return {"kind": "operator" if selector == "0xa22cb465" else "erc20", "contract": destination, "spender": spender, "tx_hash": tx.get("hash"), "discovery": "recent_wallet_transaction"}
    except (ValueError, TypeError):
        return None


def decode_log_candidate(log: dict, owner: str, expected_topic: str, kind: str) -> dict | None:
    topics = log.get("topics") or []
    if len(topics) < 3 or str(topics[0]).lower() != expected_topic.lower():
        return None
    if str(topics[1])[-40:].lower() != owner[2:].lower():
        return None
    contract = hash_of(log.get("address") or "")
    spender = "0x" + str(topics[2])[-40:]
    if not ADDRESS.fullmatch(contract) or not ADDRESS.fullmatch(spender):
        return None
    return {"kind": kind, "contract": contract, "spender": spender, "tx_hash": log.get("transactionHash"), "discovery": "bounded_rpc_event_logs"}


async def fetch_rpc_logs(client: httpx.AsyncClient, url: str, block: int, contracts: list[str], owner: str, kind: str) -> tuple[list[dict], dict]:
    sig = APPROVAL_TOPIC if kind == "erc20" else NFT_OPERATOR_TOPIC
    if LOG_LOOKBACK == 0 or not contracts:
        return [], {"status": "not_checked", "message": "Log indexing disabled or no contracts available"}
    start = max(0, block - LOG_LOOKBACK)
    results = []
    errors = []
    # Split into bounded ranges. A provider may reject large log queries even here.
    async def one_window(left: int):
        end = min(left + 499, block)
        try:
            logs = await rpc(client, url, "eth_getLogs", [{"fromBlock": hex(left), "toBlock": hex(end), "address": contracts, "topics": [sig, "0x" + encode_address(owner)]}])
            if not isinstance(logs, list):
                raise ValueError("Unexpected eth_getLogs payload")
            found = [c for log in logs[:300] if (c := decode_log_candidate(log, owner, sig, kind))]
            return found, ["RPC event result capped at 300 in one window"] if len(logs) > 300 else []
        except Exception as exc:
            return [], [short_error(exc)]
    # At most five parallel event windows with V1.1's configurable 2500-block default.
    windows = await asyncio.gather(*(one_window(left) for left in range(start, block + 1, 500)))
    for found, problems in windows:
        results.extend(found)
        errors.extend(problems)
    return results, {"status": "partial" if errors else "bounded", "from_block": start, "to_block": block, "contracts": len(contracts), "events": len(results), "message": "; ".join(errors[:2]) if errors else "Only the reported block window and token contracts were searched"}


def dt_seconds(timestamp: Any) -> float | None:
    if isinstance(timestamp, (int, float)):
        return float(timestamp)
    if isinstance(timestamp, str):
        try:
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def find_sweeper_pattern(transactions: list[dict], address: str, explorer: str) -> dict:
    """Heuristic ONLY: 2+ fast receive→send cycles to same recipient; not malware proof."""
    ins = []
    outs = []
    for tx in transactions:
        if str(tx.get("status", "")).lower() in ("error", "failed", "0"):
            continue
        try:
            value = val_to_int(tx.get("value", "0"))
        except (ValueError, TypeError):
            continue
        stamp = dt_seconds(tx.get("timestamp"))
        if value <= 0 or stamp is None:
            continue
        src, dst = hash_of(tx.get("from")).lower(), hash_of(tx.get("to")).lower()
        record = {"timestamp": stamp, "value": value, "to": dst, "hash": tx.get("hash", "")}
        if dst == address.lower() and src != address.lower():
            ins.append(record)
        if src == address.lower() and dst != address.lower():
            outs.append(record)
    incidents = []
    used = set()
    for i, inc in enumerate(sorted(ins, key=lambda x: x["timestamp"])):
        matching = [out for out in outs if out["hash"] not in used and 0 <= out["timestamp"] - inc["timestamp"] <= 120 and out["value"] >= inc["value"] * 0.7]
        if matching:
            out = min(matching, key=lambda x: x["timestamp"])
            used.add(out["hash"])
            incidents.append({"destination": out["to"], "seconds": int(out["timestamp"] - inc["timestamp"]), "incoming_tx": inc["hash"], "outgoing_tx": out["hash"], "incoming_link": explorer + "/tx/" + inc["hash"], "outgoing_link": explorer + "/tx/" + out["hash"]})
    destinations = {}
    for inc in incidents:
        destinations[inc["destination"]] = destinations.get(inc["destination"], 0) + 1
    repeat = [inc for inc in incidents if destinations[inc["destination"]] >= 2]
    return {"status": "pattern_detected" if repeat else "no_pattern_in_sample", "incidents": repeat[:4], "recent_transactions_examined": len(transactions), "method": "repeated incoming native transfer followed within 120s by >=70% outgoing to same recipient; can also be legitimate automation", "is_proof_of_compromise": False}


async def balance_fallback(client: httpx.AsyncClient, url: str, wallet: str, key: str, existing: set[str], explorer: str) -> tuple[list[dict], list[str]]:
    async def one(symbol: str, contract: str, decimals: int):
        if contract.lower() in existing:
            return None, None
        try:
            value = await eth_call(client, url, contract, "0x70a08231" + encode_address(wallet))
            if value <= 0:
                return None, None
            return {"symbol": symbol, "name": symbol + " (known-contract fallback)", "contract": contract, "raw_balance": str(value), "decimals": decimals, "balance": numeric_string(value, decimals), "usd_price": None, "usd_value": None, "source": "rpc-known-contract-only", "explorer_url": explorer + "/token/" + contract}, None
        except Exception as exc:
            return None, short_error(exc)
    results = await asyncio.gather(*(one(*row) for row in KNOWN_TOKENS[key]))
    return [r for r, _ in results if r], [err for _, err in results if err]


async def check_candidate(client: httpx.AsyncClient, rpc_url: str, wallet: str, candidate: dict, tokens_by_contract: dict, explorer: str, probe_errors: list[dict] | None = None) -> dict | None:
    token, spender, kind = candidate["contract"], candidate["spender"], candidate["kind"]
    evidence = {"tx_hash": candidate.get("tx_hash"), "discovery": candidate["discovery"], "explorer_url": explorer + "/address/" + token}
    try:
        if kind == "operator":
            value = await eth_call(client, rpc_url, token, "0xe985e9c5" + encode_address(wallet) + encode_address(spender))
            if value != 1:
                return None
            return {"kind": "nft_operator", "token_contract": token, "spender": spender, "active": True, "risk": "attention", "reason": "Current isApprovedForAll=true. Operator can transfer NFTs covered by this collection; not evidence of malicious intent.", "exposed_balance": None, "evidence": evidence}
        value = await eth_call(client, rpc_url, token, "0xdd62ed3e" + encode_address(wallet) + encode_address(spender))
        if value <= 0:
            return None
        meta = tokens_by_contract.get(token.lower(), {})
        dec = meta.get("decimals")
        amount = numeric_string(value, dec) if isinstance(dec, int) else None
        balance_raw = int(meta.get("raw_balance", 0)) if meta else None
        exposure_raw = min(balance_raw, value) if balance_raw is not None else None
        exposure = numeric_string(exposure_raw, dec) if exposure_raw is not None and isinstance(dec, int) else None
        unlimited = value >= 2**255
        return {"kind": "erc20_allowance", "token_contract": token, "token_symbol": meta.get("symbol", "Unknown token"), "spender": spender, "raw_allowance": str(value), "allowance": amount, "unlimited": unlimited, "active": True, "risk": "attention" if unlimited else "review", "reason": "Unlimited token allowance; review spender" if unlimited else "Non-zero live allowance; not by itself malicious", "exposed_balance": exposure, "balance_known": bool(meta), "evidence": evidence}
    except Exception as exc:
        # A failed eth_call is UNVERIFIED, never a verified zero allowance.
        # ERC-721 single-token approve(address,uint256) is not ERC-20 allowance.
        if probe_errors is not None:
            probe_errors.append({"kind": kind, "contract": token, "spender": spender,
                                 "error": short_error(exc)})
        return None


async def scan_permit2(client: httpx.AsyncClient, rpc_url: str, block: int, wallet: str, known_tokens: dict, explorer: str) -> tuple[list[dict], dict]:
    """Discover candidate Permit2 spender permissions in recent Permit2 logs only.

    Does not discover signatures not submitted onchain, or older authorizations.
    """
    if LOG_LOOKBACK == 0:
        return [], {"status": "not_checked", "reason": "lookback disabled"}
    start = max(0, block - LOG_LOOKBACK)
    candidates = {}
    errors = []
    async def one_window(left: int):
        try:
            logs = await rpc(client, rpc_url, "eth_getLogs", [{"fromBlock": hex(left), "toBlock": hex(min(left + 499, block)), "address": PERMIT2, "topics": [None, "0x" + encode_address(wallet)]}])
            if not isinstance(logs, list):
                raise ValueError("Invalid event logs")
            return logs[:300], ["Permit2 logs truncated"] if len(logs) > 300 else []
        except Exception as exc:
            return [], [short_error(exc)]
    windows = await asyncio.gather(*(one_window(left) for left in range(start, block + 1, 500)))
    for logs, problems in windows:
        errors.extend(problems)
        for log in logs:
            topics = log.get("topics") or []
            # Approval and Permit events index (owner, token, spender); validate onchain.
            if len(topics) != 4:
                continue
            token = "0x" + str(topics[2])[-40:]
            spender = "0x" + str(topics[3])[-40:]
            if ADDRESS.fullmatch(token) and ADDRESS.fullmatch(spender):
                candidates[(token.lower(), spender.lower())] = (token, spender, log.get("transactionHash"))
    result = []
    for token, spender, txhash in list(candidates.values())[:35]:
        try:
            data = "0x927da105" + encode_address(wallet) + encode_address(token) + encode_address(spender)
            raw = await rpc(client, rpc_url, "eth_call", [{"to": PERMIT2, "data": data}, "latest"])
            words = [int(raw[2 + i * 64: 2 + (i + 1) * 64], 16) for i in range(3)]
            if len(raw) < 194:
                continue
            amount, expiry, nonce = words
            if amount == 0 or expiry <= int(time.time()):
                continue
            meta = known_tokens.get(token.lower(), {})
            result.append({"kind": "permit2_spender", "token_contract": token, "token_symbol": meta.get("symbol", "Unknown token"), "spender": spender, "active": True, "raw_allowance": str(amount), "allowance": numeric_string(amount, meta["decimals"]) if isinstance(meta.get("decimals"), int) else None, "expiration": expiry, "unlimited": amount == MAX_UINT160, "risk": "attention" if amount == MAX_UINT160 else "review", "reason": "Live Permit2 per-spender allowance until expiry; separate from ERC-20→Permit2 approval", "evidence": {"tx_hash": txhash, "discovery": "bounded_permit2_events_plus_current_allowance", "explorer_url": explorer + "/address/" + PERMIT2}})
        except Exception as exc:
            errors.append(short_error(exc))
    return result, {"status": "partial" if errors else "bounded", "from_block": start, "to_block": block, "pairs_discovered": len(candidates), "checked": min(len(candidates), 35), "message": "Older events and offchain unsubmitted signatures are not enumerable from an address", "errors": errors[:2]}


async def scan_chain(client: httpx.AsyncClient, key: str, cfg: dict, wallet: str) -> dict:
    rpc_url = os.getenv("RPC_" + key.upper(), cfg["rpc"])
    indexer_url = os.getenv("INDEXER_" + key.upper(), cfg["indexer"])
    # Routescan Blockscout-compatible v2 requires a paid key. Avoid a predictable 401.
    indexer_auth_missing = (key == "bsc" and urlsplit(indexer_url).hostname == "blockscout.routescan.io"
                            and not os.getenv("BLOCKSCOUT_API_KEY"))
    if indexer_auth_missing:
        indexer_url = ""
    result: dict = {"chain": key, "name": cfg["name"], "chain_id": cfg["id"], "symbol": cfg["symbol"], "native_balance": None, "native_usd": None, "block": None, "native_status": "unverified", "tokens": [], "nft_assets": [], "approvals": [], "sweeper": {"status": "not_checked"}, "delegation": {"status": "not_checked"}, "coverage": {}, "error": None}
    if indexer_auth_missing:
        result["coverage"]["bsc_indexer_auth"] = "ROUTESCAN_PAID_KEY_MISSING__INDEXER_DISCOVERY_DISABLED"
    else:
        result["coverage"]["bsc_indexer_auth"] = "NOT_APPLICABLE_OR_CONFIGURED"
    block = None
    try:
        chain_id, blockhex = await asyncio.gather(
            rpc(client, rpc_url, "eth_chainId", []), rpc(client, rpc_url, "eth_blockNumber", []))
        if int(chain_id, 16) != cfg["id"]:
            raise ValueError("RPC chain ID mismatch — refusing untrusted data")
        block = int(blockhex, 16)
        # Native balance and token balances use the SAME per-chain snapshot block.
        nativehex = await rpc(client, rpc_url, "eth_getBalance", [wallet, hex(block)])
        result.update(block=block, native_status="verified", native_balance=numeric_string(int(nativehex, 16), 18))
    except Exception as exc:
        result["error"] = short_error(exc)
        result["coverage"]["rpc"] = "unavailable: " + result["error"]
        result["quality"] = evaluate_coverage(result)
        return result
    result["coverage"]["rpc"] = "live_head_checked"
    try:
        code = await rpc(client, rpc_url, "eth_getCode", [wallet, "latest"])
        if isinstance(code, str) and code.lower().startswith("0xef0100") and len(code) == 48:
            result["delegation"] = classify_delegation({"status": "eip7702_delegated", "delegate": "0x" + code[8:48], "meaning": "An EIP-7702 delegation designation exists on this chain."}, key)
        else:
            result["delegation"] = {"status": "none_detected" if code in ("0x", "0x0", "0x00") else "contract_or_custom_code"}
    except Exception as exc:
        result["delegation"] = {"status": "unverified", "error": short_error(exc)}

    result["coverage"]["inventory_sources"] = []
    tok_items = []
    tx_items = []
    tok_complete = False
    tx_complete = False
    async def load_tokens():
        if not indexer_url:
            raise RuntimeError("Token indexer unavailable or not configured for this chain")
        # Blockscout-compatible providers can expose a complete-looking,
        # unpaginated token-balances endpoint *as well as* paginated /tokens.
        # Combine both inventories, never infer global completeness from either.
        pages, balances = await asyncio.gather(
            indexer_pages(client, indexer_url, "/addresses/" + wallet + "/tokens",
                          MAX_TOKEN_PAGES, {"type": "ERC-20"}),
            indexer_get(client, indexer_url, "/addresses/" + wallet + "/token-balances"),
            return_exceptions=True)
        items = []
        pages_complete = False
        if not isinstance(pages, Exception):
            items.extend(pages[0]); pages_complete = pages[1]
        if isinstance(balances, list):
            items.extend(x for x in balances if isinstance(x, dict))
            result["coverage"]["token_balance_endpoint"] = "returned_" + str(len(balances)) + "_entries_not_guaranteed_complete"
        elif isinstance(balances, Exception):
            result["coverage"]["token_balance_endpoint"] = "unavailable: " + short_error(balances)
        else:
            result["coverage"]["token_balance_endpoint"] = "invalid_provider_format"
        if isinstance(pages, Exception) and not isinstance(balances, list):
            raise RuntimeError("Both token inventory endpoints unavailable")
        result["coverage"]["inventory_sources"].append({
            "name": "blockscout-compatible", "state": "exhausted" if pages_complete else "partial",
            "observations": len(items), "max_pages": MAX_TOKEN_PAGES,
            "token_balances_endpoint": isinstance(balances, list),
            "global_completeness": False})
        return items, pages_complete
    async def load_nfts():
        if not indexer_url:
            raise RuntimeError("NFT indexer not configured")
        # Holdings discovery is indexer evidence ONLY; ownerOf/1155 balances are
        # not yet verified in this release. Never infer NFT safety or USD value.
        return await indexer_pages(client, indexer_url,
                                   "/addresses/" + wallet + "/nft", MAX_TOKEN_PAGES)
    async def load_transactions():
        if not indexer_url:
            raise RuntimeError("Indexer not configured; no recent transaction history")
        return await indexer_pages(client, indexer_url, "/addresses/" + wallet + "/transactions", MAX_TX_PAGES)
    async def load_native_price():
        if not indexer_url:
            raise RuntimeError("Indexer not configured; no native coin price")
        d = await indexer_get(client, indexer_url, "/stats")
        return as_decimal(d.get("coin_price")) if isinstance(d, dict) else None
    loaded = await asyncio.gather(load_tokens(), load_transactions(), load_native_price(), load_nfts(), return_exceptions=True)
    token_err, tx_err = None, None
    if isinstance(loaded[3], Exception):
        result["coverage"]["nft_index"] = "unavailable: " + short_error(loaded[3])
    else:
        nft_rows, nft_complete = loaded[3]
        nfts=[]
        nft_seen=set()
        for item in nft_rows:
            if not isinstance(item,dict):
                continue
            meta=item.get('token') or {}
            if not isinstance(meta,dict):
                continue
            contract=hash_of(meta.get('address_hash') or meta.get('address') or '')
            if not ADDRESS.fullmatch(contract):
                continue
            instance=item.get('token_instance')
            instance_id=instance.get('id') if isinstance(instance,dict) else None
            identifier=str(item.get('id') or item.get('token_id') or instance_id or '')
            standard=str(meta.get('type') or '').upper()
            if standard not in ('ERC-721','ERC-1155') or not identifier.isdigit():
                continue
            identity=(contract.lower(),identifier)
            if identity in nft_seen:
                continue
            nft_seen.add(identity)
            nfts.append({'contract':contract,'token_id':identifier,'standard':standard,
                         'symbol':str(meta.get('symbol') or 'NFT')[:24],
                         'name':str(meta.get('name') or 'Unknown NFT')[:70],
                         'balance':str(item.get('value') or '1'),
                         'source':'blockscout-nft-indexer',
                         'verification_status':'INDEXER_REPORTED_NOT_ONCHAIN_RECHECKED',
                         'usd_value':None,'explorer_url':cfg['explorer']+'/token/'+contract})
        result['nft_assets']=nfts
        result["coverage"]["nft_index"] = ('indexer_pages_complete' if nft_complete else
                                             f'partial_first_{MAX_TOKEN_PAGES}_pages')
    if isinstance(loaded[0], Exception):
        token_err = short_error(loaded[0])
        result["coverage"]["inventory_sources"].append({"name": "blockscout-compatible", "state": "unavailable", "reason": token_err})
    else:
        tok_items, tok_complete = loaded[0]
    if isinstance(loaded[1], Exception):
        tx_err = short_error(loaded[1])
    else:
        tx_items, tx_complete = loaded[1]
    # Indexer /stats native price has no reliable quote timestamp. Store as
    # indicative evidence only, never silently merge into trusted USD total.
    if not isinstance(loaded[2], Exception) and loaded[2] is not None:
        result["coverage"]["indicative_native_price_unverified"] = str(loaded[2])
    native_quote, native_price_state = await native_usd_quote(client, key)
    result["coverage"]["native_usd_price"] = native_price_state
    if native_quote:
        native = as_decimal(result["native_balance"])
        if native is not None:
            result["native_usd"] = format(native * native_quote["price"], "f")
            result["native_price_source"] = "defillama_coingecko_id"
            result["native_price_timestamp"] = native_quote["timestamp"]
    result["coverage"]["token_index"] = "unavailable: " + token_err if token_err else ("indexer_pages_complete" if tok_complete else f"partial_first_{MAX_TOKEN_PAGES}_pages")
    result["coverage"]["transactions"] = "unavailable: " + tx_err if tx_err else ("recent_history_complete" if tx_complete else f"partial_first_{MAX_TX_PAGES}_pages")
    result["coverage"]["usd_prices"] = "indicative_indexer_quotes" if not isinstance(loaded[2], Exception) else "unavailable"
    parsed = [parse_token(item, key, cfg["explorer"]) for item in tok_items]
    tokens = [t for t in parsed if t]
    moralis_items = []
    if os.getenv("MORALIS_API_KEY"):
        try:
            moralis_items, moralis_complete = await moralis_token_index(client, wallet, key, cfg["explorer"])
            result["coverage"]["moralis_token_index"] = "complete_pages" if moralis_complete else f"partial_first_{MAX_TOKEN_PAGES}_pages"
            result["coverage"]["inventory_sources"].append({
                "name": "moralis", "state": "exhausted" if moralis_complete else "partial",
                "observations": len(moralis_items), "max_pages": MAX_TOKEN_PAGES, "global_completeness": False})
        except Exception as exc:
            reason = short_error(exc)
            result["coverage"]["moralis_token_index"] = "unavailable: " + reason
            result["coverage"]["inventory_sources"].append({"name": "moralis", "state": "unavailable", "reason": reason})
    else:
        result["coverage"]["moralis_token_index"] = "not_configured"
        result["coverage"]["inventory_sources"].append({"name": "moralis", "state": "not_configured"})
    tokens, merge_stats = union_token_candidates(tokens, moralis_items)
    result["coverage"]["provider_merge"] = merge_stats
    result["coverage"]["inventory_status"] = inventory_status(result["coverage"]["inventory_sources"])
    result["coverage"]["inventory_claim"] = "SOURCE_BOUNDED; NEVER GLOBAL_COMPLETE"
    # V2.5: every candidate balance is re-read directly onchain at one block.
    # Indexer USD quotes never enter KNOWN ASSET VALUE without onchain balance,
    # decimals and a fresh contract-address-specific price quote.
    verified_tokens, asset_coverage = await reconcile_assets(
        client, rpc, rpc_url, wallet, key, block, tokens, KNOWN_TOKENS[key], cfg["explorer"])
    result["tokens"] = [classify_token(t, key) for t in verified_tokens]
    result["coverage"]["asset_valuation"] = asset_coverage
    result["coverage"]["token_contracts_returned"] = len(result["tokens"])
    result["coverage"]["token_index_discovery_limit"] = (
        "BOUNDED; includes unverified indexer candidates; indexer may omit additional tokens")
    result["coverage"]["known_token_rpc"] = (
        "bounded_contract_probe" if not asset_coverage["balance_verification_failures"]
        else "partial_onchain_rpc_probe_failures")
    result["coverage"]["usd_prices"] = (
        "fresh_contract_address_quotes_only; " + asset_coverage["price_service"])

    candidates = [c for tx in tx_items if (c := candidate_from_tx(tx, wallet))]
    # Permit2 is a widely-used spender. Unlike arbitrary spender discovery, its
    # canonical address is known. Check current ERC-20 -> Permit2 allowances on
    # canonical known tokens even if historic events / indexers are unavailable.
    for _, contract, _ in KNOWN_TOKENS[key]:
        candidates.append({"kind": "erc20", "contract": contract, "spender": PERMIT2,
                           "tx_hash": None, "discovery": "known_token_to_canonical_permit2_direct_probe"})
    erc20_contracts = list({t["contract"].lower(): t["contract"] for t in result["tokens"]}.values())[:MAX_LOG_TOKEN_CONTRACTS]
    nft_contracts = []
    # NFTs held are discoverable from indexer, but a zero-NFT collection can still have a live approval.
    if token_err is None:
        try:
            nft_rows, _ = await indexer_pages(client, indexer_url, "/addresses/" + wallet + "/tokens", 1, {"type": "ERC-721,ERC-1155"})
            nft_contracts = list({h.lower(): h for row in nft_rows if ADDRESS.fullmatch(h := hash_of((row.get("token") or {}).get("address_hash")))}.values())[:MAX_LOG_TOKEN_CONTRACTS]
        except Exception:
            pass
    (logs1, info1), (logs2, info2), (permit_results, permit_coverage) = await asyncio.gather(
        fetch_rpc_logs(client, rpc_url, block, erc20_contracts, wallet, "erc20"),
        fetch_rpc_logs(client, rpc_url, block, nft_contracts, wallet, "operator"),
        scan_permit2(client, rpc_url, block, wallet, {t["contract"].lower(): t for t in result["tokens"]}, cfg["explorer"]),
    )
    result["coverage"]["approval_event_logs"] = info1
    result["coverage"]["nft_operator_event_logs"] = info2
    candidates.extend(logs1 + logs2)
    # Standard ERC-20 approval of the Permit2 contract is also checked above.
    # Permit2 internal spender discovery here is still only a recent-log sample.
    result["coverage"]["permit2_internal"] = permit_coverage
    found = {}
    for candidate in candidates:
        identity = (candidate["kind"], candidate["contract"].lower(), candidate["spender"].lower())
        if identity not in found:
            found[identity] = candidate
    meta = {t["contract"].lower(): t for t in result["tokens"]}
    probe_errors: list[dict] = []
    approval_candidates = list(found.values())[:50]
    approvals = await asyncio.gather(*(check_candidate(client, rpc_url, wallet, v, meta, cfg["explorer"], probe_errors)
                                       for v in approval_candidates))
    result["approvals"] = [a for a in approvals if a] + permit_results
    result["coverage"]["allowances_checked"] = len(approvals) - len(probe_errors)
    result["coverage"]["allowance_candidates_found"] = len(found)
    result["coverage"]["allowance_candidates_unchecked_due_to_cap"] = max(0, len(found) - len(approval_candidates))
    result["coverage"]["allowance_probe_errors"] = {"count": len(probe_errors), "examples": probe_errors[:3]}
    result["coverage"]["approvals_completeness"] = "partial_historical_discovery"  # even if zero approvals
    result["coverage"]["known_token_permit2_direct_probes"] = len(KNOWN_TOKENS[key])
    result["sweeper"] = find_sweeper_pattern(tx_items, wallet, cfg["explorer"]) if tx_items else {"status": "not_checked" if tx_err else "no_pattern_in_sample", "recent_transactions_examined": len(tx_items), "is_proof_of_compromise": False}
    result["quality"] = evaluate_coverage(result)
    return result


@app.get("/api/health")
def health():
    return {"ok": True, "service": "guardian360", "version": "2.6.0-rc-hold", "mode": "INTERNAL_REVIEW_ONLY", "chains": list(CHAINS)}


@app.get("/api/chains")
def available_chains():
    return {"chains": [{"key": key, "name": value["name"], "chain_id": value["id"]} for key, value in CHAINS.items()]}


@app.post("/api/scan")
async def scan(request: ScanRequest):
    address = request.address.strip()
    if not ADDRESS.fullmatch(address):
        raise HTTPException(422, "Invalid EVM address")
    chosen = request.chains if request.chains is not None else list(CHAINS)
    if not chosen or len(set(chosen)) != len(chosen) or any(key not in CHAINS for key in chosen):
        raise HTTPException(422, "Choose 1-4 distinct supported chains")
    async with SCAN_SLOTS:
        async with httpx.AsyncClient(headers={"User-Agent": "Guardian360/1.1.2; read-only wallet audit"}, follow_redirects=False, limits=httpx.Limits(max_connections=25)) as client:
            chains = await asyncio.gather(*(scan_chain(client, key, CHAINS[key], address) for key in chosen))
    approvals = sum(len(c["approvals"]) for c in chains)
    unlimited = sum(bool(a.get("unlimited")) for c in chains for a in c["approvals"])
    flagged = sum(c["sweeper"].get("status") == "pattern_detected" for c in chains)
    delegated = sum(c["delegation"].get("status") == "eip7702_delegated" for c in chains)
    unavailable = sum(c["native_status"] != "verified" for c in chains)
    forensic = summarize_forensic(chains)
    for chain in chains:
        partial = forensic['priced_usd_by_chain'][chain['chain']]
        chain['priced_usd_partial'] = partial['usd_priced_partial']
        chain['priced_assets_count'] = partial['priced_entries']
    payload = {"address": address, "timestamp": int(time.time()), "version": "2.6.0-public-readonly", "chains": chains, "requested_chains": chosen, "summary": {"usd_known_sum": forensic["recognized_usd_partial"], "priced_usd_by_chain": forensic["priced_usd_by_chain"], "valuation_scope": "only_requested_scanned_chains; partial; independent_block_and_price_timestamps", "usd_unverified_excluded": forensic["excluded_unverified_usd_quotes"], "token_review_count": forensic["token_review_count"], "all_approvals_status": "UNKNOWN_INCOMPLETE", "usd_completeness": "partial_or_unknown", "active_approvals_discovered": approvals, "unlimited_approvals_discovered": unlimited, "sweeper_pattern_chains": flagged, "eip7702_delegation_chains": delegated, "rpc_unavailable_chains": unavailable, "risk_level": "investigate" if flagged else ("review_permissions" if unlimited else ("review_token_integrity" if forensic["token_review_count"] else "not_assessed")), "never_a_safety_clearance": True, "security_clearance": False, "audit_quality": "INCOMPLETE"}, "coverage": {"erc20_balances": "bounded_indexer_candidates_plus_curated_rpc_probes_at_block; not guaranteed complete", "approvals": "recent_wallet_transactions_and_bounded_events_only; older or unindexed approvals can be missed", "nft_operator": "recent_transaction_and_bounded_event_candidates; NFT holdings not comprehensive", "permit2": "partial recent onchain spender event discovery; older approvals and unsubmitted signatures may be missed", "sweeper": "heuristic on recent native-value top-level transactions only; cannot establish compromised key", "device_spyware": "not_detectable_from_wallet_address", "usd": "onchain-balance-verified + fresh contract-address quote when available; still partial and not guaranteed liquid"}, "disclaimer": "This is an incomplete read-only security screen. No warnings found DOES NOT mean safe. No keys, wallet connection or transactions requested."}
    payload["asset_register"] = asset_register(chains)
    record_aggregate_scan()
    return payload


# GUARDIAN V2.4 - Read-only verification endpoints for browser-wallet revoke.
# No private keys or blockchain send operations exist on this server.

class RevokeRequest(BaseModel):
    address: str
    chain: str
    kind: str
    token_contract: str
    spender: str
    token_id: str | int | None = None


class RevokeStatusRequest(RevokeRequest):
    tx_hash: str


def validated_revoke(body: RevokeRequest) -> dict:
    try:
        return normalize_request(body.address, body.chain, body.kind,
                                 body.token_contract, body.spender, body.token_id, CHAINS)
    except UnsafeIntent as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/api/revoke/verify', tags=['Verified revoke'])
async def revoke_verify(body: RevokeRequest):
    spec = validated_revoke(body)
    config = CHAINS[spec['chain']]
    rpc_url = os.getenv('RPC_' + spec['chain'].upper(), config['rpc'])
    async with httpx.AsyncClient(timeout=15) as client:
        async def do_rpc(method, params):
            return await rpc(client, rpc_url, method, params)
        try:
            return await verify_request(spec, do_rpc, config['id'])
        except UnsafeIntent as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, 'Blockchain verification unavailable; no revoke transaction prepared') from exc


@app.post('/api/revoke/status', tags=['Verified revoke'])
async def revoke_status(body: RevokeStatusRequest):
    spec = validated_revoke(body)
    config = CHAINS[spec['chain']]
    rpc_url = os.getenv('RPC_' + spec['chain'].upper(), config['rpc'])
    async with httpx.AsyncClient(timeout=15) as client:
        async def do_rpc(method, params):
            return await rpc(client, rpc_url, method, params)
        try:
            return await inspect_receipt(spec, body.tx_hash, do_rpc, config['id'])
        except UnsafeIntent as exc:
            raise HTTPException(409, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, 'Onchain receipt verification unavailable') from exc

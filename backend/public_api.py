"""Public Guardian 360 scanner API: read-only boundary.

ONLY health, chains and scan routes are exposed. No revoke verification,
wallet signing, status/receipt endpoints or analytics/admin routes.
Public scans default OFF until explicitly enabled after HTTPS QA.
"""
from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from main import ScanRequest, scan as internal_scan, available_chains

app = FastAPI(title='Guardian 360 PUBLIC READ-ONLY API', version='2.5.0-public-beta',
              docs_url=None, redoc_url=None, openapi_url=None)
allowed = [x.strip() for x in os.getenv('CORS_ORIGINS', 'https://vubounty.github.io').split(',') if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed, allow_credentials=False,
                   allow_methods=['GET','POST'], allow_headers=['Content-Type'])

# Global per-process limiter protects a free/public RPC pool and never stores IPs.
# This is NOT a distributed rate limiter; add a WAF or gateway before scaling.
_hits: deque[float] = deque()
_limiter = asyncio.Lock()

def enabled() -> bool:
    return os.getenv('GUARDIAN_PUBLIC_ENABLE_SCAN','false').lower() == 'true'

async def admission() -> None:
    now=time.monotonic()
    limit=max(1,min(60,int(os.getenv('GUARDIAN_PUBLIC_MAX_SCANS_PER_MINUTE','8'))))
    async with _limiter:
        while _hits and _hits[0] <= now-60: _hits.popleft()
        if len(_hits)>=limit:
            raise HTTPException(429,'Public beta rate limit reached. Retry in one minute.',headers={'Retry-After':'60'})
        _hits.append(now)

@app.get('/api/health')
def public_health():
    return {'ok':True,'service':'guardian360','version':'2.5.0-public-beta',
            'mode':'PUBLIC_READ_ONLY','scan_enabled':enabled(),
            'revoke_endpoints':False,'wallet_signing':False,
            'audit_coverage':'INCOMPLETE; no safety clearance'}

@app.get('/api/chains')
def public_chains():
    return available_chains()

@app.post('/api/scan')
async def public_scan(payload: ScanRequest, request: Request):
    if not enabled():
        raise HTTPException(503,'Public scan is not enabled until HTTPS release gates are approved.')
    length=request.headers.get('content-length')
    if length and (not length.isdigit() or int(length)>4096):
        raise HTTPException(413,'Request exceeds public beta input limit')
    await admission()
    try:
        return await asyncio.wait_for(internal_scan(payload),timeout=90)
    except TimeoutError:
        raise HTTPException(504,'Scan timed out; audit incomplete. Please retry later.')

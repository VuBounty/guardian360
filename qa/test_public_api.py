from fastapi.testclient import TestClient
import pytest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
import public_api

client = TestClient(public_api.app)

def test_fail_closed_by_default(monkeypatch):
    monkeypatch.delenv('GUARDIAN_PUBLIC_ENABLE_SCAN',raising=False)
    r=client.post('/api/scan',json={'address':'0x'+'1'*40,'chains':['bsc']})
    assert r.status_code == 503

def test_scan_gate_and_chain_scope(monkeypatch):
    monkeypatch.setenv('GUARDIAN_PUBLIC_ENABLE_SCAN','true')
    async def fake_scan(body):
        return {'requested_chains':body.chains,'address':body.address,'summary':{'all_approvals_status':'UNKNOWN_INCOMPLETE'}}
    monkeypatch.setattr(public_api,'internal_scan',fake_scan)
    r=client.post('/api/scan',json={'address':'0x'+'1'*40,'chains':['bsc']})
    assert r.status_code==200
    assert r.json()['requested_chains']==['bsc']
    assert r.json()['summary']['all_approvals_status']=='UNKNOWN_INCOMPLETE'

def test_public_routes_exclude_revoke_and_analytics():
    assert client.post('/api/revoke/verify',json={}).status_code==404
    assert client.post('/api/revoke/status',json={}).status_code==404
    assert client.get('/api/analytics/summary').status_code==404
    assert client.get('/docs').status_code==404

def test_mode_and_features(monkeypatch):
    monkeypatch.delenv('GUARDIAN_PUBLIC_ENABLE_SCAN',raising=False)
    r=client.get('/api/health').json()
    assert r['mode']=='PUBLIC_READ_ONLY' and not r['scan_enabled'] and not r['revoke_endpoints'] and not r['wallet_signing']

def test_cors_whitelist(monkeypatch):
    r=client.options('/api/scan',headers={'Origin':'https://vubounty.github.io','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
    assert r.status_code==200
    assert r.headers.get('access-control-allow-origin')=='https://vubounty.github.io'
    r=client.options('/api/scan',headers={'Origin':'https://evil.example','Access-Control-Request-Method':'POST'})
    assert r.status_code==400

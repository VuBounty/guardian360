"""Isolated owner telemetry QA; temp DB only, never touches user's analytics."""
import sys
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
import analytics
from main import app

@pytest.fixture
def harness(monkeypatch,tmp_path):
    monkeypatch.setenv('GUARDIAN_ANALYTICS_DB',str(tmp_path/'qa-metrics.sqlite3'))
    monkeypatch.setenv('GUARDIAN_ANALYTICS_SECRET_FILE',str(tmp_path/'qa-secret'))
    monkeypatch.setenv('GUARDIAN_ANALYTICS_ADMIN_KEY','Q'*40)
    return TestClient(app),tmp_path

def summary(client,key='Q'*40):
    return client.get('/api/analytics/summary',headers={'X-Guardian-Admin':key})

def test_admin_private_and_empty_metrics(harness):
    client,_=harness
    assert summary(client,key='wrong').status_code==401
    response=summary(client); assert response.status_code==200
    report=response.json(); assert report['all_scans_aggregate']==0
    assert report['opted_in_unique_browsers']==0
    assert len(report['history_14d'])==14

def test_opt_in_user_count_and_dedup(harness):
    client,_=harness
    browser=str(uuid.uuid4())
    event={'visitor_id':browser,'event':'visit'}
    assert client.post('/api/analytics/event',json=event).json()['counted'] is True
    assert client.post('/api/analytics/event',json=event).json()['counted'] is False
    assert client.post('/api/analytics/event',json={**event,'event':'scan_complete'}).json()['counted'] is True
    report=summary(client).json();assert report['opted_in_unique_browsers']==1
    assert report['consented_visits']==1
    assert report['completed_scans_reported']==1

def test_aggregate_scans_not_unique_people(harness):
    client,_=harness
    analytics.record_aggregate_scan(); analytics.record_aggregate_scan(); analytics.record_aggregate_scan()
    report=summary(client).json()
    assert report['all_scans_aggregate']==3
    assert report['opted_in_unique_browsers']==0
    assert report['consented_visits']==0

def test_erasure_does_not_delete_aggregate_count(harness):
    client,_=harness
    browser=str(uuid.uuid4())
    client.post('/api/analytics/event',json={'visitor_id':browser,'event':'visit'})
    analytics.record_aggregate_scan()
    assert client.post('/api/analytics/erase',json={'visitor_id':browser}).json()['erased'] is True
    report=summary(client).json()
    assert report['opted_in_unique_browsers']==0
    assert report['all_scans_aggregate']==1

def test_no_pii_in_analytics_sqlite(harness):
    client,root=harness
    browser=str(uuid.uuid4()); wallet='0x'+'44'*20  # synthetic test-only address
    client.post('/api/analytics/event',json={'visitor_id':browser,'event':'visit'})
    raw=(root/'qa-metrics.sqlite3').read_bytes()
    assert wallet.encode() not in raw
    assert browser.encode() not in raw
    assert b'visitor_hash' in raw

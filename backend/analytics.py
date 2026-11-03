"""Privacy-first opt-in analytics for Guardian 360.

Never stores wallet addresses, access tokens, IP addresses, or user agents.
Unique users means opted-in anonymous browser identifiers, not people.
This optional server-side counter requires a persistent backend volume in production.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix='/api/analytics', tags=['Privacy-first analytics'])
ID = re.compile(r'^[0-9a-fA-F-]{36}$')
EVENTS = {'visit', 'scan_complete'}


class EventBody(BaseModel):
    visitor_id: str = Field(min_length=36, max_length=36)
    event: str = Field(min_length=1, max_length=30)


class VisitorBody(BaseModel):
    visitor_id: str = Field(min_length=36, max_length=36)


def database_file() -> Path:
    return Path(os.getenv('GUARDIAN_ANALYTICS_DB', str(Path(__file__).parent / 'data' / 'analytics.db')))


def secret_file() -> Path:
    return Path(os.getenv('GUARDIAN_ANALYTICS_SECRET_FILE', str(Path(__file__).parent / 'data' / 'analytics_salt')))


def digest_visitor(visitor_id: str) -> str:
    if not ID.fullmatch(visitor_id):
        raise HTTPException(422, 'Invalid anonymous ID')
    path = secret_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        # Local-first development convenience; for production mount a persistent volume.
        try:
            with path.open('xb') as f:
                f.write(secrets.token_bytes(32))
            os.chmod(path, 0o600)
        except FileExistsError:
            pass
    secret = path.read_bytes()
    return hmac.new(secret, visitor_id.encode('ascii'), hashlib.sha256).hexdigest()


def connect() -> sqlite3.Connection:
    path = database_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=5)
    db.execute('PRAGMA busy_timeout=3000')
    db.execute('CREATE TABLE IF NOT EXISTS events ('
               'visitor_hash TEXT NOT NULL, event TEXT NOT NULL, '
               'day TEXT NOT NULL, timestamp INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS aggregate_scans ('
               'day TEXT PRIMARY KEY, scans INTEGER NOT NULL DEFAULT 0)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_guardian_event_day ON events(day, event)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_guardian_event_visitor ON events(visitor_hash, event, timestamp)')
    return db


def record_aggregate_scan() -> None:
    """Single anonymous increment; never receives or stores wallet/IP/user ID.

    Works regardless of opt-in. Used to assess basic usage demand without
    tracking participants. This is a count of scans, NOT a count of people.
    """
    day = datetime.now(timezone.utc).date().isoformat()
    try:
        with connect() as db:
            db.execute('INSERT INTO aggregate_scans(day,scans) VALUES(?,1) '
                       'ON CONFLICT(day) DO UPDATE SET scans=scans+1', (day,))
    except sqlite3.Error:
        # A telemetry storage issue must never block a wallet read-only scan.
        return


@router.post('/event')
def record(body: EventBody):
    if body.event not in EVENTS:
        raise HTTPException(422, 'Unsupported event')
    visitor = digest_visitor(body.visitor_id)
    now = int(time.time())
    day = datetime.fromtimestamp(now, timezone.utc).date().isoformat()
    with connect() as db:
        last = db.execute('SELECT MAX(timestamp) FROM events WHERE visitor_hash=? AND event=?',
                          (visitor, body.event)).fetchone()[0]
        if last is not None and now - int(last) < (3600 * 12 if body.event == 'visit' else 20):
            return {'ok': True, 'counted': False}
        count = db.execute('SELECT COUNT(*) FROM events WHERE visitor_hash=? AND day=?', (visitor, day)).fetchone()[0]
        if count >= 100:
            return {'ok': True, 'counted': False}
        db.execute('INSERT INTO events VALUES(?,?,?,?)', (visitor, body.event, day, now))
    return {'ok': True, 'counted': True}


@router.post('/erase')
def erase(body: VisitorBody):
    visitor = digest_visitor(body.visitor_id)
    with connect() as db:
        db.execute('DELETE FROM events WHERE visitor_hash=?', (visitor,))
    return {'ok': True, 'erased': True}


def authorized(key: str | None) -> None:
    configured = os.getenv('GUARDIAN_ANALYTICS_ADMIN_KEY', '')
    if len(configured) < 24:
        raise HTTPException(503, 'Admin reporting disabled: configure GUARDIAN_ANALYTICS_ADMIN_KEY')
    if not key or not hmac.compare_digest(configured, key):
        raise HTTPException(401, 'Unauthorized')


@router.get('/summary')
def summary(x_guardian_admin: str | None = Header(default=None)):
    authorized(x_guardian_admin)
    today = datetime.now(timezone.utc).date()
    first = (today - timedelta(days=13)).isoformat()
    with connect() as db:
        all_visitors = db.execute('SELECT COUNT(DISTINCT visitor_hash) FROM events').fetchone()[0]
        total_visits = db.execute("SELECT COUNT(*) FROM events WHERE event='visit'").fetchone()[0]
        scans = db.execute("SELECT COUNT(*) FROM events WHERE event='scan_complete'").fetchone()[0]
        days = db.execute('SELECT day, COUNT(DISTINCT visitor_hash), '
                          "SUM(CASE WHEN event='visit' THEN 1 ELSE 0 END), "
                          "SUM(CASE WHEN event='scan_complete' THEN 1 ELSE 0 END) "
                          'FROM events WHERE day >= ? GROUP BY day ORDER BY day', (first,)).fetchall()
        aggregate_total = db.execute('SELECT COALESCE(SUM(scans),0) FROM aggregate_scans').fetchone()[0]
        aggregate_days = dict(db.execute('SELECT day,scans FROM aggregate_scans WHERE day >= ?', (first,)).fetchall())
        previous = db.execute('SELECT COUNT(DISTINCT visitor_hash) FROM events '
                              'WHERE day < ? AND visitor_hash IN '
                              '(SELECT visitor_hash FROM events WHERE day >= ?)', (first, first)).fetchone()[0]
    grid = {d: {'day': d, 'unique_browsers': u, 'visits': v or 0, 'scans': s or 0} for d, u, v, s in days}
    history = [(today - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    return {
        'opted_in_unique_browsers': all_visitors, 'consented_visits': total_visits,
        'completed_scans_reported': scans, 'all_scans_aggregate': aggregate_total, 'returning_browsers_last_14d': previous,
        'history_14d': [{**grid.get(d, {'day': d, 'unique_browsers': 0, 'visits': 0, 'scans': 0}), 'all_scans': aggregate_days.get(d,0)} for d in history],
        'disclaimer': 'All-scans aggregate counts scan operations without identifying users. Unique-browser and return metrics include only consented browsers. No wallet addresses stored.'
    }

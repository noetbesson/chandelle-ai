"""Encrypted account tokens and private busy intervals in the existing SQLite."""
import json
import os
import secrets
from functools import wraps
from threading import RLock
from cryptography.fernet import Fernet, InvalidToken
from backend.db import now
from .provider import CalendarError

LOCK = RLock()  # This beta runs one worker; DB uniqueness also protects persistent identities.

def calendar_locked(function):
    @wraps(function)
    def locked(*args,**kwargs):
        with LOCK:return function(*args,**kwargs)
    return locked

class CalendarStore:
    def __init__(self, db): self.db = db

    def cipher(self):
        try: return Fernet(os.environ['CALENDAR_TOKEN_KEY'].encode())
        except (KeyError, ValueError): raise CalendarError('calendar_encryption_not_configured') from None

    def seal(self, value): return self.cipher().encrypt(json.dumps(value).encode()).decode()

    def open(self, value):
        try: return json.loads(self.cipher().decrypt(value.encode()))
        except (InvalidToken, ValueError): raise CalendarError('calendar_reconnect_required') from None

    def connection(self, uid):
        with self.db.connect() as c:
            r = c.execute('SELECT * FROM v2_calendar_connections WHERE user_id=?', (uid,)).fetchone()
        if not r: raise CalendarError('calendar_not_connected')
        return dict(r)

    def save(self, uid, provider, credentials):
        with LOCK, self.db.connect() as c:
            c.execute('INSERT INTO v2_calendar_connections(user_id,provider,credentials,generation,status) VALUES(?,?,?,?,?) '
                      'ON CONFLICT(user_id) DO UPDATE SET provider=excluded.provider,credentials=excluded.credentials,'
                      'generation=excluded.generation,status=excluded.status,busy=NULL,synced_at=NULL,error=NULL',
                      (uid,provider,self.seal(credentials),secrets.token_hex(16),'connected'))
            # Reconnecting may select another external account. Never reuse its event IDs.
            c.execute('DELETE FROM v2_calendar_approvals WHERE user_id=?',(uid,))

    def credentials(self, uid):
        r=self.connection(uid)
        return r,self.open(r['credentials'])

    def update_credentials(self, row, data):
        with self.db.connect() as c:
            c.execute('UPDATE v2_calendar_connections SET credentials=? WHERE user_id=? AND generation=?',
                      (self.seal(data),row['user_id'],row['generation']))

    def disconnect(self, uid):
        with LOCK, self.db.connect() as c:
            for table in ('v2_calendar_oauth','v2_calendar_connections','v2_calendar_approvals','v2_calendar_events'):
                c.execute('DELETE FROM '+table+' WHERE user_id=?',(uid,))
        # Remote events stay in the provider calendar; no destructive side effect on disconnect.

    def status(self, uid):
        try: r=self.connection(uid)
        except CalendarError: return {'connected':False}
        return {'connected':True,'provider':r['provider'],'status':r['status'],
                'last_sync':r['synced_at'],'error':r['error'],'scope':'primary_calendar_only'}

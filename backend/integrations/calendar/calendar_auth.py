"""Server-side OAuth state, PKCE, encrypted caches and refresh. No secrets in responses."""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
import msal
from backend.db import now
from .store import CalendarStore, LOCK
from .provider import CalendarError

from .oauth_config import MS_SCOPES, callback_uri, google_flow, microsoft_app

class CalendarAuth:
    def __init__(self,db): self.store=CalendarStore(db);self.db=db

    def configured(self,provider):
        prefix={'google':'GOOGLE','outlook':'MICROSOFT'}.get(provider)
        if not prefix: return False
        try: self.store.cipher(); callback_uri(provider)
        except CalendarError: return False
        return all(os.getenv(prefix+'_'+k) for k in ('CLIENT_ID','CLIENT_SECRET'))

    def begin(self,uid,provider):
        if not self.configured(provider): raise CalendarError('calendar_oauth_not_configured')
        state=secrets.token_urlsafe(32)
        try:
            if provider=='google':
                flow=google_flow(state)
                url,_=flow.authorization_url(access_type='offline',prompt='consent',include_granted_scopes='true')
                saved={'state':state,'verifier':flow.code_verifier}
            else:
                saved=microsoft_app().initiate_auth_code_flow(MS_SCOPES,state=state,redirect_uri=callback_uri(provider),response_mode='query')
                url=saved['auth_uri']
            expires=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat()
            with self.db.connect() as c:
                c.execute('DELETE FROM v2_calendar_oauth WHERE expires_at<? OR user_id=?',(now(),uid))
                c.execute('INSERT INTO v2_calendar_oauth VALUES(?,?,?,?,?)',
                    (hashlib.sha256(state.encode()).hexdigest(),uid,provider,self.store.seal(saved),expires))
            return url
        except CalendarError: raise
        except Exception: raise CalendarError('calendar_authorization_failed') from None

    def finish(self,provider,params):
        with LOCK:return self._finish(provider,params)

    def _finish(self,provider,params):
        state=params.get('state','')
        if not state or len(state)>256: raise CalendarError('calendar_oauth_state_invalid')
        with LOCK, self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            key=hashlib.sha256(state.encode()).hexdigest()
            r=c.execute('SELECT * FROM v2_calendar_oauth WHERE state_hash=? AND provider=? AND expires_at>?',(key,provider,now())).fetchone()
            if not r: raise CalendarError('calendar_oauth_state_invalid')
            c.execute('DELETE FROM v2_calendar_oauth WHERE state_hash=?',(key,))
        if params.get('error'): raise CalendarError('calendar_consent_denied')
        try:
            saved=self.store.open(r['payload'])
            if provider=='google':
                flow=google_flow(state,saved['verifier'])
                flow.fetch_token(code=params.get('code'),timeout=15)
                import json
                credentials=json.loads(flow.credentials.to_json())
                if not credentials.get('refresh_token'): raise CalendarError('calendar_refresh_missing')
            else:
                cache=msal.SerializableTokenCache()
                app=microsoft_app(cache)
                result=app.acquire_token_by_auth_code_flow(saved,params)
                if 'access_token' not in result: raise CalendarError('calendar_token_exchange_failed')
                credentials={'cache':cache.serialize()}
            # A concurrent erasure removes the member's completion; do not reconnect it.
            with self.db.connect() as c:
                valid=c.execute("SELECT 1 FROM v2_memberships WHERE user_id=? AND status='completed'",(r['user_id'],)).fetchone()
            if not valid: raise CalendarError('calendar_profile_not_ready')
            self.store.save(r['user_id'],provider,credentials)
            return r['user_id']
        except CalendarError: raise
        except Exception: raise CalendarError('calendar_token_exchange_failed') from None

    def provider(self,uid):
        row,data=self.store.credentials(uid)
        if row['provider']=='google':
            from .google import GoogleCalendar
            return GoogleCalendar(self.store,row,data)
        from .outlook import OutlookCalendar
        return OutlookCalendar(self.store,row,data)

"""Google Calendar v3, primary calendar; deterministic event IDs prevent duplicate writes."""
import hashlib
import json
import httplib2
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from .provider import TimeSlot, CalendarError

class BoundedRequest(Request):
    def __call__(self,*args,**kwargs):
        kwargs['timeout']=15
        return super().__call__(*args,**kwargs)

class GoogleCalendar:
    def __init__(self,store,row,data): self.store,self.row,self.data=store,row,data

    def service(self):
        credentials=Credentials.from_authorized_user_info(self.data)
        if not credentials.valid:
            credentials.refresh(BoundedRequest())
            self.store.update_credentials(self.row,json.loads(credentials.to_json()))
        return build('calendar','v3',http=AuthorizedHttp(credentials,http=httplib2.Http(timeout=20)),cache_discovery=False)

    def get_busy_slots(self,start,end):
        try:
            response=self.service().freebusy().query(body={'timeMin':start.isoformat(),'timeMax':end.isoformat(),'timeZone':'UTC','items':[{'id':'primary'}]}).execute(num_retries=0)
            calendar=response['calendars']['primary']
            if calendar.get('errors'): raise CalendarError('calendar_read_failed')
            return [TimeSlot.model_validate(v) for v in calendar['busy']]
        except Exception: raise CalendarError('calendar_read_failed') from None

    @staticmethod
    def body(event):
        return {'summary':event.title,'location':event.location,'description':event.description,
                'start':{'dateTime':event.start.isoformat()},'end':{'dateTime':event.end.isoformat()}}

    def create_event(self,event,key):
        ident=hashlib.sha256(key.encode()).hexdigest()
        try:
            self.service().events().insert(calendarId='primary',body={**self.body(event),'id':ident},sendUpdates='none').execute(num_retries=0)
            return ident
        except Exception as exc:
            if getattr(getattr(exc,'resp',None),'status',None)==409:
                # A timed-out create may already exist, possibly with an older plan revision.
                self.update_event(ident,event)
                return ident
            raise CalendarError('calendar_write_failed') from None

    def update_event(self,event_id,event):
        try:
            self.service().events().patch(calendarId='primary',eventId=event_id,body=self.body(event),sendUpdates='none').execute(num_retries=0)
            return True
        except Exception: raise CalendarError('calendar_update_failed') from None

    def delete_event(self,event_id):
        try:
            self.service().events().delete(calendarId='primary',eventId=event_id,sendUpdates='none').execute(num_retries=0)
            return True
        except Exception as exc:
            if getattr(getattr(exc,'resp',None),'status',None) in (404,410): return True
            raise CalendarError('calendar_delete_failed') from None

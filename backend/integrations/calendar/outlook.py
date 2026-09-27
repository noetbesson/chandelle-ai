"""Microsoft Graph delegated access, personal and work accounts; bounded pagination."""
from urllib.parse import urlsplit, quote
from uuid import uuid5, NAMESPACE_URL
import httpx
import msal
from .oauth_config import microsoft_app, MS_SCOPES
from .provider import TimeSlot, CalendarError, graph_instant

class OutlookCalendar:
    def __init__(self,store,row,data): self.store,self.row,self.data=store,row,data

    def token(self):
        cache=msal.SerializableTokenCache();cache.deserialize(self.data['cache'])
        app=microsoft_app(cache);accounts=app.get_accounts()
        result=app.acquire_token_silent(MS_SCOPES,account=accounts[0]) if accounts else None
        if not result or 'access_token' not in result: raise CalendarError('calendar_reconnect_required')
        self.data={'cache':cache.serialize()};self.store.update_credentials(self.row,self.data)
        return result['access_token']

    def request(self,method,path,**kwargs):
        url=path if path.startswith('https://') else 'https://graph.microsoft.com/v1.0'+path
        p=urlsplit(url)
        if p.scheme!='https' or p.hostname!='graph.microsoft.com' or p.port not in (None,443) or p.username or not p.path.startswith('/v1.0/'):
            raise CalendarError('calendar_pagination_refused')
        try:
            with httpx.Client(timeout=20,follow_redirects=False) as client:
                response=client.request(method,url,headers={'Authorization':'Bearer '+self.token(),'Prefer':'outlook.timezone="UTC"'},**kwargs)
            if method=='DELETE' and response.status_code==404:return {}
            if response.status_code>=400: raise CalendarError('calendar_provider_'+str(response.status_code))
            return response.json() if response.content else {}
        except CalendarError: raise
        except Exception: raise CalendarError('calendar_provider_unavailable') from None

    def get_busy_slots(self,start,end):
        # calendarView supports Outlook personal accounts; getSchedule does not.
        params={'startDateTime':start.isoformat(),'endDateTime':end.isoformat(),'$top':100,
                '$select':'start,end,showAs,isCancelled'}
        path='/me/calendarView';slots=[]
        for _ in range(10):
            data=self.request('GET',path,params=params)
            if not isinstance(data.get('value'),list):raise CalendarError('calendar_response_invalid')
            for event in data['value']:
                if not event.get('isCancelled') and event.get('showAs')!='free':
                    slots.append(TimeSlot(start=graph_instant(event['start']),end=graph_instant(event['end'])))
            path=data.get('@odata.nextLink')
            if not path:return slots
            params=None
        raise CalendarError('calendar_pagination_limit')

    @staticmethod
    def body(event):
        return {'subject':event.title,'body':{'contentType':'text','content':event.description},
                'location':{'displayName':event.location},'showAs':'busy',
                'start':{'dateTime':event.start.isoformat(),'timeZone':'UTC'},
                'end':{'dateTime':event.end.isoformat(),'timeZone':'UTC'}}

    def create_event(self,event,key):
        data=self.request('POST','/me/events',json={**self.body(event),'transactionId':str(uuid5(NAMESPACE_URL,key))})
        if not data.get('id'):raise CalendarError('calendar_write_failed')
        return data['id']

    def update_event(self,event_id,event):
        self.request('PATCH','/me/events/'+quote(event_id,safe=''),json=self.body(event));return True

    def delete_event(self,event_id):
        self.request('DELETE','/me/events/'+quote(event_id,safe=''));return True

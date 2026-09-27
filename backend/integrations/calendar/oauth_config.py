"""Shared OAuth client configuration; no dependency on provider implementations."""
import os
import re
from urllib.parse import urlsplit
from google_auth_oauthlib.flow import Flow
import msal
import requests
from .provider import CalendarError

GOOGLE_SCOPES=['https://www.googleapis.com/auth/calendar']
MS_SCOPES=['Calendars.ReadWrite']

class BoundedHTTP:
    def __init__(self): self.session=requests.Session()
    def get(self,url,**kwargs): return self.session.get(url,timeout=15,**{k:v for k,v in kwargs.items() if k!='timeout'})
    def post(self,url,**kwargs): return self.session.post(url,timeout=15,**{k:v for k,v in kwargs.items() if k!='timeout'})

def callback_uri(provider):
    root=os.getenv('CALENDAR_REDIRECT_BASE','http://localhost:8000').rstrip('/')
    p=urlsplit(root)
    if p.username or p.password or p.query or p.fragment or p.path or not p.hostname:
        raise CalendarError('calendar_redirect_invalid')
    if p.scheme!='https' and not (p.scheme=='http' and p.hostname in ('localhost','127.0.0.1')):
        raise CalendarError('calendar_https_required')
    return root+'/api/calendar/callback/'+provider

def google_flow(state=None, verifier=None):
    config={'web':{'client_id':os.getenv('GOOGLE_CLIENT_ID',''),
        'client_secret':os.getenv('GOOGLE_CLIENT_SECRET',''),
        'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token'}}
    return Flow.from_client_config(config,scopes=GOOGLE_SCOPES,state=state,
        redirect_uri=callback_uri('google'),code_verifier=verifier,autogenerate_code_verifier=verifier is None)

def microsoft_app(cache=None):
    tenant=os.getenv('MICROSOFT_TENANT_ID','common')
    if not re.fullmatch(r'[a-zA-Z0-9.-]+',tenant): raise CalendarError('calendar_tenant_invalid')
    return msal.ConfidentialClientApplication(os.getenv('MICROSOFT_CLIENT_ID',''),
        authority='https://login.microsoftonline.com/'+tenant,
        client_credential=os.getenv('MICROSOFT_CLIENT_SECRET',''),token_cache=cache,http_client=BoundedHTTP())


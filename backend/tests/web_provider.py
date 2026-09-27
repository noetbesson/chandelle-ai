"""On-demand HTTP provider double for regressions. Never imported by application code."""
import json
from datetime import datetime,timedelta
from types import SimpleNamespace
from backend.integrations.openai import OpenAIAdapter,ParsedRequest
from backend.streams.C_discovery.web import WebDiscovery
from backend.streams.H_conversation.service import parse_request

class Provider:
    def __init__(self):self.responses=self;self.calls=[];self.override=None
    def create(self,**kwargs):
        self.calls.append(kwargs)
        payload=json.loads(kwargs['input']);window=payload['plan']['time_window']
        start=datetime.fromisoformat(window['start']);base=start.replace(hour=19,minute=0,second=0,microsecond=0)
        choices=[('food',0,20,['japanese','quiet','vegetarian']),('food',0,22,['japanese','quiet','vegan']),('food',0,18,['italian','quiet']),('outdoors',120,0,['walking','nature','romantic']),('outdoors',120,0,['walking','nature']),('outdoors',120,0,['walking','quiet']),('culture',0,10,['art','quiet']),('culture',120,12,['art','creative']),('concerts',90,15,['jazz','music','loud']),('concerts',90,17,['jazz','music','quiet'])]
        activities=[]
        for i,(category,offset,price,tags) in enumerate(choices):
            stamp=base+timedelta(minutes=offset)
            activities.append({'name':f'Provider test {i}','category':category,'kind':'place','source_url':f'https://www.paris.fr/pages/provider-test-{i}', 'description':'Provider simulation used only by tests.','address':'Paris','department':'75','location':{'lat':48.8566,'lng':2.3522},'tags':tags,'price':price,'price_unit':'person','start':stamp.isoformat(),'end':(stamp+timedelta(minutes=60)).isoformat(),'schedule_status':'proposed','availability':'unknown','evidence':'Test contract.'})
        if self.override is not None:activities=self.override(activities) if callable(self.override) else self.override
        data={'status':'completed','output':[{'type':'web_search_call','status':'completed','action':{'sources':[{'url':a['source_url']} for a in activities]}},{'type':'message','content':[{'type':'output_text','text':json.dumps({'activities':activities,'note':''}),'annotations':[]}]}]}
        return SimpleNamespace(model_dump=lambda:data,usage=SimpleNamespace(model_dump=lambda:{}))

def install(app,monkeypatch):
    monkeypatch.setenv('OPENAI_ENABLED','1');monkeypatch.setenv('OPENAI_WEB_ENABLED','1')
    monkeypatch.setenv('OPENAI_DAILY_RESERVE_USD','10');monkeypatch.setenv('OPENAI_TOTAL_RESERVE_USD','40')
    def parse(self,text):
        self.last_mode='openai';self.last_fallback=None
        return ParsedRequest(**parse_request(text))
    monkeypatch.setattr(OpenAIAdapter,'parse',parse)
    original_call=OpenAIAdapter._call
    def guarded(self,*args,**kwargs):
        if not self._injected:
            self.last_mode='offline';self.last_fallback='test_provider_not_injected';return args[2]
        return original_call(self,*args,**kwargs)
    monkeypatch.setattr(OpenAIAdapter,'_call',guarded)
    state=app.state.v2;provider=Provider();state['planning'].web=WebDiscovery(state['db'],state['memory'],provider)
    app.state.web_provider=provider
    return provider

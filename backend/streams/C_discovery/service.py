"""Persist web-sourced public facts, apply auditable filters and rank through B.

This store is a cache, never an alternative source or an offline fallback.
"""
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from backend.integrations.urls import public_url
from backend.streams.E_orchestrator.models import TimeWindow

PARIS=ZoneInfo('Europe/Paris')
CATEGORIES={'restaurant':'food','restaurants':'food','balade':'outdoors','walk':'outdoors','concert':'concerts','expo':'culture','exposition':'culture','bar':'nightlife','voyage':'travel','atelier':'workshops','film':'cinema'}
IDF={'75','77','78','91','92','93','94','95'}

def _now():return datetime.now(timezone.utc).isoformat()
def _normal(value):
    from backend.streams.H_conversation.service import normalize
    return re.sub(r'[^\w]+',' ',normalize(str(value))).strip()
def _matches(terms,value):
    value={'loud spaces':'loud','crowds':'social'}.get(str(value).casefold(),value)
    return bool(_normal(value)) and f' {_normal(value)} ' in f' {terms} '
def _list(value):return value if isinstance(value,list) else [value] if isinstance(value,str) else []
def _distance(a,b):
    lat1,lat2=map(math.radians,(a['lat'],b['lat']))
    h=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(math.radians(b['lng']-a['lng'])/2)**2
    return 6371*2*math.asin(min(1,math.sqrt(h)))
def canonical_categories(values):return list(dict.fromkeys(CATEGORIES.get(_normal(v),_normal(v)) for v in values))
def department_code(value,address=''):
    names={'paris':'75','seine et marne':'77','yvelines':'78','essonne':'91','hauts de seine':'92','seine saint denis':'93','val de marne':'94','val d oise':'95'}
    normalized=_normal(value or '')
    if normalized in IDF:return normalized
    if normalized in names:return names[normalized]
    postal=re.search(r'\b(75|77|78|91|92|93|94|95)\d{3}\b',address)
    if postal:return postal[1]
    return None

def stamp(value):return datetime.fromisoformat(value.replace('Z','+00:00')) if value else None

def record_web(value,checked):
    from backend.streams.H_conversation.service import interests
    a=dict(value);start=stamp(a.get('start'));end=stamp(a.get('end'))
    price=a.get('price');unit=a.get('price_unit','unknown')
    price_per_person=price/2 if price is not None and unit=='couple' else price if unit in ('person','free') else None
    tags=list(dict.fromkeys(a.get('tags',[])+interests(' '.join([a['name'],*a.get('tags',[])]))[0]))
    ident='web_'+hashlib.sha256((a['source_url']+'|'+_normal(a['name'])+'|'+(a.get('start') or '' if a['kind'] in ('event','screening','bookable_slot') else '')).encode()).hexdigest()[:24]
    return {**a,'id':ident,'title':a['name'],'category':CATEGORIES.get(a['category'],a['category']),
            'department':department_code(a.get('department'),a.get('address') or ''),'tags':tags,'price_per_person':price_per_person,'currency':'EUR',
            'start':start.astimezone(PARIS).strftime('%H:%M') if start else None,
            'end':end.astimezone(PARIS).strftime('%H:%M') if end else None,
            'starts_at':a.get('start'),'ends_at':a.get('end'),
            'duration_minutes':round((end-start).total_seconds()/60) if start and end else None,
            'booking_url':None,'source':a['source_url'],'demo':False,'provider':'openai_web',
            'last_verified_at':checked,'checked_at':checked,'address':a.get('address') or '',
            'rating':None,'media':[],'popularity':None,'accessibility':{},'weather_sensitive':a['category']=='outdoors'}

class CatalogService:
    def __init__(self,db,memory):self.db,self.memory=db,memory

    def remove_synthetic(self):
        """Narrow migration: remove only explicitly synthetic cache records, not user memory/history."""
        with self.db.connect() as c:
            ids=[r['id'] for r in c.execute('SELECT id,payload FROM v2_activities') if json.loads(r['payload']).get('demo') is True]
            c.executemany('DELETE FROM v2_activity_states WHERE activity_id=?',[(i,) for i in ids])
            c.executemany('DELETE FROM v2_activities WHERE id=?',[(i,) for i in ids])
            old=[r['id'] for r in c.execute('SELECT id,payload FROM v2_suggestions') if any(a.get('demo') for a in json.loads(r['payload']).get('plan',{}).get('activities',[]))]
            c.executemany("UPDATE v2_suggestions SET state='expired' WHERE id=?",[(i,) for i in old])
        return len(ids)

    def persist(self,rows):
        with self.db.connect() as c:
            c.executemany('INSERT INTO v2_activities VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',[(a['id'],json.dumps(a,ensure_ascii=False)) for a in rows])

    def browse(self,query='',category=None,limit=30,offset=0):
        if not 1<=limit<=100 or offset<0:raise ValueError('Invalid pagination')
        # Compatibility endpoint: no independent discovery and no catalogue fallback.
        return {'items':[],'total':0,'limit':limit,'offset':offset,'message':'Lancez une recherche dans Ask ou Discover.'}

    def get(self, activity_id):
        with self.db.connect() as con:
            row = con.execute('SELECT payload FROM v2_activities WHERE id=?', (activity_id,)).fetchone()
        if not row:
            raise KeyError(activity_id)
        return json.loads(row['payload'])

    def set_state(self, user_id, activity_id, state):
        if state not in {'saved', 'liked', 'disliked', 'rejected', 'neutral'}:
            raise ValueError('Unknown activity state')
        self.get(activity_id)
        with self.db.connect() as con:
            con.execute('INSERT INTO v2_activity_states(user_id,activity_id,state,updated_at) VALUES (?,?,?,?) '
                        'ON CONFLICT(user_id,activity_id) DO UPDATE SET state=excluded.state,updated_at=excluded.updated_at',
                        (user_id, activity_id, state, _now()))
        return {'activity_id': activity_id, 'state': state}

    def record_state(self,couple_id,user_id,aid,state):
        result=self.set_state(user_id,aid,state)
        activity=self.get(aid)
        previous=[f for f in self.memory.list_facts(couple_id,'PERSON',user_id,user_id) if f['key']=='activity:'+aid]
        if state in ('liked','saved','disliked','rejected'):
            self.memory.ingest(couple_id,'PERSON',user_id,user_id,'dislikes' if state in ('disliked','rejected') else 'interests','activity:'+aid,{'values':[activity['category']]},'COUPLE_RECOMMENDATION','activity_feedback',supersedes=previous[0]['id'] if previous else None)
            for old in previous[1:]:self.memory.delete(old['id'],user_id)
        else:
            for old in previous:self.memory.delete(old['id'],user_id)
        return result

    def filter_web(self,cid,records,window=None,budget=None,categories=None,radius_km=None,excluded=(),requested_tags=None,trace=None):
        from backend.streams.H_conversation.service import interests
        trace=trace if trace is not None else []
        context=self.memory.planning_context(cid)
        profiles=[context.get(k,{}) for k in ('person_a','person_b','couple')]
        caps=[budget] if budget is not None else []
        for p in profiles:
            v=p.get('budget')
            if isinstance(v,(int,float)):caps.append(v)
            elif isinstance(v,dict) and not v.get('flexible') and v.get('max') is not None:caps.append(v['max']*(2 if v.get('unit')=='person' else 1))
        cap=min(caps) if caps else None
        origin=profiles[2].get('location')
        categories=canonical_categories(categories or [])
        with self.db.connect() as c:
            states={r[0] for r in c.execute("SELECT activity_id FROM v2_activity_states WHERE user_id IN (SELECT user_id FROM v2_memberships WHERE couple_id=?) AND state IN ('disliked','rejected')",(cid,))}
        rows=list(records)
        def step(name,check):
            nonlocal rows
            before=len(rows);unknown=0;accepted=[]
            for a in rows:
                decision=check(a)
                if decision is None:unknown+=1
                if decision is not False:accepted.append(a)
            rows=accepted;trace.append({'stage':name,'before':before,'after':len(rows),'removed':before-len(rows),'unknown':unknown})
        step('provenance',lambda a:a.get('provider')=='openai_web' and not a.get('demo') and bool(public_url(a.get('source_url',''))))
        step('region_idf',lambda a:a.get('department') in IDF)
        step('expiration',lambda a: not (a.get('kind') in ('event','screening','bookable_slot') and stamp(a.get('ends_at') or a.get('starts_at')) and stamp(a.get('ends_at') or a.get('starts_at'))<datetime.now(timezone.utc)))
        step('category',lambda a:not categories or a['category'] in categories)
        step('budget',lambda a:None if a['price_per_person'] is None else cap is None or a['price_per_person']*2<=cap)
        step('radius',lambda a:None if not origin or not a.get('location') else radius_km is None or _distance(a['location'],origin)<=radius_km)
        step('availability',lambda a:a.get('availability')!='unavailable')
        def time_ok(a):
            if window is None:return True
            start,end=stamp(a.get('starts_at')),stamp(a.get('ends_at'))
            if not start or not end:return None
            return start>=window.start and end<=window.end
        step('time_window',time_ok)
        def preferences(a):
            terms=_normal(' '.join([a['title'],a['category'],*a['tags']]))
            if a['id'] in states or any(_matches(terms,t) for t in excluded):return False
            for p in profiles:
                if any(_matches(terms,t) for t in _list(p.get('dislikes'))):return False
            return True
        step('explicit_exclusions',preferences)
        def constraint_values(key):
            return [p.get('constraints',{}).get(key) for p in profiles if isinstance(p.get('constraints'),dict) and p['constraints'].get(key) is not None]
        def days_ok(a):
            start=stamp(a.get('starts_at'))
            if not start:return None
            index=start.astimezone(PARIS).weekday();names=['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
            return all(not values or index in values or names[index] in [str(v).lower() for v in values] for values in constraint_values('days'))
        step('preferred_days',days_ok)
        step('accessibility',lambda a:all(a.get('accessibility',{}).get(v,False) for values in constraint_values('accessibility') for v in _list(values)))
        step('dietary',lambda a:a['category'] not in ('food','home') or all(_matches(_normal(' '.join([a['title'],a['category'],*a['tags']])),v) for values in constraint_values('dietary') for v in _list(values)))
        step('mobility_time',lambda a:None if not origin or not a.get('location') else all(_distance(a['location'],origin)/4*60<=float(v) for v in constraint_values('travel_minutes')))
        step('requested_tags',lambda a:all(_matches(_normal(' '.join([a['title'],*a['tags']])),tag) for tag in (requested_tags or {}).get(a['category'],[])))
        unique={a['id']:a for a in rows};trace.append({'stage':'deduplication','before':len(rows),'after':len(unique),'removed':len(rows)-len(unique),'unknown':0})
        with self.db.connect() as c:
            history=[json.loads(r[0]) for r in c.execute("SELECT payload FROM v2_plans WHERE couple_id=? AND status='completed'",(cid,))]
        seen={a['id'] for p in history for a in p.get('activities',[])}
        ranked=[]
        for a in unique.values():
            terms=_normal(' '.join([a['title'],a['category'],*a['tags']]))
            scores=[min(.95,.45+.2*sum(p.get('interest_weights',{}).get(v,1)*_matches(terms,v) for v in _list(p.get('interests')))) for p in profiles[:2]]
            shared=.05 if any(_matches(terms,v) for v in _list(profiles[2].get('interests'))) else 0
            distance=_distance(a['location'],origin) if a.get('location') and origin else None
            novelty=.2*float(profiles[2].get('novelty',.5) or 0) if a['id'] in seen else 0
            score=max(0,min(1,.6*min(scores)+.2*sum(scores)+shared-novelty))
            candidate=None
            if all(a.get(k) is not None for k in ('price_per_person','location','start','end','duration_minutes')) and window and time_ok(a):
                candidate={'id':a['id'],'type':a['category'],'name':a['title'],'start':a['start'],'end':a['end'], 'price_per_person':a['price_per_person'],'location':a['location'],'tags':a['tags'],'booking_url':a.get('source_url'),'match_score':score,'user_a_score':scores[0],'user_b_score':scores[1]}
            ranked.append({'activity':a,'candidate':candidate,'person_a_score':scores[0],'person_b_score':scores[1],'couple_score':score,
                'components':{'fairness':score,'shared_bonus':shared,'query_bonus':0,'novelty_penalty':novelty,'distance_penalty':0,'distance_km':distance or 0,'diversity_penalty':0},
                'evidence':['Source : '+a['source_url'],'Disponibilité à confirmer.']})
        ranked.sort(key=lambda r:(-r['couple_score'],r['activity']['id']))
        return ranked,cap

    def discover(self,couple_id,time_window,budget=None,categories=None,radius_km=None,limit=30,query='',candidate_ids=None):
        # Only revalidation of a saved web search. Never scan or seed an offline catalogue.
        if not candidate_ids:return []
        with self.db.connect() as c:
            rows=[json.loads(r[0]) for aid in candidate_ids for r in c.execute('SELECT payload FROM v2_activities WHERE id=?',(aid,))]
        window=TimeWindow.model_validate(time_window) if isinstance(time_window,dict) else time_window
        from backend.streams.A_calendar.service import paris_window
        window=paris_window(window)
        ranked,_=self.filter_web(couple_id,rows,window,budget,categories,radius_km)
        return [r for r in ranked if r['candidate'] is not None][:limit]

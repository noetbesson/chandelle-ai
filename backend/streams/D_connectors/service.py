"""Inert, bounded imports adapted from peer signals.ts. No URL is fetched."""
import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field
from backend.integrations.urls import public_url
from backend.streams.H_conversation.service import normalize, interests
from backend.streams.B_memory.service import Privacy


class SignalImport(BaseModel):
    platform: Literal['manual','google_maps','instagram','tiktok']='manual'
    format: Literal['text','json','csv']='text'
    content: str=Field(min_length=1,max_length=1_000_000)
    privacy_scope: Privacy='PRIVATE'
    signal_at: str | None=Field(default=None,max_length=100)
    horizon: Literal['durable','temporary']='durable'


class SignalConfirm(BaseModel):
    tags: list[str]=Field(max_length=20)
    privacy_scope: Privacy='PRIVATE'
    horizon: Literal['durable','temporary']='durable'


def signal_date(value):
    if value is None or value=='':return None
    try:
        if isinstance(value,(int,float)) or str(value).isdigit():
            n=float(value)
            return datetime.fromtimestamp(n/1000 if n>1e12 else n,timezone.utc).isoformat()
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        # An unzoned export establishes a day, not an exact instant.
        if d.tzinfo is None:d=d.replace(hour=0,minute=0,second=0,microsecond=0,tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).isoformat()
    except (ValueError,OverflowError,OSError):return None


def parse_import(body):
    if len(body.content.encode())>1_000_000:raise ValueError('Import limité à 1 Mo.')
    rows=[]
    if body.format=='text':rows=[{'text':body.content,'date':body.signal_at}]
    elif body.format=='csv':
        if body.platform!='google_maps':raise ValueError('CSV réservé aux exports Google Maps.')
        first=body.content.splitlines()[0]
        reader=csv.DictReader(io.StringIO(body.content.lstrip('\ufeff')),delimiter=';' if first.count(';')>first.count(',') else ',',strict=True)
        fields={normalize(k):k for k in reader.fieldnames or []}
        title=next((fields[k] for k in ('title','nom','name','titre') if k in fields),None)
        url=next((fields[k] for k in ('url','lien','google maps url') if k in fields),None)
        if not title or not url:raise ValueError('CSV attendu : Title/Nom, URL, éventuellement Note et Date.')
        try:
            for row in reader:
                row={normalize(k):v for k,v in row.items() if isinstance(k,str)}
                rows.append({'text':str(row.get(normalize(title)) or '')+' '+str(row.get('note') or row.get('description') or ''),'url':row.get(normalize(url)),'date':row.get('date')})
        except csv.Error as exc:raise ValueError('CSV invalide.') from exc
    else:
        try:data=json.loads(body.content)
        except (ValueError,RecursionError) as exc:raise ValueError('JSON invalide.') from exc
        if body.platform=='google_maps' and isinstance(data,dict) and data.get('type')=='FeatureCollection':
            for f in data.get('features',[]):
                if not isinstance(f,dict):continue
                p=f.get('properties') or {}
                if not isinstance(p,dict):continue
                loc=p.get('Location') or {}
                loc=loc if isinstance(loc,dict) else {}
                rows.append({'text':' '.join(str(x) for x in (loc.get('Business Name') or p.get('name') or p.get('Title') or '',p.get('Comment') or p.get('description') or '')),'url':p.get('Google Maps URL') or p.get('url'),'date':p.get('Published')})
        elif body.platform=='instagram':
            collections=[data] if isinstance(data,list) else [v for k,v in data.items() if k in ('saved_saved_media','saved_media','likes_media_likes','liked_posts','saved_posts') and isinstance(v,list)] if isinstance(data,dict) else []
            if not collections:raise ValueError('Export Instagram Saved/Likes attendu.')
            for collection in collections:
                for row in collection:
                    if not isinstance(row,dict):continue
                    values=row.get('string_list_data')
                    if not isinstance(values,list):
                        mapping=row.get('string_map_data')
                        values=list(mapping.values()) if isinstance(mapping,dict) else []
                    for v in values:
                        if isinstance(v,dict) and v.get('href'):
                            rows.append({'text':row.get('caption') or row.get('description') or '', 'url':v['href'],'date':v.get('timestamp')})
        elif body.platform=='tiktok':
            recognized=False
            def visit(value,depth=0,allowed=False):
                nonlocal recognized
                if depth>7:return
                if isinstance(value,list):
                    for row in value:
                        if isinstance(row,dict) and allowed:
                            url=row.get('Link') or row.get('VideoLink') or row.get('Video Landing Page Link')
                            if url:rows.append({'text':row.get('Title') or row.get('Description') or '', 'url':url,'date':row.get('Date')})
                        visit(row,depth+1,allowed)
                elif isinstance(value,dict):
                    for k,v in value.items():
                        key=''.join(c for c in normalize(k) if c.isalpha())
                        approved=key in ('likelist','likedvideos','favoritevideos','favouritevideos','sharehistory')
                        if approved:recognized=True
                        if approved or key in ('activity','youractivity','useractivity','videolist','list','itemfavoritelist','itemlikelist'):
                            visit(v,depth+1,allowed or approved)
            visit(data)
            if not recognized:raise ValueError('Export TikTok Likes/Favorites/Share History attendu.')
        else:raise ValueError('Format ou structure d’export non pris en charge.')
    import re
    entries=[];seen=set();duplicates=0;warnings=set()
    for row in rows:
        if len(str(row.get('text') or ''))>8000:
            warnings.add('Un texte a été limité à 8 000 caractères ; vérifiez les goûts proposés.')
        text=str(row.get('text') or '')[:8000].strip()
        raw=row.get('url') or next(iter(re.findall(r'https?://[^\s<>"\']+',text)),None)
        url=public_url(raw) if isinstance(raw,str) else None
        plain=re.sub(r'https?://\S+','',text).strip()
        if not plain and not url:continue
        fingerprint=hashlib.sha256((body.platform+'\n'+(url or normalize(plain))).encode()).hexdigest()
        if fingerprint in seen:duplicates+=1;continue
        seen.add(fingerprint)
        if len(entries)>=200:continue
        stamp=signal_date(row.get('date'))
        if not stamp:warnings.add('Date du signal inconnue ; la date d’import ne la remplace pas.')
        if not plain:warnings.add('Lien sans contenu : aucune page ni transcription récupérée, aucun goût déduit.')
        tags,_=interests(plain)
        entries.append({'fingerprint':fingerprint,'platform':body.platform,'text':text,'source_url':url,
                        'signal_at':stamp,'signal_date_raw':str(row.get('date')) if row.get('date') is not None else None,
                        'proposed_tags':tags,'confirmed':False,'horizon':body.horizon})
    return {'entries':entries,'duplicates':duplicates,'warnings':sorted(warnings),'truncated':len(seen)>200}


class InspirationService:
    def __init__(self,memory):self.memory=memory

    def list(self,cid,uid):
        return {'items':[f for f in self.memory.list_facts(cid,'PERSON',uid,uid) if f['source']=='inspiration_import']}

    def ingest(self,cid,uid,body):
        from backend.db import now
        parsed=parse_import(body)
        existing={f['key']:f for f in self.list(cid,uid)['items']}
        results=[]
        for entry in parsed.pop('entries'):
            key='signal:'+entry['fingerprint']
            if key in existing:
                results.append(existing[key]);parsed['duplicates']+=1;continue
            entry['imported_at']=now()
            fact=self.memory.ingest(cid,'PERSON',uid,uid,'inspiration',key,entry,body.privacy_scope,'inspiration_import')
            existing[key]=fact;results.append(fact)
        return {**parsed,'items':results}

    def confirm(self,mid,uid,body):
        from datetime import timedelta
        fact=self.memory._owned(mid,uid)
        if fact['source']!='inspiration_import':raise ValueError('Cette mémoire n’est pas une inspiration importée.')
        tags=sorted(set(normalize(t).strip() for t in body.tags))
        if any(not t or len(t)>100 for t in tags):raise ValueError('Goût invalide.')
        value={**fact['value'],'values':tags,'confirmed':True,'horizon':body.horizon}
        stamp=signal_date(value.get('signal_at'))
        value['expires_at']=(datetime.fromisoformat(stamp)+timedelta(days=45)).isoformat() if stamp and body.horizon=='temporary' else None
        return self.memory.update(mid,uid,category='interests',value=value,privacy_scope=body.privacy_scope,confidence=1)

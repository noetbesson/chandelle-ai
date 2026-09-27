"""Public activity projections and saved search snapshots; no private profile fields."""
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from backend.integrations.urls import public_url


def catalogue_image(activity):
    values=[activity.get('image_url'),*activity.get('media',[])]
    for value in values:
        raw=value.get('url') if isinstance(value,dict) else value
        url=public_url(raw) if isinstance(raw,str) else None
        if url and url.startswith('https://'):return url
    return None


def activity_choices(rows,window,plan_ids=()):
    counts=Counter();result=[]
    # Preserve alternatives by category, including every activity in proposed plans.
    ordered=sorted(rows,key=lambda r:(r['activity']['id'] not in plan_ids,-r['couple_score'],r['activity']['id']))
    for row in ordered:
        a,c=row['activity'],row['candidate'];category=a['category']
        if counts[category]>=5 and a['id'] not in plan_ids:continue
        counts[category]+=1
        zone=window.start.tzinfo or ZoneInfo('Europe/Paris')
        start=datetime.combine(window.start.date(),datetime.strptime(c['start'],'%H:%M').time(),zone)
        if start<window.start.replace(tzinfo=zone):start+=timedelta(days=1)
        end=start+timedelta(minutes=a['duration_minutes'])
        why=('Correspond à des goûts partagés autorisés.' if row['components'].get('shared_bonus',0)>0
             else 'Classée selon les préférences autorisées de votre couple.')
        why+=f" {a['price_per_person']*2:g} € à deux, dans le créneau demandé."
        # No stock photography, rating inferred from popularity, or device position claimed.
        result.append({'id':a['id'],'name':a['title'],'category':category,'start':start.isoformat(),'end':end.isoformat(),
            'price_per_person':a['price_per_person'],'location':a['location'],'address':a.get('address',''),
            'tags':a.get('tags',[]),'why':why,'demo':bool(a.get('demo')), 'image_url':catalogue_image(a),
            'rating':a.get('rating'),'source':a.get('source','Source inconnue')})
        if len(result)>=50:break
    return result


def search_snapshot(rows,window,budget,rid,options,created_at,radius):
    return {'time_window':window.model_dump(mode='json'),'budget_cap':budget,'generated_at':created_at,
        '_deck':{'pool':rows,'search_id':rid,'owner_id':options['owner_id'],'created_at':created_at,
                 'duration':options['duration'],'travel':options['travel'],'radius_km':radius}}


def web_activity_choices(rows):
    result=[]
    for r in rows[:50]:
        a=r['activity']
        result.append({'id':a['id'],'name':a['title'],'category':a['category'],
            'start':a.get('starts_at'),'end':a.get('ends_at'),'price_per_person':a.get('price_per_person'),
            'location':a.get('location'),'address':a['address'],'tags':a['tags'],
            'why':('Fiche importée, classée selon votre demande et les préférences autorisées. Détails à confirmer.' if a.get('provider')=='user_import' else 'Correspond à votre recherche, avec classement selon les préférences autorisées.'),
            'demo':False,'source':a['source_url'],'source_url':a['source_url'],'kind':a['kind'],
            'checked_at':a['checked_at'],'schedule_status':a['schedule_status'],
            'availability':a.get('availability','unknown'),'price_unit':a.get('price_unit','unknown'),
            'composable':r['candidate'] is not None,'image_url':None,'rating':a.get('rating'),
            'price_tier':a.get('price_tier'),'city':a.get('city'),'source_name':a.get('source_name'),
            'pint_price_from_eur':a.get('pint_price_from_eur'),'offer_note':a.get('offer_note'),
            'imported_at':a.get('imported_at'),'description':a.get('description',''),
            'source_kind':'import' if a.get('provider')=='user_import' else 'web'})
    return result

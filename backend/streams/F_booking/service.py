"""Calendar export and human booking preparation, adapted from peer domain.ts."""
from datetime import datetime, timedelta, timezone

from backend.streams.A_calendar.service import instant, PARIS
from backend.integrations.urls import public_url


def schedule(plan):
    """Expand E's local HH:MM into dated, ordered instants for export."""
    cursor=instant(plan['start'])
    for activity in plan['activities']:
        day=cursor.astimezone(PARIS).date()
        start=instant(datetime.fromisoformat(f"{day}T{activity['start']}"))
        if start<cursor:
            start=instant(datetime.fromisoformat(f"{day+timedelta(days=1)}T{activity['start']}"))
        end=instant(datetime.fromisoformat(f"{start.astimezone(PARIS).date()}T{activity['end']}"))
        if end<=start:end=instant(datetime.fromisoformat(f"{start.astimezone(PARIS).date()+timedelta(days=1)}T{activity['end']}"))
        yield activity,start,end
        cursor=end


def prepare(plan):
    if plan['status'] not in ('accepted','completed'):
        raise ValueError('Acceptez le programme avant de préparer les réservations.')
    actions=[]
    for activity,start,end in schedule(plan):
        url=public_url(activity.get('booking_url')) if not activity.get('demo',True) else None
        actions.append({'activity_id':activity['id'],'title':activity.get('title',activity['name']),
                        'start':start.isoformat(),'end':end.isoformat(),'participants':2,
                        'price_per_person':activity['price_per_person'],'booking_url':url,
                        'status':'provider_link' if url else 'manual_check_required',
                        'availability':'unverified','requires_user_confirmation':True,
                        'demo':activity.get('demo',True)})
    return {'date_plan_id':plan['id'],'actions':actions,'total_couple_cost':plan['total_couple_cost'],
            'requires_user_confirmation':True,'payment_performed':False,
            'message':'Vérifiez les horaires, les prix et la disponibilité auprès du lieu. Aucune réservation effectuée.'}


def calendar(plan):
    if plan['status'] not in ('accepted','completed'):
        raise ValueError('Acceptez le programme avant de l’exporter.')
    def escape(value):
        return str(value).replace('\\','\\\\').replace('\r\n','\n').replace('\r','\n').replace('\n','\\n').replace(';','\\;').replace(',','\\,')
    stamp=lambda d:d.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Chandelle//Local DatePlan//FR','CALSCALE:GREGORIAN','METHOD:PUBLISH']
    for a,start,end in schedule(plan):
        lines.extend(['BEGIN:VEVENT',f"UID:{plan['id']}-{a['id']}@chandelle.local",
                      'DTSTAMP:'+stamp(instant(plan['generated_at'])), 'DTSTART:'+stamp(start),'DTEND:'+stamp(end),
                      'SUMMARY:'+escape(a.get('title',a['name'])), 'LOCATION:'+escape(a.get('address','')),
                      'DESCRIPTION:'+escape('Chandelle — programme pour deux. Disponibilité à vérifier. Aucune réservation effectuée.'),
                      'STATUS:TENTATIVE','END:VEVENT'])
    lines.append('END:VCALENDAR')
    # RFC 5545 folding: <=75 octets, without splitting UTF-8 characters.
    folded=[]
    for line in lines:
        part=''
        for char in line:
            if len((part+char).encode())>75:
                folded.append(part);part=' '
            part+=char
        folded.append(part)
    return '\r\n'.join(folded)+'\r\n'

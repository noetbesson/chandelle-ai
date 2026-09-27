"""Private discovery sessions: language decisions, real retrieval, verified planning."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import json
import re
from uuid import uuid4
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field, model_validator
from backend.db import encoded
from backend.integrations.dialogue import DialogueAdapter, DialogueDecision, SearchIntent, GroundedReply, DialogueUnavailable
from backend.integrations.openai import ParsedRequest
from backend.streams.H_conversation.service import parse_request, interests, normalize
from backend.streams.C_discovery.web import WebQuery
from backend.streams.C_discovery.recommendations import DatabaseActivities
from backend.streams.C_discovery.service import CatalogService, record_web
from backend.streams.E_orchestrator.service import Query, PlanningIssue
from backend.streams.E_orchestrator.models import TimeWindow

PARIS = ZoneInfo('Europe/Paris')

class DialogueConflict(ValueError):
    pass

class ChatTurn(BaseModel):
    model_config = {"extra":"forbid"}
    message: str = Field(default='', max_length=1500)
    session_id: str | None = Field(default=None, min_length=1, max_length=100)
    request_id: str = Field(min_length=1, max_length=100)
    revision: int = Field(default=0, ge=0)
    recommend: bool = False
    cloud_consent: bool = False
    web_consent: bool = False

    @model_validator(mode='after')
    def consent(self):
        if self.web_consent and not self.cloud_consent:
            raise ValueError('Le web nécessite le consentement OpenAI.')
        return self


def spoken_budget(text):
    parsed = parse_request(text)['budget']
    if parsed is not None:
        return parsed
    # Common French spoken amounts; other language understanding belongs to the model.
    units = dict(zip(['zero','un','deux','trois','quatre','cinq','six','sept','huit','neuf','dix','onze','douze','treize','quatorze','quinze','seize'], range(17)))
    tens = {'vingt':20,'trente':30,'quarante':40,'cinquante':50,'soixante':60}
    s = normalize(text).replace('-', ' ')
    if re.search(r'\b(mille|million|virgule)\b',s):return None
    match = re.search(r'((?:(?:'+'|'.join([*units,*tens,'cent','vingts','cents','et'])+r')\s+)+)euros?\b', s)
    if not match:
        return None
    phrase = match[1].strip().replace('quatre vingts','80').replace('quatre vingt','80')
    total, group = 0, 0
    for word in phrase.split():
        if word == 'et': continue
        if word in ('cent','cents'): group = max(group,1)*100
        else: group += units.get(word,tens.get(word,80 if word=='80' else 0))
    total += group
    return total * (2 if re.search(r'par personne|chacun',s) else 1)


def local_decision(message, previous, last_result, recommend=False):
    """Honest offline fallback; never pretend to understand arbitrary language."""
    intent = previous.model_copy(deep=True)
    text = normalize(message)
    parsed = parse_request(message)
    likes, excluded = interests(message)
    correction = bool(re.search(r'plutot|finalement|en fait|remplace|oublie', text))
    if message:
        intent.summary = message[:800] if correction or not intent.summary else intent.summary
    if parsed['categories']:
        intent.categories = parsed['categories']
        if correction: intent.selected_ids = []
    if likes: intent.preferences = sorted(set(likes) | (set() if correction else set(intent.preferences)))[:15]
    if excluded:
        intent.excluded = sorted(set(intent.excluded) | set(excluded))[:15]
        intent.categories = [c for c in intent.categories if c not in excluded]
        intent.preferences = [c for c in intent.preferences if c not in excluded]
    amount = spoken_budget(message)
    if amount is None and (correction or not intent.budget):
        match = re.fullmatch(r'\s*(?:plutot\s+)?(\d+)\s*', text)
        if match: amount = float(match[1])
    if amount is not None: intent.budget = amount
    city = re.search(r'\b(paris|lyon|lille|marseille|nantes|bordeaux|toulouse|rennes|montpellier|strasbourg)\b', text)
    if city: intent.location = city[1].capitalize()
    if 'demain' in text or 'ce soir' in text or "aujourd'hui" in text:
        day=(datetime.now(PARIS)+timedelta(days=1 if 'demain' in text else 0)).date().isoformat()
        intent.date_from=intent.date_to=day
        intent.start=intent.end=None
    if re.search(r'autre|different|deja propose',text):
        intent.avoid_ids = list(dict.fromkeys([*intent.avoid_ids, *[a['id'] for a in last_result.get('suggestions',[])]]))[-30:]
        intent.selected_ids = []
    if re.search(r'pourquoi|explique|compare',text) and last_result.get('suggestions'):
        a = last_result['suggestions'][0]
        return DialogueDecision(intent=intent,action='reply',reply=f"Pour {a['name']} : {'. '.join(a['reasons'])}. Les informations à confirmer figurent sur la fiche.")
    if re.search(r'programme|planifie|organise|itineraire',text):
        return DialogueDecision(intent=intent,action='plan',reply='Je vérifie les activités et le créneau.')
    if not intent.location:
        return DialogueDecision(intent=intent,action='reply',reply='Dans quelle ville ou quel quartier voulez-vous sortir ? Vous pouvez me donner vos envies et votre budget dans la même phrase.')
    if not intent.categories and not intent.preferences and not recommend:
        return DialogueDecision(intent=intent,action='reply',reply=f'Quel genre de moment vous ferait plaisir à {intent.location} ? On peut aussi partir de votre budget ou de ce que vous préférez éviter.')
    return DialogueDecision(intent=intent,action='discover',reply='Je cherche des pistes réelles qui correspondent à votre envie.')


def validate_window(intent):
    if not intent.start and not intent.end:
        return None
    if not intent.start or not intent.end:
        raise PlanningIssue('time_incomplete', 'À quelle heure souhaitez-vous commencer et terminer ? Je peux proposer des idées avant de fixer le programme.')
    try:
        start, end = datetime.fromisoformat(intent.start), datetime.fromisoformat(intent.end)
        if start.tzinfo is None or end.tzinfo is None or not timedelta(0) < end-start <= timedelta(days=2):
            raise ValueError()
        if start < datetime.now(timezone.utc):
            raise PlanningIssue('time_in_past', 'Ce créneau est déjà passé. Quel prochain jour vous conviendrait ?')
        return TimeWindow(start=start,end=end)
    except PlanningIssue:
        raise
    except (ValueError, TypeError):
        raise PlanningIssue('invalid_time', 'Je n’ai pas de créneau précis et valide. Quel jour et quelles heures vous conviendraient, en heure de Paris ?') from None


def budget_check(result):
    items = result.get('suggestions',[])
    return {'total_budget_for_two':result.get('intent',{}).get('budget'),
        'known_price_count':sum(a.get('total_couple_cost') is not None for a in items),
        'unknown_price_names':[a['name'] for a in items if a.get('total_couple_cost') is None]}


def public_result(result):
    # Bounded grounding for the model. No raw memory or implementation snapshots.
    safe={k:result[k] for k in ('suggestions','plans','diagnostic','reply') if k in result}
    safe['budget_check']=budget_check(result)
    if result.get('web',{}).get('status')=='completed':
        retained = {a.get('website') for a in result.get('suggestions',[])}
        safe['web']={'answer':result['web']['answer'][:5000],
                     'sources':[s for s in result['web']['sources'] if s['url'] in retained][:5],
                     'verification':'Pistes web ; compatibilité et disponibilité non validées par le planificateur.'}
    return safe


def grounding(result):
    """Only public activity facts reach the answer model, never profile scores/evidence."""
    fields = ('id','name','title','description','category','location','website','source',
              'price_per_person','total_couple_cost','price_level','rating','tags','start','end','unknown')
    activities = list(result.get('suggestions', []))
    activities += [a for plan in result.get('plans', []) for a in plan.get('activities', [])]
    safe = {'activities': [{k: a[k] for k in fields if k in a} for a in activities[:9]],
            'diagnostic': result.get('diagnostic'), 'fallback_reply': result['reply'],
            'budget_check':budget_check(result)}
    if result.get('web', {}).get('status') == 'completed':
        safe['web'] = public_result(result)['web']
    return safe


class DiscoveryDialogue:
    def __init__(self, db, planning, real, web, adapter_factory=DialogueAdapter):
        self.db, self.planning, self.real, self.web = db, planning, real, web
        self.adapter_factory = adapter_factory

    def close(self, member, sid):
        with self.db.connect() as c:
            row = c.execute('SELECT owner_id FROM v2_discovery_sessions WHERE id=?',(sid,)).fetchone()
            if row and row['owner_id'] != member['id']: raise PermissionError('Échange privé inconnu')
            c.execute('DELETE FROM v2_discovery_sessions WHERE id=? AND owner_id=?',(sid,member['id']))
        return {'closed':True}

    def _acquire(self, member, body):
        stamp = datetime.now(timezone.utc)
        fingerprint = sha256(encoded(body.model_dump(exclude={'revision','session_id'})).encode()).hexdigest()
        with self.db.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('DELETE FROM v2_discovery_sessions WHERE expires_at<?',(stamp.isoformat(),))
            sid = body.session_id
            if sid is None:
                # Retrying the initial request cannot create a second paid conversation.
                row = c.execute('SELECT id FROM v2_discovery_sessions WHERE owner_id=? AND initial_request_id=?',(member['id'],body.request_id)).fetchone()
                sid = row['id'] if row else uuid4().hex
                if not row:
                    count = c.execute('SELECT count(*) FROM v2_discovery_sessions WHERE owner_id=?',(member['id'],)).fetchone()[0]
                    if count >= 10: raise DialogueConflict('Trop d’échanges ouverts. Fermez un échange ou réessayez après expiration.')
                    c.execute('INSERT INTO v2_discovery_sessions VALUES(?,?,?,?,?,?,?,?,?)',
                        (sid,member['id'],member['couple_id'],body.request_id,0,None,(stamp+timedelta(hours=2)).isoformat(),stamp.isoformat(),encoded({'intent':{},'history':[]})))
            row = c.execute('SELECT * FROM v2_discovery_sessions WHERE id=? AND owner_id=? AND couple_id=?',(sid,member['id'],member['couple_id'])).fetchone()
            if not row: raise PermissionError('Échange expiré ou privé. Recommencez depuis votre profil.')
            payload = json.loads(row['payload'])
            if payload.get('request_id') == body.request_id:
                if payload.get('fingerprint') != fingerprint: raise DialogueConflict('Cet identifiant de message a déjà été utilisé pour un autre contenu.')
                return sid, payload, payload['response'], fingerprint
            if row['in_flight']:
                # Never auto-retry an ambiguous paid request after a worker crash.
                raise DialogueConflict('Un message est déjà en cours. Attendez sa réponse, ou recommencez cet échange s’il a été interrompu.')
            if body.revision != row['revision']:
                raise DialogueConflict('Cet échange a changé. Recommencez pour éviter de mélanger deux réponses.')
            c.execute('UPDATE v2_discovery_sessions SET in_flight=? WHERE id=?',(body.request_id,sid))
        return sid, payload, None, fingerprint

    def turn(self, member, body):
        sid, payload, replay, fingerprint = self._acquire(member,body)
        if replay is not None: return {**replay,'replayed':True}
        try:
            result, intent, history = self._run(member,body,payload,sid)
            result.update(session_id=sid,revision=body.revision+1,replayed=False)
            payload = {'intent':intent.model_dump(), 'history':history[-24:],
                'request_id':body.request_id,'fingerprint':fingerprint,'response':result}
            with self.db.connect() as c:
                # Closing/erasing while OpenAI works cannot resurrect the conversation.
                changed = c.execute('UPDATE v2_discovery_sessions SET revision=?,in_flight=NULL,payload=? WHERE id=? AND owner_id=? AND in_flight=?',
                    (result['revision'],encoded(payload),sid,member['id'],body.request_id)).rowcount
                if not changed: raise PermissionError('Cet échange a été fermé.')
            return result
        except Exception as exc:
            with self.db.connect() as c:
                c.execute('UPDATE v2_discovery_sessions SET in_flight=NULL WHERE id=? AND in_flight=?',(sid,body.request_id))
                if isinstance(exc,DialogueUnavailable) and body.session_id is None:
                    # A failed typed opening has no session ID on the client yet.
                    c.execute('DELETE FROM v2_discovery_sessions WHERE id=? AND owner_id=? AND revision=0 AND in_flight IS NULL',
                              (sid,member['id']))
            raise

    def _assert_active(self, sid, member, request_id):
        with self.db.connect() as c:
            row=c.execute('SELECT 1 FROM v2_discovery_sessions WHERE id=? AND owner_id=? AND in_flight=? AND expires_at>?',
                (sid,member['id'],request_id,datetime.now(timezone.utc).isoformat())).fetchone()
        if not row:raise PermissionError('Cet échange a été fermé ou a expiré.')

    def _run(self, member, body, payload, sid):
        intent = SearchIntent.model_validate(payload['intent'])
        history = list(payload.get('history',[]))
        last = payload.get('response',{})
        message = body.message.strip()
        if not message and not body.recommend:
            result = {'reply':'Bonjour ! Racontez-moi le moment que vous aimeriez partager. Vous pouvez préciser, changer d’avis ou me demander d’autres idées.',
                      'plans':[], 'suggestions':[], 'mode':'offline','diagnostic':None,'intent':intent.model_dump(),'fallback':None}
            return result,intent,history+[{'role':'assistant','content':result['reply']}]
        fallback = local_decision(message,intent,last,body.recommend)
        adapter = self.adapter_factory(db=self.db,enabled=body.cloud_consent and DialogueAdapter().enabled)
        decision = adapter.decide({'now':datetime.now(PARIS).isoformat(),'timezone':'Europe/Paris',
            'history':history[-12:], 'previous_intent':intent.model_dump(),'last_result':public_result(last),
            'message':message,'recommend':body.recommend,'web_consent':body.web_consent}, fallback)
        self._assert_active(sid,member,body.request_id)
        if body.cloud_consent and adapter.last_mode != 'openai':
            # A requested AI conversation must not silently become a local script.
            raise DialogueUnavailable(adapter.last_fallback)
        intent = decision.intent
        allowed = {a['id'] for a in last.get('suggestions',[])} | {a['id'] for p in last.get('plans',[]) for a in p.get('activities',[])}
        if not set(intent.selected_ids) <= allowed:
            if body.cloud_consent and decision.action=='plan':
                raise DialogueUnavailable('invalid_selection')
            # Comparing cards does not execute a selection. Drop unusable IDs instead
            # of failing an otherwise valid answer; plans still reject unknown IDs.
            intent.selected_ids = [ident for ident in intent.selected_ids if ident in allowed]
        if intent.date_to and not intent.date_from:intent.date_from=intent.date_to
        if intent.date_from and not intent.date_to:intent.date_to=intent.date_from
        history.append({'role':'user','content':message or 'Propose-moi des idées.'})
        result = {'reply':decision.reply,'plans':[],'suggestions':last.get('suggestions',[]) if decision.action=='reply' else [],
                  'mode':adapter.last_mode,'fallback':adapter.last_fallback,'diagnostic':None,'intent':intent.model_dump()}
        if decision.action=='reply':
            result['plans']=last.get('plans',[])
            if last.get('web'):result['web']=last['web']
        try:
            # Validate any model-created dates before they can enter comparisons or E.
            if intent.date_from or intent.date_to:
                try:
                    day_start=date.fromisoformat(intent.date_from or intent.date_to)
                    day_end=date.fromisoformat(intent.date_to or intent.date_from)
                    if day_end<day_start or day_end<datetime.now(PARIS).date():raise ValueError()
                except ValueError:
                    raise PlanningIssue('invalid_date','Cette période est passée ou invalide. Quels prochains jours vous conviendraient ?') from None
            window = validate_window(intent) if intent.start and intent.end else None
            if decision.action in ('discover','web','plan'):
                if not intent.location:
                    raise PlanningIssue('location_missing','Dans quelle ville ou quel quartier souhaitez-vous chercher ?')
                found = self.real.search(member['couple_id'],intent,limit=100 if decision.action=='plan' else 4)
                result['suggestions'], result['retrieval'] = found['items'][:4], {k:v for k,v in found.items() if k!='items'}
                if decision.action == 'plan':
                    window = validate_window(intent)
                    # Explicit time or two real calendars: never silently schedule a demo Friday.
                    from backend.streams.A_calendar.service import AvailabilityService
                    availability = AvailabilityService(self.db)
                    if window is None and not availability._rows(member['couple_id']):
                        raise PlanningIssue('time_missing','Quel jour et quel créneau souhaitez-vous pour le programme ? Les idées ci-dessous restent disponibles.')
                    # Data completeness before scheduling is an actionable failure of its own.
                    complete = [a for a in found['items'] if a['kind']=='event' and a['start'] and a['end'] and a['price_per_person'] is not None and a['location']['lat'] is not None and a['location']['lng'] is not None]
                    if not complete:
                        raise PlanningIssue('activity_details_missing','Je peux proposer ces pistes, mais leurs prix, horaires précis ou coordonnées ne permettent pas encore de construire un programme fiable. Consultez les sources ou cherchons d’autres activités.')
                    query = Query(text=intent.summary or 'Sortie à deux',budget=intent.budget,categories=intent.categories,
                        time_window=window,activity_count=intent.activity_count,max_plans=1,required_activity_ids=intent.selected_ids)
                    with self.db.atomic():
                        self._assert_active(sid,member,body.request_id)
                        planned = self.planning.query(member['couple_id'],query,
                            parsed_request=ParsedRequest(budget=intent.budget,categories=intent.categories,excluded=intent.excluded),
                            candidate_provider=lambda w,b: self.real.candidates(member['couple_id'],intent,w,b))
                    result.update(planned)
                    result['mode']=adapter.last_mode
                    names = ' puis '.join(a['title'] for a in planned['plans'][0]['activities'])
                    result['reply']=f"Voici un programme avec {names}. Les horaires et prix viennent des sources ; les places disponibles restent à confirmer auprès des lieux."
                elif body.web_consent and (decision.action=='web' or len(found['items'])<4
                        or (intent.budget is not None and any(a['price_per_person'] is None for a in found['items'][:4]))):
                    self._search_web(member,intent,result,sid,body.request_id)
                elif found['items']:
                    names = ', '.join(a['name'] for a in found['items'])
                    result['reply']=f"J’ai trouvé {names}. Les fiches indiquent pourquoi ces pistes correspondent et ce qu’il reste à vérifier. Laquelle vous tente, ou préférez-vous une autre ambiance ?"
                else:
                    result['diagnostic']={'code':'no_matching_real_activity'}
                    result['reply']='Le catalogue seul ne contient pas de fiche assez précise pour cette demande. Votre agenda ne bloque pas la recherche ; une recherche web peut compléter les adresses et les prix manquants.'
        except PlanningIssue as exc:
            result.update(reply=str(exc),diagnostic={'code':exc.code})
        if adapter.last_mode == 'openai' and decision.action != 'reply':
            self._assert_active(sid,member,body.request_id)
            facts = grounding(result)
            allowed_ids = {a['id'] for a in facts['activities'] if a.get('id')}
            answer = adapter.respond({'message':message,'history':history[-12:],
                'intent':intent.model_dump(),'result':facts},
                GroundedReply(candidate_ids=[], reply=result['reply'][:1100]), allowed_ids)
            self._assert_active(sid,member,body.request_id)
            result['reply'] = answer.reply
            if adapter.last_mode != 'openai':
                # Keep a completed search/plan, but disclose the failed reformulation.
                result.update(mode='openai_partial',fallback=adapter.last_fallback,
                    warning='La reformulation OpenAI a échoué. Les résultats vérifiés restent affichés. ' + str(DialogueUnavailable(adapter.last_fallback)))
        history.append({'role':'assistant','content':result['reply']})
        return result,intent,history

    def _search_web(self, member, intent, result, sid, request_id):
        # Only the current user-approved search, never raw profiles or conversation history.
        query = ' ; '.join(x for x in [intent.location,
            'catégories : '+', '.join(intent.categories) if intent.categories else '',
            f'budget maximum {intent.budget:g} EUR pour deux' if intent.budget is not None else '',
            f'soit AU PLUS {intent.budget/2:g} EUR PAR PERSONNE' if intent.budget is not None else '',
            f'du {intent.start} au {intent.end}' if intent.start and intent.end else '',
            f'période {intent.date_from} à {intent.date_to or intent.date_from}' if intent.date_from else '',
            'envies : '+', '.join(intent.preferences) if intent.preferences else '',
            'éviter : '+', '.join(intent.excluded) if intent.excluded else '', intent.summary[:250]] if x)
        query = ('Cherche jusqu’à 8 adresses candidates pour retenir 4 recommandations distinctes. '
                 'Le budget indiqué est le TOTAL pour deux, pas par personne. '
                 'Priorité aux menus ou tarifs documentés. ' + query)
        if len(query)>800:
            raise PlanningIssue('search_too_long','La recherche contient trop de contraintes. Quelles sont vos deux ou trois priorités ?')
        records, seen_names, batches = {}, [], []
        web = None
        # One complementary search after actual filtering, never an unbounded agent loop.
        for attempt in range(2):
            self._assert_active(sid,member,request_id)
            batch = self.web.search(member,WebQuery(text=query,area=intent.location,cloud_consent=True,
                processing='ask',result_limit=8,already_seen=seen_names[:16],refinement=bool(attempt)))
            batches.append(batch)
            if batch['status']!='completed':
                if web is None:
                    result['web']=batch
                    result['diagnostic']={'code':batch['reason']}
                    result['reply']='La recherche web est indisponible pour le moment. '+str(DialogueUnavailable(batch['reason']))
                    return
                web['refinement_reason']=batch['reason']
                break  # Keep the first search's cards if the complement fails or hits quota.
            self._assert_active(sid,member,request_id)
            for activity in batch.get('activities',[]):
                row = record_web(activity,batch.get('searched_at',datetime.now(timezone.utc).isoformat()))
                records[row['id']] = row
                if activity['name'] not in seen_names:
                    seen_names.append(activity['name'])
            # Structured web facts use the same constraints/ranking as the catalog.
            found = self.real.search(member['couple_id'],intent,limit=4,
                extra_records=[DatabaseActivities.adapt(a) for a in records.values()])
            sources = {s['url']:s for b in batches for s in b.get('sources',[])}
            web = {**batch,'sources':list(sources.values()),'source_count':len(sources),
                'cached':all(b.get('cached',False) for b in batches)}
            for field in ('raw_count','invalid_count','uncited_count','tool_calls','search_calls'):
                web[field] = sum(b.get(field,0) for b in batches)
            result['suggestions'] = found['items']
            result['retrieval']['web'] = {k:v for k,v in found.items() if k!='items'}
            if len(found['items'])>=4 and (intent.budget is None
                    or all(a['price_per_person'] is not None for a in found['items'])):
                break
        CatalogService(self.db,self.real.memory).persist(list(records.values()))
        web['requests']=len(batches)
        result['retrieval']['web']['requests']=len(batches)
        if result['suggestions']:
            names = ', '.join(a['name'] for a in result['suggestions'])
            result['reply']=f'Voici {names}. Les prix connus figurent sur les fiches ; les autres prix et la disponibilité restent à confirmer.'
        else:
            result['diagnostic']={'code':'no_matching_web_activity'}
            result['reply']='La recherche web n’a pas fourni d’adresse correspondant aux critères avec une source exploitable. Je peux chercher une autre cuisine ou un secteur voisin ; je n’ai pas modifié votre budget.'
        if web.get('refinement_reason'):
            result['warning']='La recherche complémentaire a échoué ; les premières pistes sont conservées. '+str(DialogueUnavailable(web['refinement_reason']))
        # Do not announce unfiltered (over-budget/excluded) venues in the summary.
        result['web']={**web,'answer':result['reply'],'activities':[]}

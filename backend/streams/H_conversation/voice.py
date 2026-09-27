"""Ephemeral guided discovery dialogue; the injected planner owns recommendations."""
from typing import Annotated
from pydantic import BaseModel, Field
from .service import parse_request


class DiscoveryTurn(BaseModel):
    messages: list[Annotated[str, Field(min_length=1, max_length=1500)]] = Field(default_factory=list, max_length=8)
    recommend: bool = False


class SpeechText(BaseModel):
    text: str = Field(min_length=1, max_length=1500)


def discovery_turn(body, recommend):
    messages = [m.strip() for m in body.messages if m.strip()]
    if not messages:
        return {'reply': 'Bonjour ! Quelle sortie vous ferait plaisir à deux : un dîner, une balade, de la culture, ou autre chose ?', 'plans': []}
    parsed = [parse_request(m) for m in messages]
    budget = next((p['budget'] for p in reversed(parsed) if p['budget'] is not None), None)
    if not body.recommend and len(messages) < 3:
        reply = ('Ça marche. Quel budget maximum prévoyez-vous pour vous deux ? Dites par exemple « 80 euros pour deux ». Vous pouvez aussi garder le budget de votre profil.'
                 if budget is None and len(messages) == 1 else
                 'Merci ! Y a-t-il une ambiance à privilégier ou quelque chose à éviter ? Je vérifierai ensuite vos disponibilités communes enregistrées.')
        return {'reply': reply, 'plans': []}
    # Keep the request bounded without truncating away the latest constraints.
    text = '\n'.join(messages)
    if len(text) > 2000:
        return {'reply': 'Résumez votre envie et vos contraintes en un message plus court, puis recommencez cet échange.', 'plans': []}
    try:
        result = recommend(text, budget)
    except ValueError:
        return {'reply': 'Je ne trouve pas de programme qui respecte toutes les contraintes. Vérifiez vos disponibilités dans « Nos disponibilités », ou recommencez avec une autre envie ou un autre budget.', 'plans': []}
    plans = result.get('plans', [])
    if not plans:
        if any(step.get('stage') == 'calendar_window' and step.get('after') == 0 for step in result.get('trace', [])):
            return {**result, 'reply': 'Vos disponibilités ne permettent pas de composer un programme sur ce créneau. Vous pouvez parcourir les idées et ajuster vos disponibilités.'}
        if result.get('activities'):
            return {**result, 'reply': 'Voici des idées de sorties à parcourir. Certains prix ou horaires restent à confirmer avant de composer le programme.'}
        return {**result, 'reply': result.get('message') or 'Aucun programme compatible pour le moment. Vérifiez vos disponibilités ou essayons une autre envie.'}
    plan = plans[0]
    titles = ' puis '.join(a.get('title') or a.get('name', 'une activité') for a in plan['activities'])
    return {**result, 'reply': f"Je vous propose {titles}, pour un budget estimé de {plan['total_couple_cost']:g} euros à deux. Les sources et les informations à confirmer figurent sur les cartes."}

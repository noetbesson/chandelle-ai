"""Ephemeral guided discovery dialogue; the injected planner owns recommendations."""
from typing import Annotated
from pydantic import BaseModel, Field
from .service import parse_request


class DiscoveryTurn(BaseModel):
    model_config = {"extra":"forbid"}
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
    except ValueError as exc:
        return {'reply': str(exc) if hasattr(exc,'code') else 'Je ne trouve pas de programme compatible avec ces contraintes. Essayons une autre activité ou un autre budget.', 'plans': [], 'diagnostic': {'code':getattr(exc,'code','no_feasible_activities')}}
    plans = result.get('plans', [])
    if not plans:
        return {'reply': 'Aucun programme compatible pour le moment. Essayons une autre envie.', 'plans': []}
    plan = plans[0]
    titles = ' puis '.join(a.get('title') or a.get('name', 'une activité') for a in plan['activities'])
    return {**result, 'reply': f"Je vous propose {titles}, pour {plan['total_couple_cost']:g} euros à deux. Voici la fiche avec le créneau et les détails. Ce sont des exemples du catalogue de démonstration."}

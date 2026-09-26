"""Depuis la racine : python -m backend.streams.C_discovery.run_discovery."""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from openai import APIConnectionError, APIStatusError, OpenAI
from pydantic import ValidationError

from .normalizers.models import Activity, DiscoveredActivity, SearchResults
from .sources.openai_web import search_activities

STREAM_DIR = Path(__file__).resolve().parent
ROOT = STREAM_DIR.parents[2]
PARIS = ZoneInfo("Europe/Paris")


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_urls(raw: dict) -> set[str]:
    """URLs attestées par les recherches ou citations de la réponse API."""
    urls = set()
    for item in raw.get("output", []):
        if item.get("type") == "web_search_call":
            for source in (item.get("action") or {}).get("sources") or []:
                if source.get("url"):
                    urls.add(source["url"].split("#")[0].rstrip("/"))
        elif item.get("type") == "message":
            for content in item.get("content", []):
                for annotation in content.get("annotations") or []:
                    if annotation.get("type") == "url_citation":
                        urls.add(annotation["url"].split("#")[0].rstrip("/"))
    return urls


def normalize(records: list, urls: set[str], now: datetime) -> list[Activity]:
    activities = []
    seen = set()
    today = now.astimezone(PARIS).date()
    for index, record in enumerate(records, 1):
        try:
            discovered = DiscoveredActivity.model_validate(record)
            source = str(discovered.source_url).split("#")[0].rstrip("/")
            if urls and source not in urls:
                raise ValueError("source_url absente des sources de recherche")
            if not (discovered.location.address or discovered.website):
                raise ValueError("ni adresse ni site web pour identifier le lieu")
            if discovered.kind == "event":
                if discovered.start is None:
                    raise ValueError("événement sans début vérifiable")
                start = discovered.start.astimezone(PARIS).date()
                end = (discovered.end or discovered.start).astimezone(PARIS).date()
                if start >= today + timedelta(days=14) or end < today:
                    raise ValueError("événement hors de la fenêtre des 14 jours")
            identity = (
                discovered.name.casefold(),
                (discovered.location.address or str(discovered.website)).casefold(),
                discovered.start.isoformat() if discovered.start else None,
            )
            if identity in seen:
                continue
            activity = Activity.model_validate({
                **discovered.model_dump(exclude={"source_url"}),
                "id": "activity_" + uuid5(NAMESPACE_URL, json.dumps(identity)).hex,
                "source": "openai_web",
                "match_score": None,
                "why": None,
                "attribution": "OpenAI web search",
                "fetched_at": now,
            })
            seen.add(identity)
            activities.append(activity)
        except ValidationError:
            print(f"Résultat {index} rejeté : données incompatibles avec Activity.")
        except ValueError as exc:
            print(f"Résultat {index} rejeté : {exc}.")
    return activities


def main() -> int:
    load_dotenv(ROOT / ".env")
    if os.getenv("DISCOVERY_ENABLE_LIVE") != "true":
        print("Live discovery disabled: no OpenAI API call made.")
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, choices=range(1, 6), metavar="1-5")
    args = parser.parse_args()
    try:
        limit = int(os.getenv("DISCOVERY_LIMIT", "5"))
        if not 1 <= limit <= 5:
            raise ValueError
    except ValueError:
        print("Erreur : DISCOVERY_LIMIT doit être un entier entre 1 et 5. Aucun appel API.", file=sys.stderr)
        return 1
    if args.limit is not None:
        limit = min(limit, args.limit)
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("Erreur : OPENAI_API_KEY manque. Renseignez le fichier .env à la racine.", file=sys.stderr)
        return 1
    now = datetime.now(PARIS)
    try:
        with OpenAI(api_key=api_key, timeout=180.0, max_retries=0) as client:
            response = search_activities(
                client, schema=SearchResults.model_json_schema(), today=now.date(),
                limit=limit, model=os.getenv("OPENAI_DISCOVERY_MODEL", "gpt-4.1"),
            )
        report_response(response, limit)
        raw = response.model_dump(mode="json")
        raw_path = STREAM_DIR / "data" / "raw" / f"openai_web_{now.date().isoformat()}.json"
        write_json(raw_path, raw)
        if response.status != "completed":
            raise ValueError("Réponse OpenAI incomplète ; réponse brute conservée.")
        if not any(item.get("type") == "web_search_call" and item.get("status") == "completed"
                   for item in raw.get("output", [])):
            raise ValueError("Aucune recherche web terminée dans la réponse.")
        payload = json.loads(response.output_text)
        if not isinstance(payload, dict) or not isinstance(payload.get("activities"), list):
            raise ValueError("Réponse structurée invalide ; réponse brute conservée.")
        records = payload["activities"]
        print(f"OpenAI web search : {len(records)} résultats récupérés")
        if len(records) > limit:
            raise ValueError("La réponse dépasse la limite demandée ; sortie conservée uniquement en brut.")
        urls = source_urls(raw)
        if not urls:
            print("Avertissement : OpenAI n'a fourni aucune URL de source dans les métadonnées ; vérifier les pages avant usage en démo.")
        activities = normalize(records, urls, now)
        print(f"{len(activities)} résultats valides")
        if not activities:
            raise ValueError("Aucune Activity exploitable ; activities.json n'a pas été modifié.")
        write_json(STREAM_DIR / "data" / "activities.json",
                   [activity.model_dump(mode="json") for activity in activities])
        print("activities.json écrit avec succès")
        for activity in activities:
            print(f"- {activity.name} ({activity.type})")
        return 0
    except APIConnectionError:
        print(f"Activités demandées : {limit} ; retournées : indisponible ; response.id : indisponible ; usage tokens : indisponible")
        print("Erreur : connexion à l'API OpenAI impossible.", file=sys.stderr)
    except APIStatusError as exc:
        print(f"Activités demandées : {limit} ; retournées : indisponible ; response.id : indisponible ; usage tokens : indisponible")
        print(f"Erreur API OpenAI (HTTP {exc.status_code}). Vérifiez accès, modèle et quota.", file=sys.stderr)
    except (ValueError, OSError):
        print("Erreur : réponse inexploitable ou écriture impossible. Consultez les données brutes si présentes.", file=sys.stderr)
    return 1


def report_response(response, limit: int) -> None:
    """Afficher les compteurs même si la réponse est ensuite rejetée."""
    count = "indisponible"
    try:
        payload = json.loads(response.output_text)
        if isinstance(payload, dict) and isinstance(payload.get("activities"), list):
            count = len(payload["activities"])
    except (ValueError, TypeError):
        pass
    print(f"Activités demandées : {limit}")
    print(f"Activités retournées : {count}")
    print(f"response.id : {response.id or 'indisponible'}")
    usage = response.usage
    print("Usage tokens : " + (json.dumps(usage.model_dump(mode="json")) if usage else "indisponible"))


if __name__ == "__main__":
    raise SystemExit(main())

"""Lecture locale pour la démo : aucun client réseau ni rafraîchissement."""

import json
from pathlib import Path


def load_activities() -> list[dict]:
    path = Path(__file__).with_name("activities.json")
    if not path.is_file():
        raise FileNotFoundError(
            "Cache activities.json absent : aucune recherche live automatique."
        )
    return json.loads(path.read_text(encoding="utf-8"))

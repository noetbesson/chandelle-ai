"""Conservative first-person mood declarations, shared by H and G."""
import re
import unicodedata

def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFD",str(text)) if not unicodedata.combining(c)).lower().replace("’", "'")

def explicit_mood(text: str) -> str | None:
    text = normalize(text)
    for label, pattern in [('stressé',r'stresse?e?'),('fatigué',r'fatiguee?|epuisee?'),
                           ('enthousiaste',r'enthousiaste|impatient(?:e)?'),('positif',r'content(?:e)?|heureu[xs]e?')]:
        # Require a self declaration; quoted opinions about a place are not a mood.
        if re.search(r"(?:^|[.!?;\n])\s*(?:aujourd'hui,?\s*)?(?:je suis|je me sens)\s+(?:tres |vraiment |un peu )?(?:"+pattern+r')\b',text):return label
    return None


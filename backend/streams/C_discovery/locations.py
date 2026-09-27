"""Match documented places, including Paris districts, without inventing addresses."""
import re
from backend.streams.C_discovery.import_normalize import fold


def paris_district(value):
    text = fold(value or '')
    postal = re.search(r'\b750(0[1-9]|1[0-9]|20)\b', text)
    if postal:
        return int(postal[1])
    if 'paris' not in text and 'arrondissement' not in text:
        return None
    district = re.search(r'\bparis\s+(\d{1,2})(?:e|eme|er)?\b|\b(\d{1,2})(?:e|eme|er)\b', text)
    if district:
        number = int(district[1] or district[2])
        return number if 1 <= number <= 20 else None
    roman = re.search(r'\bparis\s+(xx|xix|xviii|xvii|xvi|xv|xiv|xiii|xii|xi|ix|viii|vii|vi|iv|iii|ii|x|v|i)(?:e|eme)?\b', text)
    if roman:
        return ['i','ii','iii','iv','v','vi','vii','viii','ix','x','xi','xii','xiii','xiv','xv','xvi','xvii','xviii','xix','xx'].index(roman[1]) + 1
    return None


def matches_location(requested, address, district=None):
    if not requested:
        return True
    wanted = paris_district(requested)
    known = district or paris_district(address)
    address_words = set(re.findall(r'\w+', fold(address or '')))
    if known:
        address_words.add('paris')
    if wanted:
        return known == wanted
    stop = set('a au aux de du des le la les en dans pres vers autour arrondissement france'.split())
    words = set(re.findall(r'\w+', fold(requested))) - stop
    return words <= address_words

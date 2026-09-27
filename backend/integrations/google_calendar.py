"""Read-only Google iCal import. Secret URLs and event text are never persisted."""
from datetime import date, datetime, time, timedelta, timezone
import logging
import re
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import httpx

MAX_BYTES = 5_000_000
PARIS = ZoneInfo('Europe/Paris')


class CalendarUnavailable(RuntimeError):
    pass


class _RedactCalendarURL(logging.Filter):
    def filter(self, record):
        # httpx emits the request URL at INFO, including private iCal capabilities.
        message = record.getMessage()
        if '/calendar/ical/' in message:
            record.msg = re.sub(r'https://[^\s"\']+/calendar/ical/[^\s"\']+', '[Google Calendar privé]', message)
            record.args = ()
        return True


logging.getLogger('httpx').addFilter(_RedactCalendarURL())


def google_ical_url(value):
    try:
        url = urlsplit(value.strip())
        valid = (len(value) <= 2048 and url.scheme == 'https' and
                 url.netloc in ('calendar.google.com', 'www.google.com') and
                 not url.query and not url.fragment and
                 re.fullmatch(r'/calendar/ical/[^/\s]+/(public|private-[a-fA-F0-9]+)/basic\.ics', url.path))
    except ValueError:
        valid = False
    if not valid:
        raise ValueError('Collez l’adresse Google « iCal » se terminant par basic.ics, pas le lien de consultation ou de partage de l’agenda.')
    return urlunsplit(('https', 'calendar.google.com', url.path, '', ''))


async def download_calendar(url):
    url = google_ical_url(url)
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            async with client.stream('GET', url, headers={'Accept': 'text/calendar'}) as response:
                if response.status_code != 200:
                    raise CalendarUnavailable('Agenda inaccessible. Vérifiez son adresse iCal et les autorisations Google. Vos disponibilités précédentes sont conservées.')
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_BYTES:
                        raise CalendarUnavailable('Agenda trop volumineux (5 Mo maximum).')
                return bytes(data)
    except httpx.HTTPError:
        raise CalendarUnavailable('Impossible de joindre Google Calendar. Réessayez ; vos disponibilités précédentes sont conservées.') from None


def busy_intervals(data, start, end):
    """Expand bounded VEVENTs, retaining only UTC occupied intervals.

    A malformed/unsupported calendar fails closed rather than creating free time.
    All-day DTEND is exclusive; transparent and cancelled events do not block.
    """
    from icalendar import Calendar
    import recurring_ical_events

    try:
        if len(data) > MAX_BYTES or not data.lstrip().startswith(b'BEGIN:VCALENDAR') or not data.rstrip().endswith(b'END:VCALENDAR'):
            raise ValueError()
        calendar = Calendar.from_ical(data)
        calendar_zone = ZoneInfo(str(calendar.get('X-WR-TIMEZONE', 'Europe/Paris')))
        events = calendar.walk('VEVENT')
        if len(events) > 5000 or calendar.errors:
            raise ValueError()
        # Require known timezone information; do not silently interpret an unknown TZID as Paris.
        def utc(value):
            if isinstance(value, datetime):
                if value.tzinfo is None:
                    options = {value.replace(tzinfo=calendar_zone, fold=f).astimezone(timezone.utc) for f in (0, 1)
                               if value.replace(tzinfo=calendar_zone, fold=f).astimezone(timezone.utc).astimezone(calendar_zone).replace(tzinfo=None) == value}
                    if len(options) != 1:
                        raise ValueError()
                    return options.pop()
                return value.astimezone(timezone.utc)
            if isinstance(value, date):
                return datetime.combine(value, time.min, calendar_zone).astimezone(timezone.utc)
            raise ValueError()

        for event in events:
            if event.errors or ('DTSTART' not in event and str(event.get('STATUS', '')).upper() != 'CANCELLED'):
                raise ValueError()
            for key in ('DTSTART', 'DTEND', 'RECURRENCE-ID'):
                prop = event.get(key)
                if prop is not None:
                    if prop.params.get('TZID') and isinstance(prop.dt, datetime) and prop.dt.tzinfo is None:
                        raise ValueError()
                    utc(prop.dt)
            rules = event.get('RRULE', [])
            if not isinstance(rules, list):
                rules = [rules]
            for rule in rules:
                if rule.get('FREQ', [''])[0] not in ('DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY') or any(len(rule.get(k, [])) > 1 for k in ('BYSECOND', 'BYMINUTE', 'BYHOUR')):
                    raise ValueError()
            # Google normally expresses cancellations through EXDATE / RECURRENCE-ID.
        occurrences = recurring_ical_events.of(calendar, skip_bad_series=False).between(start.astimezone(calendar_zone), end.astimezone(calendar_zone))
        if len(occurrences) > 10000:
            raise ValueError()
        busy = []
        for event in occurrences:
            if str(event.get('STATUS', '')).upper() == 'CANCELLED' or str(event.get('TRANSP', '')).upper() == 'TRANSPARENT':
                continue
            begin = event.decoded('DTSTART')
            finish = event.decoded('DTEND', None)
            if finish is None:
                duration = event.decoded('DURATION', None)
                if duration is None:
                    if isinstance(begin, datetime):
                        raise ValueError()
                    duration = timedelta(days=1)
                finish = begin + duration
            a, b = utc(begin), utc(finish)
            if b <= a:
                raise ValueError()
            if a < end and b > start:
                busy.append((max(a, start), min(b, end)))
        return busy
    except Exception:
        # Parser errors can contain event titles, email addresses and raw ICS.
        raise ValueError('Agenda iCal invalide ou récurrence non prise en charge. Aucun créneau n’a été remplacé.') from None

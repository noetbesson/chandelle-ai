"""Google iCal → free slots; provider is always simulated."""
from datetime import datetime, timezone
import json
import logging

import httpx
import pytest

from backend.integrations.google_calendar import busy_intervals, google_ical_url
from backend.tests.test_api import client, ready, create, headers, offline_only

HTTP_CLIENT = httpx.AsyncClient

URL = 'https://calendar.google.com/calendar/ical/example%40gmail.com/private-123abc/basic.ics'


def calendar(*events, zone='Europe/Paris'):
    return ('BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Chandelle Tests//FR\r\nX-WR-TIMEZONE:' + zone + '\r\n' +
            '\r\n'.join('BEGIN:VEVENT\r\nUID:test-' + str(i) + '\r\n' + event + '\r\nEND:VEVENT' for i,event in enumerate(events)) +
            '\r\nEND:VCALENDAR\r\n').encode()


def mock_google(monkeypatch, content, status=200, extra_headers=None):
    requests = []
    original = HTTP_CLIENT
    def handle(request):
        requests.append(request)
        assert request.url.host == 'calendar.google.com'
        return httpx.Response(status, content=content, headers=extra_headers or {})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    return requests


def submit(client, member, **changes):
    return client.post('/api/v2/availability/google-calendar', headers=headers(member), json={
        'url': URL, 'start_date':'2026-10-01', 'days':1, 'daily_start':'08:00', 'daily_end':'23:00', **changes})


def test_import_subtracts_busy_and_keeps_private_data_out_of_storage(client, monkeypatch, caplog):
    pair,a,b = ready(client)
    assert client.get('/api/v2/health').json()['extensions']['google_ical'] == 1
    assert client.get('/api/v2/integrations').json()['calendar']['automatic_sync'] is False
    mock_google(monkeypatch, calendar('DTSTART;TZID=Europe/Paris:20261001T100000\r\nDTEND;TZID=Europe/Paris:20261001T110000\r\nSUMMARY:PRIVATE_EVENT_TITLE\r\nDESCRIPTION:PRIVATE_EVENT_DESCRIPTION'))
    with caplog.at_level(logging.INFO, logger='httpx'):
        response = submit(client,a)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['own_slots'] == [{'start':'2026-10-01T06:00:00+00:00','end':'2026-10-01T08:00:00+00:00'}, {'start':'2026-10-01T09:00:00+00:00','end':'2026-10-01T21:00:00+00:00'}]
    assert result['calendar_import']['days'] == 1 and result['common_slots'] == []
    partner = client.get('/api/v2/availability',headers=headers(b)).json()
    assert partner['own_slots'] == [] and partner['calendar_import'] is None
    assert 'private-123abc' not in caplog.text
    with client.app.state.v2['db'].connect() as conn:
        dump = '\n'.join(conn.iterdump())
    for secret in ['PRIVATE_EVENT_TITLE','PRIVATE_EVENT_DESCRIPTION','private-123abc','example%40gmail.com']:
        assert secret not in dump and secret not in response.text


def test_both_imports_intersect_and_invalidate_suggestions(client, monkeypatch):
    pair,a,b = ready(client)
    with client.app.state.v2['db'].connect() as conn:
        conn.execute('INSERT INTO v2_suggestions(id,couple_id,state,payload,created_at,expires_at) VALUES(?,?,?,?,?,?)',
                     ('pending-calendar-test',pair['couple_id'],'new','{}','2026-10-01','2026-10-03'))
    mock_google(monkeypatch, calendar('DTSTART:20261001T080000Z\r\nDTEND:20261001T090000Z'))
    assert submit(client,a).status_code == 200
    mock_google(monkeypatch, calendar('DTSTART:20261001T083000Z\r\nDTEND:20261001T100000Z'))
    result = submit(client,b).json()
    assert result['both_configured']
    with client.app.state.v2['db'].connect() as conn:
        assert conn.execute('SELECT state FROM v2_suggestions WHERE id=?',('pending-calendar-test',)).fetchone()[0]=='expired'
    assert result['common_slots'] == [{'start':'2026-10-01T06:00:00+00:00','end':'2026-10-01T08:00:00+00:00'}, {'start':'2026-10-01T10:00:00+00:00','end':'2026-10-01T21:00:00+00:00'}]
    # Editing manually replaces the import source and does not restore demo mode.
    result = client.put('/api/v2/availability',headers=headers(b),json={'slots':[]}).json()
    assert result['calendar_import'] is None and result['common_slots'] == []
    assert result['mode'] != 'demo'


def test_recurrence_exceptions_and_dst():
    data = calendar('DTSTART;TZID=Europe/Paris:20261018T100000\r\nDTEND;TZID=Europe/Paris:20261018T110000\r\nRRULE:FREQ=WEEKLY;COUNT=3\r\nEXDATE;TZID=Europe/Paris:20261025T100000')
    busy = busy_intervals(data,datetime(2026,10,17,tzinfo=timezone.utc),datetime(2026,11,3,tzinfo=timezone.utc))
    assert [(a.isoformat(),b.isoformat()) for a,b in busy] == [('2026-10-18T08:00:00+00:00','2026-10-18T09:00:00+00:00'),('2026-11-01T09:00:00+00:00','2026-11-01T10:00:00+00:00')]


def test_moved_occurrence():
    data = calendar('DTSTART:20261001T100000Z\r\nDTEND:20261001T110000Z\r\nRRULE:FREQ=DAILY;COUNT=2',
                    'RECURRENCE-ID:20261002T100000Z\r\nDTSTART:20261002T120000Z\r\nDTEND:20261002T130000Z').replace(b'UID:test-1', b'UID:test-0')
    busy = busy_intervals(data,datetime(2026,10,1,tzinfo=timezone.utc),datetime(2026,10,3,tzinfo=timezone.utc))
    assert [a.hour for a,b in busy] == [10,12]


def test_all_day_exclusive_end_transparent_cancelled_and_overlaps(client, monkeypatch):
    _,a,_=ready(client)
    mock_google(monkeypatch,calendar('DTSTART;VALUE=DATE:20261001\r\nDTEND;VALUE=DATE:20261003',
        'DTSTART:20261003T080000Z\r\nDTEND:20261003T090000Z\r\nTRANSP:TRANSPARENT',
        'DTSTART:20261003T100000Z\r\nDTEND:20261003T120000Z\r\nSTATUS:CANCELLED'))
    result=submit(client,a,days=3).json()
    assert result['own_slots'] == [{'start':'2026-10-03T06:00:00+00:00','end':'2026-10-03T21:00:00+00:00'}]
    mock_google(monkeypatch,calendar('DTSTART:20261001T070000Z\r\nDTEND:20261001T083000Z', 'DTSTART:20261001T080000Z\r\nDTEND:20261001T100000Z'))
    result=submit(client,a).json()
    assert result['own_slots'] == [{'start':'2026-10-01T06:00:00+00:00','end':'2026-10-01T07:00:00+00:00'}, {'start':'2026-10-01T10:00:00+00:00','end':'2026-10-01T21:00:00+00:00'}]


@pytest.mark.parametrize('url', ['http://calendar.google.com/calendar/ical/a/public/basic.ics','https://localhost/test.ics','https://calendar.google.com.evil.test/calendar/ical/a/public/basic.ics','https://calendar.google.com/calendar/u/0/r','https://calendar.google.com/calendar/ical/a/public/basic.ics?redirect=evil','https://user@calendar.google.com/calendar/ical/a/public/basic.ics'])
def test_invalid_links_never_fetched(url):
    with pytest.raises(ValueError): google_ical_url(url)


@pytest.mark.parametrize('content,status', [(b'private server error',403),(b'',302),(b'<html>login</html>',200),(b'BEGIN:VCALENDAR\r\nBAD',200)])
def test_failed_import_preserves_previous_slots(client,monkeypatch,content,status):
    _,a,_=ready(client)
    slots=[{'start':'2026-10-01T18:00:00+00:00','end':'2026-10-01T22:00:00+00:00'}]
    client.put('/api/v2/availability',headers=headers(a),json={'slots':slots})
    calls=mock_google(monkeypatch,content,status,{'Location':'http://localhost/private'})
    response=submit(client,a)
    assert response.status_code in (422,502),response.text
    assert len(calls)==1 and 'private server error' not in response.text
    assert client.get('/api/v2/availability',headers=headers(a)).json()['own_slots']==slots


def test_empty_calendar_and_short_gaps(client,monkeypatch):
    _,a,_=ready(client)
    mock_google(monkeypatch,calendar())
    assert submit(client,a).json()['imported_slots']==1
    mock_google(monkeypatch,calendar('DTSTART:20261001T062000Z\r\nDTEND:20261001T210000Z'))
    result=submit(client,a).json()
    assert result['own_slots']==[] and result['configured']


def test_owner_gate_and_private_erasure(client,monkeypatch):
    body={'url':URL,'start_date':'2026-10-01'}
    assert client.post('/api/v2/availability/google-calendar',json=body).status_code==403
    pair=create(client)
    assert client.post('/api/v2/availability/google-calendar',headers=headers(pair['members'][0]),json=body).status_code==409
    _,a,_=ready(client);mock_google(monkeypatch,calendar())
    assert submit(client,a).status_code==200
    assert client.request('DELETE','/api/v2/users/me/data',headers=headers(a),json={'confirmation':'DELETE MY DATA'}).status_code==200
    with client.app.state.v2['db'].connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM v2_calendar_imports WHERE user_id=?',(a['id'],)).fetchone()[0]==0


def test_calendar_timezone_and_cancelled_occurrence():
    start,end=datetime(2026,10,1,tzinfo=timezone.utc),datetime(2026,10,4,tzinfo=timezone.utc)
    data=calendar('DTSTART;VALUE=DATE:20261001\r\nDTEND;VALUE=DATE:20261002',zone='America/New_York')
    busy=busy_intervals(data,start,end)
    assert busy==[(datetime(2026,10,1,4,tzinfo=timezone.utc),datetime(2026,10,2,4,tzinfo=timezone.utc))]
    data=calendar('DTSTART:20261001T100000Z\r\nDTEND:20261001T110000Z\r\nRRULE:FREQ=DAILY;COUNT=2',
                  'RECURRENCE-ID:20261002T100000Z\r\nDTSTART:20261002T100000Z\r\nDTEND:20261002T110000Z\r\nSTATUS:CANCELLED').replace(b'UID:test-1',b'UID:test-0')
    busy=busy_intervals(data,start,end)
    assert len(busy)==1 and busy[0][0].day==1


@pytest.mark.parametrize('event', ['DTSTART;TZID=Not/AZone:20261001T100000\r\nDTEND;TZID=Not/AZone:20261001T110000',
    'DTSTART:20261001T100000Z\r\nDTEND:20261001T110000Z\r\nRRULE:FREQ=SECONDLY',
    'DTSTART:garbage\r\nDTEND:20261001T110000Z'])
def test_unsupported_events_fail_closed(event):
    with pytest.raises(ValueError,match='Aucun créneau'):
        busy_intervals(calendar(event),datetime(2026,10,1,tzinfo=timezone.utc),datetime(2026,10,2,tzinfo=timezone.utc))


def test_import_persists_across_reopen_and_drives_planning(client,monkeypatch):
    from datetime import timedelta
    from backend.db import Database
    from backend.streams.A_calendar.service import AvailabilityService
    pair,a,b=ready(client)
    # The whole first day is busy; the planner must choose the second day.
    mock_google(monkeypatch,calendar('DTSTART;VALUE=DATE:20261001\r\nDTEND;VALUE=DATE:20261002'))
    assert submit(client,a,days=2).status_code==200
    assert submit(client,b,days=2).status_code==200
    db=Database(client.app.state.v2['db'].path)
    state=AvailabilityService(db).state(pair['couple_id'],a['id'])
    assert state['calendar_import'] and len(state['common_slots'])==1
    # The merged planner searches the web; publish test offers on the free day,
    # rather than relying on the old catalogue's floating opening hours.
    def offers_on_free_day(activities):
        for activity in activities:
            for field in ('start', 'end'):
                activity[field] = (datetime.fromisoformat(activity[field]) + timedelta(days=1)).isoformat()
        return activities
    client.app.state.web_provider.override = offers_on_free_day
    response=client.post('/api/v2/recommendations/query',headers=headers(a),json={'text':'Une sortie pour deux','budget':140,'activity_count':1,'max_plans':1,
        'time_window':{'start':'2026-10-01T08:00:00+02:00','end':'2026-10-02T23:00:00+02:00'}})
    assert response.status_code==200,response.text
    assert response.json()['plans'][0]['time_window']['start'].startswith('2026-10-02')

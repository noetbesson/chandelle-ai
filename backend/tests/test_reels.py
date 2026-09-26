"""Integration proof: real synthetic MP4 -> existing B facts -> confirmed planning tastes."""
from dataclasses import replace
from pathlib import Path
import subprocess
import pytest
from backend.tests.test_api import client, offline_only, ready, headers, PREFIX
from backend.integrations.reels.config import Settings
from backend.integrations.reels.errors import ReelError
from backend.integrations.reels.models import TasteSignal

@pytest.fixture
def video(tmp_path):
    cfg=Settings()
    if not cfg.ffmpeg_path.is_file(): pytest.skip('Local FFmpeg required for real video integration')
    path=tmp_path/'sample.mp4'
    subprocess.run([str(cfg.ffmpeg_path),'-nostdin','-v','error','-f','lavfi','-i','color=c=black:s=64x64:r=5','-t','0.4','-c:v','mpeg4',str(path)],check=True,timeout=20)
    return path.read_bytes()

def upload(client,member,video,**extra):
    return client.post(PREFIX+'/reels/upload?wait=true',headers=headers(member),
        files={'video':('sample.mp4',video,'video/mp4')},data={'consent':'true','caption':'Un concert jazz à Paris',**extra})

def facts(client,member):
    return client.get(PREFIX+'/inspirations',headers=headers(member)).json()['items']

def scores(client,cid):
    return client.app.state.v2['catalog'].discover(cid,{'start':'2026-09-26T18:00:00','end':'2026-09-26T23:00:00'},limit=100)

def test_real_video_private_confirmation_dedup_and_erasure(client,video):
    couple,a,b=ready(client);cid=couple['couple_id']
    before=scores(client,cid)
    response=upload(client,a,video,signal_at='2020-01-01T12:00:00Z')
    assert response.status_code==200,response.text
    signal=TasteSignal.model_validate_json(response.text)
    assert signal.source=='reel' and signal.raw_transcript==''
    own=facts(client,a);assert len(own)==1 and facts(client,b)==[]
    fact=own[0];assert fact['privacy_scope']=='PRIVATE' and not fact['value']['confirmed']
    assert fact['value']['signal_at'].startswith('2020-01-01')
    assert fact['value']['taste_signal']['signal_id']==signal.signal_id
    assert 'jazz' in fact['value']['proposed_tags']
    assert scores(client,cid)==before
    repeat=upload(client,a,video)
    assert repeat.status_code==200 and repeat.headers['x-reel-duplicate']=='true'
    assert repeat.json()['signal_id']==signal.signal_id
    assert len(facts(client,a))==1 and facts(client,a)[0]['reinforcement_count']==1
    job=response.headers['x-reel-job-id']
    assert client.get(PREFIX+'/reels/jobs/'+job,headers=headers(b)).status_code==404
    status=client.get(PREFIX+'/reels/jobs/'+job,headers=headers(a)).json()
    assert status['status']=='completed' and status['fact_id']==fact['id']
    confirm=client.post(PREFIX+'/inspirations/'+fact['id']+'/confirm',headers=headers(a),json={'tags':['jazz'],'privacy_scope':'COUPLE_RECOMMENDATION','horizon':'durable'})
    assert confirm.status_code==200,confirm.text
    after=scores(client,cid)
    assert after!=before
    assert facts(client,b)==[]
    new=facts(client,a)[0]
    assert client.get(PREFIX+'/reels/jobs/'+job,headers=headers(a)).json()['fact_id']==new['id']
    # Old imported signals are not fresh temporary wishes.
    assert client.post(PREFIX+'/inspirations/'+new['id']+'/confirm',headers=headers(a),json={'tags':['jazz'],'privacy_scope':'COUPLE_RECOMMENDATION','horizon':'temporary'}).status_code==200
    assert scores(client,cid)==before
    root=client.app.state.v2['reels'].settings.work_dir
    assert not list(root.glob('*/input.mp4')) and not list(root.glob('*/audio.wav'))
    assert client.request('DELETE',PREFIX+'/users/me/data',headers=headers(a),json={'confirmation':'DELETE MY DATA'}).status_code==200
    with client.app.state.v2['db'].connect() as c:
        assert c.execute('SELECT COUNT(*) FROM v2_reel_jobs WHERE owner_id=?',(a['id'],)).fetchone()[0]==0

@pytest.mark.parametrize('changes,expected',[({'consent':'false'},422),({'share_with_couple':'true'},422),({'source_url':'http://localhost/private'},422),({'couple_id':'foreign'},422)])
def test_reel_validation(client,video,changes,expected):
    _,a,_=ready(client)
    assert upload(client,a,video,**changes).status_code==expected
    assert facts(client,a)==[]

def test_async_and_failed_upload_cleanup(client,video):
    _,a,_=ready(client)
    result=client.post(PREFIX+'/reels/upload',headers=headers(a),files={'video':('sample.mp4',video,'video/mp4')},data={'consent':'true','caption':'jazz'})
    assert result.status_code==202,result.text
    status=client.get(result.json()['status_url'],headers=headers(a)).json()
    assert status['status']=='completed'
    invalid=upload(client,a,b'not a video')
    assert invalid.status_code==415
    assert len(facts(client,a))==1

def test_cancelled_job_cannot_reinsert_private_data(client,video,monkeypatch):
    couple,a,_=ready(client)
    import backend.streams.B_memory.reels as module
    original=module.normalize_signal
    def cancelling(*args,**kwargs):
        client.app.state.v2['reels'].cancel({**a,'couple_id':couple['couple_id']})
        return original(*args,**kwargs)
    monkeypatch.setattr(module,'normalize_signal',cancelling)
    assert upload(client,a,video).status_code==410
    assert facts(client,a)==[]

def test_async_duplicate_and_restart_cleanup(client,video):
    from backend.api.app import create_app
    from backend.db import now
    from uuid import uuid4
    couple,a,_=ready(client)
    first=upload(client,a,video)
    duplicate=client.post(PREFIX+'/reels/upload',headers=headers(a),files={'video':('sample.mp4',video,'video/mp4')},data={'consent':'true','caption':'jazz'})
    assert duplicate.status_code==200 and duplicate.json()['duplicate']
    assert duplicate.json()['job_id']==first.headers['x-reel-job-id']
    service=client.app.state.v2['reels']; jid=str(uuid4())
    directory=service.settings.work_dir/jid;directory.mkdir(parents=True)
    (directory/'input.mp4').write_bytes(video)
    with service.db.connect() as c:
        c.execute('INSERT INTO v2_reel_jobs(id,couple_id,owner_id,fingerprint,status,phase,backend,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)', (jid,couple['couple_id'],a['id'],'interrupted','processing','extraction','local',now(),now()))
    restarted=create_app(service.db.path)
    state=restarted.state.v2['reels'].status(jid,{**a,'couple_id':couple['couple_id']})
    assert state['status']=='failed' and state['error']=='INTERRUPTED'
    assert not directory.exists()

def test_upload_needs_identity_rejects_oversize_and_filters_negation(client,video):
    assert client.post(PREFIX+'/reels/upload',files={'video':('a.mp4',video,'video/mp4')}).status_code in (401,403)
    _,a,_=ready(client)
    response=client.post(PREFIX+'/reels/upload',headers={**headers(a),'Content-Type':'multipart/form-data; boundary=test','Content-Length':str(34*1024*1024)},content=b'')
    assert response.status_code==413
    response=upload(client,a,video,caption='Pas de jazz. Je veux un atelier de céramique.')
    assert response.status_code==200,response.text
    proposed=facts(client,a)[0]['value']['proposed_tags']
    assert 'jazz' not in proposed and 'creative' in proposed

def test_manually_edited_memory_is_not_overwritten_on_duplicate(client,video):
    _,a,_=ready(client)
    assert upload(client,a,video).status_code==200
    fact=facts(client,a)[0]
    corrected={'platform':'manual','text':'Ma correction','confirmed':False}
    response=client.patch(PREFIX+'/memories/'+fact['id'],headers=headers(a),json={'value':corrected})
    assert response.status_code==200,response.text
    duplicate=upload(client,a,video)
    assert duplicate.status_code==409 and duplicate.json()['code']=='EXISTING_EDITED'
    assert facts(client,a)[0]['value']==corrected

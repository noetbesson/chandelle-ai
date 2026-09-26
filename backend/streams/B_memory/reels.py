"""Reel jobs write proposed tastes into the existing B memory, never a second store."""
from datetime import datetime, timedelta, timezone
from threading import RLock, BoundedSemaphore
from urllib.parse import urlsplit
import logging
from backend.db import now
from backend.integrations.reels.config import Settings
from backend.integrations.reels.errors import ReelError
from backend.integrations.reels.extract_audio import extract_audio
from backend.integrations.reels.transcribe_gradium import transcribe
from backend.integrations.reels.normalize_pipelex import normalize_signal
from backend.streams.H_conversation.service import interests

LOGGER = logging.getLogger(__name__)

class ReelMemoryService:
    def __init__(self, memory, settings: Settings):
        self.memory, self.db, self.settings = memory, memory.db, settings
        self.guard = RLock()
        self.slots = BoundedSemaphore(2)
        # BackgroundTasks cannot resume after a process restart. Preserve an honest status.
        with self.db.connect() as c:
            c.execute("UPDATE v2_reel_jobs SET status='failed',error='INTERRUPTED',updated_at=? WHERE status IN ('queued','processing')", (now(),))

    def fact(self, member, fingerprint):
        return next((f for f in self.memory.list_facts(member['couple_id'], 'PERSON', member['id'], member['id'])
                     if f['source']=='inspiration_import' and f['key']=='reel:'+fingerprint), None)

    def reserve(self, received, member, backend):
        with self.guard:
            existing=self.fact(member,received.fingerprint)
            if existing:
                return existing
            with self.db.connect() as c:
                active=c.execute("SELECT id FROM v2_reel_jobs WHERE owner_id=? AND fingerprint=? AND status IN ('queued','processing')", (member['id'],received.fingerprint)).fetchone()
                if active: raise ReelError('DUPLICATE_PENDING','Cette vidéo est déjà en cours de traitement.',409)
                since=(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
                count=c.execute('SELECT COUNT(*) FROM v2_reel_jobs WHERE owner_id=? AND created_at>?',(member['id'],since)).fetchone()[0]
                if count>=10: raise ReelError('RATE_LIMIT','Attendez une minute avant un nouvel envoi.',429)
                if not self.slots.acquire(blocking=False): raise ReelError('BUSY','Deux vidéos sont déjà en cours. Réessayez après leur traitement.',429)
                try:
                    c.execute('INSERT INTO v2_reel_jobs(id,couple_id,owner_id,fingerprint,status,phase,backend,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                              (received.job_id,member['couple_id'],member['id'],received.fingerprint,'queued','upload',backend,now(),now()))
                except BaseException:
                    self.slots.release()
                    raise
            return None

    def phase(self, job_id, phase, *, status='processing', error=None):
        with self.db.connect() as c:
            result=c.execute('UPDATE v2_reel_jobs SET phase=?,status=?,error=?,updated_at=? WHERE id=?', (phase,status,error,now(),job_id))
            if not result.rowcount: raise ReelError('CANCELLED','Import annulé après suppression des données.',410)

    def cancel(self, member):
        # Holding this guard against the final write prevents erased data from reappearing.
        with self.guard, self.db.connect() as c:
            c.execute('DELETE FROM v2_reel_jobs WHERE owner_id=? AND couple_id=?',(member['id'],member['couple_id']))

    def status(self, job_id, member):
        with self.db.connect() as c:
            row=c.execute('SELECT id,fingerprint,status,phase,backend,error,created_at,updated_at FROM v2_reel_jobs WHERE id=? AND owner_id=? AND couple_id=?', (job_id,member['id'],member['couple_id'])).fetchone()
        if row is None: raise ReelError('NOT_FOUND','Traitement introuvable.',404)
        result=dict(row)
        fact=self.fact(member,result.pop('fingerprint'))
        result['fact_id']=fact['id'] if fact else None
        return result

    def process(self, received, member, settings):
        try:
            self.phase(received.job_id,'extraction')
            audio=extract_audio(received.video_path,settings=settings)
            self.phase(received.job_id,'transcription')
            transcript=transcribe(audio,settings=settings)
            self.phase(received.job_id,'normalization')
            signal=normalize_signal(transcript,received.caption,received.source_url,settings=settings)
            proposed,_=interests(' '.join(signal.tags))
            _,negative=interests('\n'.join(x for x in [transcript,received.caption] if x))
            proposed=sorted(set(proposed)-set(negative))
            host=urlsplit(received.source_url or '').hostname or ''
            platform='instagram' if (host=='instagram.com' or host.endswith('.instagram.com')) else 'tiktok' if (host=='tiktok.com' or host.endswith('.tiktok.com')) else 'reel'
            value={'platform':platform,'text':'\n'.join(x for x in [received.caption,transcript] if x),
                   'source_url':received.source_url,'signal_at':received.signal_at,'imported_at':now(),
                   'fingerprint':received.fingerprint,'proposed_tags':proposed,'confirmed':False,'horizon':'durable',
                   'taste_signal':signal.model_dump(mode='json'),'normalization_backend':settings.normalization_backend,
                   'transcription_status':'transcribed' if transcript else 'unavailable_or_silent'}
            with self.guard:
                self.phase(received.job_id,'memory')  # cancellation check under the write lock
                self.memory.ingest(member['couple_id'],'PERSON',member['id'],member['id'],
                    'inspiration','reel:'+received.fingerprint,value,privacy_scope='PRIVATE',source='inspiration_import',
                    confidence=signal.confidence,salience=.3,idempotency_key=received.job_id)
                self.phase(received.job_id,'complete',status='completed')
            return signal
        except ReelError as error:
            try: self.phase(received.job_id,'failed',status='failed',error=error.code)
            except ReelError: pass
            raise
        except Exception:
            LOGGER.exception('reel_processing_failed',exc_info=False)
            try: self.phase(received.job_id,'failed',status='failed',error='PROCESSING')
            except ReelError: pass
            raise ReelError('PROCESSING','Le traitement a échoué. Réessayez avec une légende.',500) from None
        finally:
            self.slots.release()

"""Opt-in Gradium REST speech. Keys and audio never enter logs or local storage."""
import io
import json
import os
import wave

import httpx


class SpeechUnavailable(RuntimeError):
    pass


class GradiumAdapter:
    def status(self):
        enabled = os.getenv('GRADIUM_ENABLED', '').lower() in ('1', 'true')
        configured = bool(os.getenv('GRADIUM_API_KEY') and os.getenv('GRADIUM_VOICE_ID'))
        return {'enabled': enabled, 'configured': configured, 'available': enabled and configured}

    async def _post(self, path, **kwargs):
        if not self.status()['available']:
            raise SpeechUnavailable('Voix non configurée : renseignez GRADIUM_ENABLED, GRADIUM_API_KEY et GRADIUM_VOICE_ID côté serveur.')
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post('https://api.gradium.ai/api/post/speech/' + path,
                    headers={'x-api-key': os.environ['GRADIUM_API_KEY'], **kwargs.pop('headers', {})}, **kwargs)
                response.raise_for_status()
                return response
        except httpx.HTTPError:
            raise SpeechUnavailable('Gradium est indisponible. Vérifiez la configuration et le quota, ou continuez par écrit.') from None

    async def transcribe(self, audio):
        try:
            with wave.open(io.BytesIO(audio), 'rb') as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or not 8000 <= wav.getframerate() <= 48000:
                    raise ValueError('Format attendu : WAV PCM mono 16 bits, entre 8 et 48 kHz.')
                if not 0 < wav.getnframes() / wav.getframerate() <= 46:
                    raise ValueError('Une prise de parole doit durer entre 0 et 45 secondes.')
                if len(wav.readframes(wav.getnframes())) != wav.getnframes() * 2:
                    raise ValueError('Audio WAV incomplet.')
        except (wave.Error, EOFError):
            raise ValueError('Audio WAV invalide.') from None
        response = await self._post('asr', content=audio, headers={'Content-Type': 'audio/wav'},
            params={'model': os.getenv('GRADIUM_STT_MODEL', 'default'), 'json_config': json.dumps({'language': 'fr'})})
        try:
            words = []
            for line in response.text.splitlines():
                if not line.strip():
                    continue
                message = json.loads(line)
                if message.get('type') == 'error':
                    raise ValueError()
                if message.get('type') == 'text':
                    words.append(str(message['text']))
            text = ' '.join(words).strip()
            if not text or len(text) > 1500:
                raise ValueError()
            return text
        except (ValueError, KeyError, AttributeError):
            raise SpeechUnavailable('Transcription inexploitable. Réessayez plus brièvement ou écrivez votre message.') from None

    async def speak(self, text):
        response = await self._post('tts', json={'text': text,
            'voice_id': os.environ.get('GRADIUM_VOICE_ID'),
            'model_name': os.getenv('GRADIUM_TTS_MODEL', 'default'),
            'output_format': 'wav', 'only_audio': True})
        if not response.content.startswith(b'RIFF') or response.content[8:12] != b'WAVE':
            raise SpeechUnavailable('La réponse audio de Gradium est invalide. Le texte reste disponible.')
        return response.content

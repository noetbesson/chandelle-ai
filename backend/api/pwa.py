"""PWA assets and an explicit fallback when the share service worker is unavailable."""
from pathlib import Path
from fastapi.responses import FileResponse, HTMLResponse

ROOT=Path(__file__).resolve().parents[2]/'frontend'/'app'

def install_pwa(app):
    @app.get('/manifest.json',include_in_schema=False)
    def manifest():
        return FileResponse(ROOT/'manifest.json',media_type='application/manifest+json',headers={'Cache-Control':'no-cache'})

    @app.get('/sw.js',include_in_schema=False)
    def worker():
        return FileResponse(ROOT/'sw.js',media_type='text/javascript',headers={'Cache-Control':'no-cache','Service-Worker-Allowed':'/'})

    @app.get('/partager',include_in_schema=False)
    def receiver_page():
        return FileResponse(ROOT/'share.html',headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff'})

    @app.get('/installer',include_in_schema=False)
    def installer_page():
        return FileResponse(ROOT/'install.html',headers={'Cache-Control':'no-cache'})

    @app.post('/api/receive-share',include_in_schema=False)
    async def unsupported_share():
        # No anonymous upload storage, no implicit assignment to a couple.
        # The installed PWA intercepts this navigation on-device before networking.
        return HTMLResponse('<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Partage non reçu</title><h1>Le partage n’a pas été enregistré</h1><p>Ouvrez Chandelle et vérifiez son installation, puis recommencez le partage. Vous pouvez aussi ajouter le fichier manuellement.</p><p><a href="/installer">Vérifier l’installation</a> · <a href="/partager">Importer manuellement</a></p></html>',status_code=409,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})

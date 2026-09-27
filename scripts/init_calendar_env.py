"""Add private local calendar settings without printing secrets or overwriting existing settings."""
from pathlib import Path
import subprocess
from cryptography.fernet import Fernet

def main():
    root=Path(__file__).resolve().parents[1]
    subprocess.run(['git','check-ignore','--quiet','.env'],cwd=root,check=True)
    path=root/'.env';text=path.read_text(encoding='utf-8-sig') if path.exists() else ''
    current={line.split('=',1)[0].strip():line.split('=',1)[1].strip().strip('"\x27') for line in text.splitlines() if '=' in line and not line.lstrip().startswith('#')}
    if current.get('CALENDAR_TOKEN_KEY'):Fernet(current['CALENDAR_TOKEN_KEY'].encode())
    else:
        text='\n'.join(line for line in text.splitlines() if not line.startswith('CALENDAR_TOKEN_KEY='))+'\nCALENDAR_TOKEN_KEY='+Fernet.generate_key().decode()+'\n'
    defaults={'CALENDAR_REDIRECT_BASE':'http://127.0.0.1:8000','GOOGLE_CLIENT_ID':'','GOOGLE_CLIENT_SECRET':'',
              'MICROSOFT_CLIENT_ID':'','MICROSOFT_CLIENT_SECRET':'','MICROSOFT_TENANT_ID':'common',
              'PROACTIVE_SCHEDULER_ENABLED':'0','PROACTIVE_DEMO_MODE':'0','PROACTIVE_MOOD_OPENAI':'0',
              'CALENDAR_ALLOW_DEMO_EVENTS':'0'}
    text=text.rstrip()+'\n'+''.join(k+'='+v+'\n' for k,v in defaults.items() if k not in current)
    path.write_text(text,encoding='utf-8')
    print('Configuration calendrier préparée dans le .env ignoré. Aucune valeur secrète affichée. OAuth et planification restent à configurer.')

if __name__=='__main__':main()

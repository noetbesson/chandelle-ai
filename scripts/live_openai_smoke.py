"""Never called by tests or demo initialization."""
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if os.getenv('RUN_LIVE_OPENAI_SMOKE')!='1':
    raise SystemExit('Set RUN_LIVE_OPENAI_SMOKE=1 explicitly to permit the live smoke.')
from backend.integrations.openai import OpenAIAdapter
adapter=OpenAIAdapter()
if not adapter.status()['available']:
    raise SystemExit('Configure OPENAI_ENABLED=1, OPENAI_API_KEY and OPENAI_MODEL first.')
result=adapter.parse('A culture date under 80 euros')
if adapter.last_mode!='openai':
    raise SystemExit('Live smoke failed; provider returned no validated output.')
print('Live Responses structured-output smoke passed.')

"""Initialize local V2 SQL/catalog; --seed explicitly opts into completed demo interviews."""
import argparse
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.api.app import create_app
from backend.streams.B_memory.onboarding import CoupleCreate,Answer

parser=argparse.ArgumentParser()
parser.add_argument('--database',default='.runtime/chandelle_v2.sqlite3')
parser.add_argument('--seed',action='store_true')
args=parser.parse_args()
app=create_app(args.database)
if args.seed:
    onboarding=app.state.v2['onboarding']
    result=onboarding.create(CoupleCreate(person_a='Alex',person_b='Sam'))
    for person in result['members']:
        member=onboarding.authenticate(person['token'])
        for step in range(1,8):
            value={'name':person['name']} if step==1 else {'values':['food','culture']} if step==2 else {'skip':True}
            onboarding.answer(result['couple_id'],person['id'],member,Answer(step=step,value=value))
        onboarding.complete(result['couple_id'],person['id'],member)
    # Local capabilities are sensitive: write to ignored private file, never logs.
    import json,os
    target=Path('.runtime/demo-session.json');target.parent.mkdir(exist_ok=True)
    descriptor=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(descriptor,'w') as f:json.dump(result,f)
    print('Demo created. Prefer CHANDELLE_DEV=1 and Settings → Demo seed for browser sign-in.')
print('Initialized V2 schema and fictional catalog:',args.database)

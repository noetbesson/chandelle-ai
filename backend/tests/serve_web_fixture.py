"""Explicit localhost UI harness; provider simulations, not a deployable data source."""
import os
from pathlib import Path
if os.getenv('RUN_WEB_UI_FIXTURE')!='1':raise RuntimeError('Test harness requires RUN_WEB_UI_FIXTURE=1')
os.environ['CHANDELLE_DEV']='1';os.environ['PROACTIVE_SCHEDULER_ENABLED']='0'
from backend.api.app import create_app
from backend.tests.web_provider import install
class Patches:
    def setenv(self,k,v):os.environ[k]=v
    def setattr(self,obj,key,value):setattr(obj,key,value)
app=create_app(Path(__file__).resolve().parents[2]/'.runtime/web-ui.sqlite3')
install(app,Patches())

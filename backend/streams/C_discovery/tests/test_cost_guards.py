"""The retired command delegates only to the authenticated application API."""
import json
from unittest.mock import patch
import pytest
from backend.streams.C_discovery import run_discovery as runner

def test_cli_requires_identity_without_network(monkeypatch):
    monkeypatch.delenv('CHANDELLE_MEMBER_TOKEN',raising=False)
    with patch.object(runner,'urlopen') as call:
        with pytest.raises(SystemExit):runner.main(['--query','Un dîner'])
        call.assert_not_called()

def test_cli_uses_same_route_and_no_direct_provider(monkeypatch):
    monkeypatch.setenv('CHANDELLE_MEMBER_TOKEN','test-capability')
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'status':'completed','activities':[],'message':'Aucune piste','trace':[]}).encode()
    with patch.object(runner,'urlopen',return_value=Response()) as call:
        assert runner.main(['--query','Un dîner'])==0
        request=call.call_args.args[0]
        assert request.full_url=='http://127.0.0.1:8000/api/v2/dates/search'
        assert json.loads(request.data)['constraints']['mode']=='auto'

"""The launcher loads secrets without executing .env contents or contacting providers."""
from pathlib import Path
import subprocess
import sys

import pytest

from scripts import run_local as launcher


@pytest.fixture
def local_env(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, 'ROOT', tmp_path)
    for name in launcher.ALLOWED | {'CHANDELLE_ENV_FILE'}:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
    return tmp_path / '.env'


def complete_file(path):
    path.write_text('OPENAI_API_KEY=sk-test-only\nGRADIUM_API_KEY=test-gradium-only\n'
                    'GRADIUM_VOICE_ID=test-voice\nOPENAI_ENABLED=1\n'
                    'OPENAI_WEB_ENABLED=1\nGRADIUM_ENABLED=1\n')


def test_dotenv_is_data_and_exported_values_win(local_env, tmp_path, capsys):
    marker = tmp_path / 'must-not-exist'
    local_env.write_text(f'export OPENAI_API_KEY="sk-test#literal"\n'
                         f'OPENAI_MODEL="$(touch {marker})"\n'
                         'GRADIUM_API_KEY=${OPENAI_API_KEY}\n'
                         'OPENAI_ENABLED=true\nLD_PRELOAD=untrusted\nPORT=8123\n')
    env = launcher.load_environment(local_env, {'PORT':'8124', 'OPENAI_ENABLED':'0'})
    assert env['OPENAI_API_KEY'] == 'sk-test#literal'
    assert env['GRADIUM_API_KEY'] == '${OPENAI_API_KEY}'
    assert env['OPENAI_MODEL'] == f'$(touch {marker})'
    assert env['PORT'] == '8124' and env['OPENAI_ENABLED'] == '0'
    assert 'LD_PRELOAD' not in env and not marker.exists()
    assert 'untrusted' not in capsys.readouterr().err


@pytest.mark.parametrize('contents', [
    'OPENAI_API_KEY="SECRET_UNFINISHED',
    'OPENAI_API_KEY=SECRET_FIRST\nOPENAI_API_KEY=SECRET_DUPLICATE',
    'GRADIUM_API_KEY="SECRET WITH SPACES"',
    'GRADIUM_VOICE_ID',
    'OPENAI_ENABLED=SECRET_INVALID_FLAG',
])
def test_invalid_config_fails_without_secret_output(local_env, contents, capsys):
    local_env.write_text(contents)
    assert launcher.main(['--check-env']) == 1
    output = capsys.readouterr()
    assert 'SECRET' not in output.out + output.err
    assert output.err


def test_voice_launch_never_prompts_when_configured(local_env, monkeypatch, capsys):
    complete_file(local_env)
    captured = {}
    monkeypatch.setattr('builtins.input', lambda *a: pytest.fail('Unnecessary prompt'))
    monkeypatch.setattr(launcher.getpass, 'getpass', lambda *a: pytest.fail('Unnecessary secret prompt'))
    monkeypatch.setattr(launcher.os, 'chdir', lambda path: None)
    monkeypatch.setattr(launcher.os, 'execve', lambda exe, argv, env: captured.update(exe=exe, argv=argv, env=env))
    assert launcher.main(['--voice']) == 0
    assert captured['env']['OPENAI_API_KEY'] == 'sk-test-only'
    assert captured['env']['GRADIUM_API_KEY'] == 'test-gradium-only'
    assert captured['argv'][-3:] == ['127.0.0.1', '--port', '8000']
    assert all('test-only' not in arg for arg in captured['argv'])
    output = capsys.readouterr()
    assert 'test-only' not in output.out + output.err


def test_explicit_disable_is_respected_even_by_voice_launch(local_env, monkeypatch):
    local_env.write_text('OPENAI_ENABLED=0\nGRADIUM_ENABLED=0\n')
    captured = {}
    monkeypatch.setattr(launcher.os, 'chdir', lambda path: None)
    monkeypatch.setattr(launcher.os, 'execve', lambda exe, argv, env: captured.update(env))
    assert launcher.main(['--voice']) == 0
    assert captured['OPENAI_ENABLED'] == captured['GRADIUM_ENABLED'] == '0'


def test_voice_launch_enables_ai_with_three_keys_and_no_extra_prompt(local_env,monkeypatch):
    local_env.write_text('OPENAI_API_KEY=sk-test-only\nGRADIUM_API_KEY=test-only\nGRADIUM_VOICE_ID=test-voice\n')
    captured={}
    monkeypatch.setattr('builtins.input',lambda *a: pytest.fail('No activation checkbox or launch prompt'))
    monkeypatch.setattr(launcher.os,'chdir',lambda path:None)
    monkeypatch.setattr(launcher.os,'execve',lambda exe,argv,env:captured.update(env))
    assert launcher.main(['--voice'])==0
    assert captured['OPENAI_ENABLED']==captured['GRADIUM_ENABLED']=='1'
    assert captured['OPENAI_WEB_ENABLED']=='1'


def test_noninteractive_missing_secret_fails_without_server(local_env, monkeypatch, capsys):
    monkeypatch.setattr(launcher.os, 'execve', lambda *a: pytest.fail('Must not start'))
    assert launcher.main(['--voice']) == 1
    assert 'GRADIUM_API_KEY manque' in capsys.readouterr().err


def test_check_env_uses_shared_file_without_starting_server(local_env, tmp_path, monkeypatch, capsys):
    target = tmp_path / 'private.env'
    complete_file(target)
    local_env.symlink_to(target)
    monkeypatch.setattr(launcher.os, 'execve', lambda *a: pytest.fail('Check must not start server'))
    assert launcher.main(['--voice', '--check-env']) == 0
    output = capsys.readouterr().out
    assert 'renseigné' in output and 'sk-test-only' not in output and 'test-gradium-only' not in output


def test_explicit_missing_env_path_has_safe_error(local_env, monkeypatch, capsys):
    monkeypatch.setenv('CHANDELLE_ENV_FILE', str(local_env.parent / 'SECRET_MISSING'))
    assert launcher.main(['--check-env']) == 1
    assert 'SECRET_MISSING' not in capsys.readouterr().err


def test_both_shell_entrypoints_accept_diagnostic_from_another_directory(tmp_path):
    config = tmp_path / 'config.env'
    complete_file(config)
    root = Path(__file__).resolve().parents[2]
    for entrypoint in ('run.sh', 'run_voice.sh'):
        result = subprocess.run(['bash', str(root / 'scripts' / entrypoint), '--check-env'],
                                cwd=tmp_path, env={'CHANDELLE_ENV_FILE':str(config), 'PATH':'/usr/bin:/bin'},
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stderr
        assert 'OPENAI_API_KEY : renseigné' in result.stdout
        assert 'sk-test-only' not in result.stdout + result.stderr


def test_dotenv_files_are_not_served_by_api(client):
    for path in ('/.env', '/v2-static/.env', '/v2-static/../.env'):
        assert client.get(path).status_code == 404


# Reuse the isolated API fixture; it never imports the real local .env.
from backend.tests.test_api import client, offline_only


def test_missing_dependency_shows_actionable_message_before_loading_secrets(local_env, monkeypatch, capsys):
    complete_file(local_env)
    installed = launcher.version
    def missing_crypto(name):
        if name == 'cryptography':
            raise launcher.PackageNotFoundError(name)
        return installed(name)
    monkeypatch.setattr(launcher, 'version', missing_crypto)
    monkeypatch.setattr(launcher.os, 'execve', lambda *a: pytest.fail('Incomplete runtime must not start'))
    assert launcher.main(['--voice']) == 1
    output = capsys.readouterr().err
    assert 'cryptography (absent)' in output
    assert 'uv pip install --python .venv/bin/python -r backend/requirements.txt' in output
    assert 'sk-test-only' not in output and 'Traceback' not in output


def test_new_calendar_and_web_configuration_is_loaded_as_data(local_env):
    local_env.write_text('CALENDAR_TOKEN_KEY=encrypted-test-only\nGOOGLE_CLIENT_ID=local-id\n'
                         'GOOGLE_CLIENT_SECRET=local-secret\nCALENDAR_REDIRECT_BASE=http://127.0.0.1:8000\n'
                         'PROACTIVE_SCHEDULER_ENABLED=false\nOPENAI_WEB_MAX_TOOL_CALLS=2\n')
    env = launcher.load_environment(local_env, {})
    assert env['CALENDAR_TOKEN_KEY'] == 'encrypted-test-only'
    assert env['GOOGLE_CLIENT_SECRET'] == 'local-secret'
    assert env['CALENDAR_REDIRECT_BASE'] == 'http://127.0.0.1:8000'
    assert env['PROACTIVE_SCHEDULER_ENABLED'] == '0'
    assert env['OPENAI_WEB_MAX_TOOL_CALLS'] == '2'

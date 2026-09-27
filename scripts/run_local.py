"""Load local configuration as data, then replace this process with the server."""
import argparse
import getpass
import os
from pathlib import Path
import sys

from dotenv.parser import parse_stream

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = frozenset('''
OPENAI_API_KEY OPENAI_ENABLED OPENAI_WEB_ENABLED OPENAI_MODEL OPENAI_WEB_MODEL
OPENAI_DIALOGUE_MODEL OPENAI_EMBEDDING_MODEL OPENAI_DAILY_RESERVE_USD
OPENAI_TOTAL_RESERVE_USD OPENAI_PLAN_EXPLANATIONS
GRADIUM_API_KEY GRADIUM_VOICE_ID GRADIUM_ENABLED GRADIUM_STT_MODEL GRADIUM_TTS_MODEL
REELS_LIVE_ENABLED REELS_NORMALIZATION_BACKEND REELS_OPENAI_MODEL PIPELEX_API_KEY
DISCOVERY_ENABLE_LIVE DISCOVERY_LIMIT OPENAI_DISCOVERY_MODEL PORT
'''.split())
SWITCHES = {'OPENAI_ENABLED', 'OPENAI_WEB_ENABLED', 'OPENAI_PLAN_EXPLANATIONS',
            'GRADIUM_ENABLED', 'REELS_LIVE_ENABLED'}
SECRETS = ('OPENAI_API_KEY', 'GRADIUM_API_KEY', 'GRADIUM_VOICE_ID')


class ConfigurationError(ValueError):
    pass


def load_environment(path, inherited):
    """No shell evaluation or ${...} interpolation; exported values take priority."""
    values = {}
    ignored = 0
    try:
        with path.open(encoding='utf-8-sig') as stream:
            for row in parse_stream(stream):
                if row.error:
                    raise ConfigurationError(f'.env invalide à la ligne {row.original.line} ; contenu masqué.')
                if row.key is None:
                    continue
                if row.key not in ALLOWED:
                    ignored += 1
                    continue
                if row.key in values:
                    raise ConfigurationError(f'{row.key} est défini plusieurs fois ; garder une seule valeur.')
                if row.value is None or '\x00' in row.value:
                    raise ConfigurationError(f'{row.key} doit être une affectation NOM=valeur valide.')
                values[row.key] = row.value
    except FileNotFoundError:
        if path.is_symlink():
            raise ConfigurationError('Le lien vers le .env ne pointe pas vers un fichier accessible.') from None
    except (OSError, UnicodeError):
        raise ConfigurationError('Impossible de lire le .env ; vérifier son emplacement et ses permissions.') from None
    result = {**values, **inherited}
    for name in SWITCHES & result.keys():
        value = result[name].strip().lower()
        if value not in ('0', '1', 'true', 'false'):
            raise ConfigurationError(f'{name} doit valoir 0 ou 1.')
        result[name] = '1' if value in ('1', 'true') else '0'
    for name in SECRETS:
        value = result.get(name, '')
        if value and (any(c.isspace() for c in value) or '\x00' in value):
            raise ConfigurationError(f'{name} contient des espaces ou caractères invalides ; valeur masquée.')
    if ignored:
        print(f'.env : {ignored} variable(s) non prise(s) en charge ignorée(s).', file=sys.stderr)
    return result


def require_value(env, name, label):
    if env.get(name):
        return
    if not sys.stdin.isatty():
        raise ConfigurationError(f'{name} manque. Renseigner le .env avant de relancer.')
    value = getpass.getpass(label + ' (saisie masquée) : ').strip()
    if not value or any(c.isspace() for c in value):
        raise ConfigurationError(f'{name} manque ou contient des espaces ; valeur masquée.')
    env[name] = value


def configure_voice(env):
    env.setdefault('GRADIUM_ENABLED', '1')
    if env['GRADIUM_ENABLED'] == '1':
        require_value(env, 'GRADIUM_API_KEY', 'Clé API Gradium')
        require_value(env, 'GRADIUM_VOICE_ID', 'Identifiant de voix Gradium')
    # Explicit flags, including 0, avoid repeated prompts and stay authoritative.
    if 'OPENAI_ENABLED' not in env:
        answer = input('Activer le dialogue OpenAI ? [o/N] ') if sys.stdin.isatty() else ''
        env['OPENAI_ENABLED'] = '1' if answer.lower() in ('o', 'y') else '0'
    if env['OPENAI_ENABLED'] == '1':
        require_value(env, 'OPENAI_API_KEY', 'Clé API OpenAI')
        if 'OPENAI_WEB_ENABLED' not in env:
            answer = input('Permettre la recherche web (consentement séparé dans Ask) ? [o/N] ') if sys.stdin.isatty() else ''
            env['OPENAI_WEB_ENABLED'] = '1' if answer.lower() in ('o', 'y') else '0'


def main(argv=None):
    parser = argparse.ArgumentParser(description='Démarrage local Chandelle avec chargement du .env.')
    parser.add_argument('--voice', action='store_true')
    parser.add_argument('--check-env', action='store_true', help='Diagnostic masqué, sans serveur ni appel API.')
    args = parser.parse_args(argv)
    try:
        configured_path = os.environ.get('CHANDELLE_ENV_FILE')
        path = Path(configured_path).expanduser() if configured_path else ROOT / '.env'
        if configured_path and not path.is_file():
            raise ConfigurationError('Le fichier indiqué par CHANDELLE_ENV_FILE est introuvable.')
        env = load_environment(path, os.environ)
        if args.check_env:
            print('.env : ' + ('fichier lu' if path.is_file() else 'absent ; environnement du terminal uniquement'))
            for name in SECRETS:
                print(name + ' : ' + ('renseigné' if env.get(name) else 'manquant'))
            for name in ('OPENAI_ENABLED', 'OPENAI_WEB_ENABLED', 'GRADIUM_ENABLED'):
                print(name + ' : ' + ('activé' if env.get(name) == '1' else 'désactivé ou non défini'))
            print('Diagnostic local uniquement : validité des clés auprès des fournisseurs non vérifiée.')
            return 0 if all(env.get(name) for name in SECRETS) else 1
        if args.voice:
            configure_voice(env)
        for flag, keys in [('OPENAI_ENABLED', ('OPENAI_API_KEY',)),
                           ('GRADIUM_ENABLED', ('GRADIUM_API_KEY', 'GRADIUM_VOICE_ID'))]:
            if env.get(flag) == '1':
                for name in keys:
                    if not env.get(name):
                        raise ConfigurationError(f'{name} manque alors que {flag} est activé.')
        port = env.get('PORT', '8000')
        if not port.isascii() or not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ConfigurationError('PORT doit être un entier de 1 à 65535.')
        print(f'Démarrage de Chandelle sur http://127.0.0.1:{port}', flush=True)
        print('Si cet onglet était déjà ouvert, rechargez-le (⌘R sur Mac) pour afficher cette version.', flush=True)
        os.chdir(ROOT)
        os.execve(sys.executable, [sys.executable, '-m', 'uvicorn', 'backend.api.app:app',
                                  '--host', '127.0.0.1', '--port', port], env)
        return 0
    except (ConfigurationError, EOFError, KeyboardInterrupt) as exc:
        print(str(exc) if isinstance(exc, ConfigurationError) else 'Démarrage annulé.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

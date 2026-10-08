"""Start the authenticated report app on this computer; preserve local configuration."""
import argparse
import getpass
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / '.local-web'


def create_reviewer(username, password):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.password_validation import validate_password
    from django.db import transaction
    from pronto_web.reports.models import ReportGrant, ReportRecord

    users = get_user_model()
    user = users(username=username)
    user.full_clean(exclude=['password'], validate_unique=False)
    validate_password(password, user=user)
    with transaction.atomic():
        if users.objects.filter(username=username).exists():
            raise ValueError('This account already exists; its password and access were not changed.')
        user.set_password(password)
        user.save()
        ReportGrant.objects.bulk_create(ReportGrant(report=record, user=user) for record in ReportRecord.objects.all())
    return user


def configure(database=None, port=None):
    STATE.mkdir(mode=0o700, exist_ok=True)
    config_file = STATE / 'config.json'
    config = json.loads(config_file.read_text(encoding='utf-8')) if config_file.exists() else {}
    selected = Path(database or config.get('database') or STATE / 'pronto.sqlite3')
    if not selected.is_absolute():
        selected = ROOT / selected
    selected = selected.resolve()
    if (database or config.get('database')) and not selected.is_file():
        raise ValueError('The selected database does not exist. Omit --database to create an empty database.')
    selected_port = port if port is not None else config.get('port', 8770)
    if not isinstance(selected_port, int) or not 1024 <= selected_port <= 65535:
        raise ValueError('Port must be between 1024 and 65535.')
    key_file = STATE / 'secret.key'
    if not key_file.exists():
        with key_file.open('x', encoding='utf-8') as output:
            os.chmod(key_file, 0o600)
            output.write(secrets.token_urlsafe(48))
    key = key_file.read_text(encoding='utf-8').strip()
    if len(key) < 50:
        raise ValueError('The local secret key is missing or invalid.')
    os.environ['PRONTO_DJANGO_SECRET_KEY'] = key
    os.environ['PRONTO_DJANGO_DB'] = str(selected)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'pronto_web.local_settings'
    sys.path.insert(0, str(ROOT))
    return selected, selected_port, config_file


def main():
    from django.core.exceptions import ValidationError
    from django.core.management import CommandError
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', help='Existing SQLite file; selection is remembered.')
    parser.add_argument('--port', type=int, help='Local port (default 8770); selection is remembered.')
    parser.add_argument('--setup-user', help='Create a regular reviewer with access to all current reports.')
    parser.add_argument('--check', action='store_true', help='Check configuration and migrate without starting the server.')
    options = parser.parse_args()
    try:
        database, port, config_file = configure(options.database, options.port)
        import django
        django.setup()
        from django.core.management import call_command
        call_command('migrate', interactive=False, verbosity=0)
        if options.setup_user:
            password = getpass.getpass('Passord for ny bruker: ')
            if password != getpass.getpass('Gjenta passord: '):
                raise ValueError('Passwords do not match.')
            create_reviewer(options.setup_user, password)
            print(f'Bruker opprettet: {options.setup_user}')
        call_command('check')
        temporary = config_file.with_suffix('.tmp')
        temporary.write_text(json.dumps({'database': str(database), 'port': port}, indent=2), encoding='utf-8')
        temporary.replace(config_file)
        if not options.check:
            print(f'PRONTO: http://127.0.0.1:{port}/reports/\nStopp med Ctrl+C.', flush=True)
            call_command('runserver', f'127.0.0.1:{port}', use_reloader=False, insecure_serving=True)
    except (ValueError, OSError, ValidationError, CommandError) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()

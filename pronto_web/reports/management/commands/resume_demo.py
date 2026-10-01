"""Reopen one previously created local demo without reseeding its database."""

import sqlite3
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connections


def inspect_demo_database(database: Path, report_id: str) -> int:
    """Return the restricted demo principal only for an isolated demo database."""
    database = database.resolve()
    if (not database.is_file() or not database.name.endswith('.demo.sqlite3')
            or database == Path(settings.DATABASES['default']['NAME']).resolve()
            or not report_id.startswith('demo-')):
        raise CommandError('Existing *.demo.sqlite3 database and demo- report ID required.')
    try:
        with closing(sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True)) as connection:
            if connection.execute('PRAGMA quick_check').fetchone() != ('ok',):
                raise CommandError('Demo database failed its integrity check.')
            reports = connection.execute('SELECT report_id FROM reports_reportrecord').fetchall()
            users = connection.execute('SELECT id, username FROM auth_user').fetchall()
            grants = connection.execute('SELECT report_id, user_id FROM reports_reportgrant').fetchall()
            revisions = connection.execute(
                'SELECT revision FROM reports_reviewrevision WHERE report_id = ?', (report_id,)
            ).fetchall()
            write_grants = connection.execute('SELECT 1 FROM reports_reportwritegrant LIMIT 1').fetchone()
    except sqlite3.Error as exc:
        raise CommandError('Not a readable PRONTO demo database.') from exc
    if (reports != [(report_id,)] or len(users) != 1
            or users[0][1] != 'local-demo-service'
            or grants != [(report_id, users[0][0])]
            or not revisions or write_grants):
        raise CommandError('Demo database does not match the restricted report and user.')
    return users[0][0]


class Command(BaseCommand):
    help = 'Loopback-only reopening of an existing run_demo database; no data is reseeded.'

    def add_arguments(self, parser):
        parser.add_argument('--database', required=True)
        parser.add_argument('--report', required=True)
        parser.add_argument('--port', type=int, default=8768)

    def handle(self, *args, **options):
        if not 1024 <= options['port'] <= 65535:
            raise CommandError('Use an unprivileged port (1024–65535).')
        database = Path(options['database']).resolve()
        user_id = inspect_demo_database(database, options['report'])
        connections.close_all()
        settings.DATABASES['default']['NAME'] = str(database)
        connections['default'].settings_dict['NAME'] = str(database)
        settings.PRONTO_DEMO_ENABLED = True
        settings.PRONTO_DEMO_REPORTS = [options['report']]
        settings.PRONTO_DEMO_USER_ID = user_id
        settings.PRONTO_REQUIRE_INITIALS = True
        settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
        settings.MIDDLEWARE = [*settings.MIDDLEWARE, 'pronto_web.reports.demo_access.DemoAccessMiddleware']
        self.stdout.write(f'Local demo: http://127.0.0.1:{options["port"]}/reports/{options["report"]}/')
        call_command('runserver', f'127.0.0.1:{options["port"]}', use_reloader=False, insecure_serving=True)

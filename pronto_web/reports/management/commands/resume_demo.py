"""Reopen a previously created local demo without reseeding its database."""

import sqlite3
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connections


def inspect_demo_cohort(database: Path) -> tuple[int, tuple[str, ...]]:
    """Allow only a bounded demo-only database with exact grants to its sole user."""
    database = database.resolve()
    if (not database.is_file() or not database.name.endswith('.demo.sqlite3')
            or database == Path(settings.DATABASES['default']['NAME']).resolve()):
        raise CommandError('Existing isolated *.demo.sqlite3 database required.')
    try:
        with closing(sqlite3.connect(f'{database.as_uri()}?mode=ro', uri=True)) as connection:
            if connection.execute('PRAGMA quick_check').fetchone() != ('ok',):
                raise CommandError('Demo database failed its integrity check.')
            reports = connection.execute('SELECT report_id FROM reports_reportrecord ORDER BY report_id LIMIT 501').fetchall()
            users = connection.execute('SELECT id, username FROM auth_user').fetchall()
            grants = connection.execute('SELECT report_id, user_id FROM reports_reportgrant').fetchall()
            revisions = connection.execute('SELECT DISTINCT report_id FROM reports_reviewrevision').fetchall()
            write_grants = connection.execute('SELECT 1 FROM reports_reportwritegrant LIMIT 1').fetchone()
    except sqlite3.Error as exc:
        raise CommandError('Not a readable PRONTO demo database.') from exc
    report_ids = tuple(row[0] for row in reports)
    if (not 1 <= len(report_ids) <= 500 or any(not identifier.startswith('demo-') for identifier in report_ids)
            or len(users) != 1
            or users[0][1] != 'local-demo-service'
            or sorted(grants) != [(identifier, users[0][0]) for identifier in report_ids]
            or {row[0] for row in revisions} != set(report_ids) or write_grants):
        raise CommandError('Demo database does not match the restricted report and user.')
    return users[0][0], report_ids


def inspect_demo_database(database: Path, report_id: str) -> int:
    """Single-report reopening stays strict; cohorts require an explicit opt-in."""
    user_id, reports = inspect_demo_cohort(database)
    if reports != (report_id,):
        raise CommandError('Use --all-reports to reopen an explicitly validated demo cohort.')
    return user_id


class Command(BaseCommand):
    help = 'Loopback-only reopening of an existing run_demo database; no data is reseeded.'

    def add_arguments(self, parser):
        parser.add_argument('--database', required=True)
        selection = parser.add_mutually_exclusive_group(required=True)
        selection.add_argument('--report')
        selection.add_argument('--all-reports', action='store_true')
        parser.add_argument('--port', type=int, default=8768)

    def handle(self, *args, **options):
        if not 1024 <= options['port'] <= 65535:
            raise CommandError('Use an unprivileged port (1024–65535).')
        database = Path(options['database']).resolve()
        if options['all_reports']:
            user_id, reports = inspect_demo_cohort(database)
        else:
            user_id = inspect_demo_database(database, options['report'])
            reports = (options['report'],)
        connections.close_all()
        settings.DATABASES['default']['NAME'] = str(database)
        connections['default'].settings_dict['NAME'] = str(database)
        settings.PRONTO_DEMO_ENABLED = True
        settings.PRONTO_DEMO_REPORTS = list(reports)
        settings.PRONTO_DEMO_USER_ID = user_id
        settings.PRONTO_REQUIRE_INITIALS = True
        settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
        settings.MIDDLEWARE = [*settings.MIDDLEWARE, 'pronto_web.reports.demo_access.DemoAccessMiddleware']
        self.stdout.write(f'Local demo ({len(reports)} reports): http://127.0.0.1:{options["port"]}/reports/')
        call_command('runserver', f'127.0.0.1:{options["port"]}', use_reloader=False, insecure_serving=True)

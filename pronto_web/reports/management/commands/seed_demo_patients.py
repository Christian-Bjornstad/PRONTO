"""Explicitly append invented patients to an existing isolated demo database."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import BaseCommand, CommandError
from django.db import connections

from .resume_demo import inspect_demo_cohort
from pronto_web.reports.synthetic_demo import seed_synthetic_cohort
from pronto_web.reports.synthetic_data import synthetic_report_id


class Command(BaseCommand):
    help = 'Add repeatable synthetic patients to an existing *.demo.sqlite3 database without overwriting reviews.'

    def add_arguments(self, parser):
        parser.add_argument('--database', required=True)
        parser.add_argument('--count', type=int, default=30)
        parser.add_argument('--seed', type=int, default=20261001)

    def handle(self, *args, **options):
        if not 1 <= options['count'] <= 200 or not 0 <= options['seed'] <= 2**31 - 1:
            raise CommandError('Use 1-200 cases and a nonnegative 32-bit seed.')
        database = Path(options['database']).resolve()
        user_id, reports = inspect_demo_cohort(database)
        additions = {synthetic_report_id(index, options['seed']) for index in range(options['count'])} - set(reports)
        if len(reports) + len(additions) > 500:
            raise CommandError('This batch would exceed the 500-report local demo limit.')
        connections.close_all()
        original_name = settings.DATABASES['default']['NAME']
        settings.DATABASES['default']['NAME'] = str(database)
        connections['default'].settings_dict['NAME'] = str(database)
        try:
            result = seed_synthetic_cohort(get_user_model().objects.get(pk=user_id),
                                          count=options['count'], seed=options['seed'])
        finally:
            connections.close_all()
            settings.DATABASES['default']['NAME'] = original_name
            connections['default'].settings_dict['NAME'] = original_name
        self.stdout.write(f'Synthetic demo patients: {result["created"]} added; {result["existing"]} existing patients preserved.')
        self.stdout.write('Reopen with resume_demo --database <same database> --all-reports --port <port>.')

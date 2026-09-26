"""Start an isolated, approved-data demo. Never reuse an existing database."""
import json
from pathlib import Path
from dataclasses import replace
from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.db import connections


class Command(BaseCommand):
    help = 'Loopback-only demo with self-reported initials (new database required).'

    def add_arguments(self, parser):
        parser.add_argument('--database')
        parser.add_argument('--report', action='append')
        parser.add_argument('--port', type=int, default=8768)

    def handle(self, *args, **options):
        if not options['database'] or not options['report']:
            raise CommandError('Explicit new demo database and report ID are required.')
        database = Path(options['database']).resolve()
        reports = options['report']
        if (database.exists() or database == Path(settings.DATABASES['default']['NAME']).resolve()
                or not database.name.endswith('.demo.sqlite3') or len(reports) != 1
                or not reports[0].startswith('demo-') or not 1024 <= options['port'] <= 65535):
            raise CommandError('Use a new *.demo.sqlite3 database, one demo- report ID and an unprivileged port.')
        from pronto_report.adapters.pronto_output import adapt_pronto_output
        from pronto_report.validation import validate_review_state
        from pronto_report.serialization import serialize_report_data, serialize_review_state
        from django.contrib.auth import get_user_model
        from pronto_web.reports.models import ReportRecord, ReviewRevision, ReportAsset, ReportGrant

        root = settings.BASE_DIR / 'test_data/ous/251114_A02134_0115_BHCJCKDRX7_TSO_500_LocalApp_postprocessing_results'
        report = replace(adapt_pronto_output(root, sample_id='IPD2225-D01-P01-A08',
            generated_at='2026-09-26T12:00:00Z', generator_version='1.0.0'), report_id=reports[0])
        from django.utils import timezone
        now = timezone.now().isoformat()
        review = validate_review_state({'schemaVersion': '2.0', 'reportId': report.report_id,
            'revision': 1, 'status': 'DRAFT', 'reviewer': {'reviewerId': 'demo'},
            'createdAt': now, 'updatedAt': now, 'variantReviews': [],
            'runQcAssessment': {'status': 'NOT_REVIEWED'}, 'valueCorrections': [],
            'notes': {'summary': '', 'biomarkerContext': '', 'additional': '', 'importedLegacyNote': ''}}, report=report)
        # Exclusive creation refuses races with any pre-existing database.
        database.touch(exist_ok=False)
        connections.close_all()
        settings.DATABASES['default']['NAME'] = str(database)
        connections['default'].settings_dict['NAME'] = str(database)
        call_command('migrate', interactive=False, verbosity=0)
        user = get_user_model().objects.create_user(username='local-demo-service')
        record = ReportRecord.objects.create(report_id=report.report_id, report_data=json.loads(serialize_report_data(report)))
        ReviewRevision.objects.create(report=record, revision=1, review_data=json.loads(serialize_review_state(review)))
        for item in report.attachments:
            ReportAsset.objects.create(report=record, asset_id=item['assetId'], content=(root / item['name']).read_bytes())
        ReportGrant.objects.create(report=record, user=user)
        settings.PRONTO_DEMO_ENABLED = True
        settings.PRONTO_DEMO_REPORTS = reports
        settings.PRONTO_DEMO_USER_ID = user.pk
        settings.PRONTO_REQUIRE_INITIALS = True
        settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
        settings.MIDDLEWARE = [*settings.MIDDLEWARE, 'pronto_web.reports.demo_access.DemoAccessMiddleware']
        self.stdout.write(f'Local demo: http://127.0.0.1:{options["port"]}/reports/{report.report_id}/')
        call_command('runserver', f'127.0.0.1:{options["port"]}', use_reloader=False, insecure_serving=True)

import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from pronto_web.reports.management.commands.resume_demo import inspect_demo_database


class ResumeDemoDatabaseTests(SimpleTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / 'review.demo.sqlite3'
        with closing(sqlite3.connect(self.database)) as connection:
            connection.executescript('''
                CREATE TABLE reports_reportrecord (report_id TEXT PRIMARY KEY);
                CREATE TABLE auth_user (id INTEGER PRIMARY KEY, username TEXT);
                CREATE TABLE reports_reportgrant (report_id TEXT, user_id INTEGER);
                CREATE TABLE reports_reportwritegrant (report_id TEXT, user_id INTEGER);
                CREATE TABLE reports_reviewrevision (report_id TEXT, revision INTEGER);
                INSERT INTO reports_reportrecord VALUES ('demo-review');
                INSERT INTO auth_user VALUES (1, 'local-demo-service');
                INSERT INTO reports_reportgrant VALUES ('demo-review', 1);
                INSERT INTO reports_reviewrevision VALUES ('demo-review', 1);
                INSERT INTO reports_reviewrevision VALUES ('demo-review', 2);
            ''')

    def test_existing_demo_can_resume_with_its_revision_history(self):
        self.assertEqual(inspect_demo_database(self.database, 'demo-review'), 1)

    def test_report_mismatch_or_extra_report_is_refused(self):
        with self.assertRaises(CommandError):
            inspect_demo_database(self.database, 'demo-other')
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("INSERT INTO reports_reportrecord VALUES ('demo-other')")
            connection.commit()
        with self.assertRaises(CommandError):
            inspect_demo_database(self.database, 'demo-review')

    def test_extra_user_or_alignment_write_grant_is_refused(self):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("INSERT INTO auth_user VALUES (2, 'other-user')")
            connection.commit()
        with self.assertRaises(CommandError):
            inspect_demo_database(self.database, 'demo-review')
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute('DELETE FROM auth_user WHERE id=2')
            connection.execute("INSERT INTO reports_reportwritegrant VALUES ('demo-review', 1)")
            connection.commit()
        with self.assertRaises(CommandError):
            inspect_demo_database(self.database, 'demo-review')

    def test_missing_or_non_demo_database_is_refused_without_creation(self):
        missing = self.database.with_name('missing.demo.sqlite3')
        with self.assertRaises(CommandError):
            inspect_demo_database(missing, 'demo-review')
        self.assertFalse(missing.exists())
        with self.assertRaises(CommandError):
            inspect_demo_database(self.database, 'ordinary-report')

    def test_cohort_requires_every_report_to_have_a_grant_and_saved_revision(self):
        from pronto_web.reports.management.commands.resume_demo import inspect_demo_cohort
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("INSERT INTO reports_reportrecord VALUES ('demo-synthetic')")
            connection.commit()
        with self.assertRaises(CommandError):
            inspect_demo_cohort(self.database)

        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("INSERT INTO reports_reportgrant VALUES ('demo-synthetic', 1)")
            connection.execute("INSERT INTO reports_reviewrevision VALUES ('demo-synthetic', 1)")
            connection.commit()
        assert inspect_demo_cohort(self.database) == (1, ('demo-review', 'demo-synthetic'))
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("INSERT INTO reports_reportrecord VALUES ('real-patient')")
            connection.execute("INSERT INTO reports_reportgrant VALUES ('real-patient', 1)")
            connection.execute("INSERT INTO reports_reviewrevision VALUES ('real-patient', 1)")
            connection.commit()
        with self.assertRaises(CommandError):
            inspect_demo_cohort(self.database)

    def test_seed_command_refuses_non_demo_database_without_modification(self):
        database = self.database.with_name('ordinary.sqlite3')
        database.write_bytes(self.database.read_bytes())
        original = database.read_bytes()
        configured = settings.DATABASES['default']['NAME']
        with self.assertRaises(CommandError):
            call_command('seed_demo_patients', database=str(database))
        assert database.read_bytes() == original
        assert settings.DATABASES['default']['NAME'] == configured

    def test_seed_command_rejects_count_and_seed_bounds_without_modification(self):
        original = self.database.read_bytes()
        for count, seed in ((0, 1), (201, 1), (2, -1)):
            with self.assertRaises(CommandError):
                call_command('seed_demo_patients', database=str(self.database), count=count, seed=seed)
        assert self.database.read_bytes() == original

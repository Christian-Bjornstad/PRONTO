import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

from django.core.management import CommandError
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

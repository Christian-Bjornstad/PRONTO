from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from pronto_web.reports.models import ReportGrant, ReportRecord, ReportWriteGrant


class LocalStartupTests(TestCase):
    def test_reviewer_setup_grants_reports_without_admin_or_alignment_permissions(self):
        from scripts.start_web import create_reviewer
        record = ReportRecord.objects.create(report_id='one', report_data={})
        create_reviewer('operator', 'test-password-1234')
        user = get_user_model().objects.get(username='operator')
        assert user.check_password('test-password-1234')
        assert not user.is_staff and not user.is_superuser
        assert ReportGrant.objects.filter(user=user, report=record).exists()
        assert not ReportWriteGrant.objects.exists()
        with self.assertRaises(ValueError):
            create_reviewer('operator', 'replacement-password')
        user.refresh_from_db()
        assert user.check_password('test-password-1234')

    def test_unapproved_reports_remain_private_after_login(self):
        self.client.login(username='missing', password='wrong')
        assert self.client.get('/reports/').status_code == 302
        user = get_user_model().objects.create_user(username='operator', password='test-password-1234')
        self.client.force_login(user)
        ReportRecord.objects.create(report_id='private', report_data={})
        assert self.client.get('/reports/private/').status_code == 404

    def test_local_settings_do_not_enable_demo_access(self):
        from pronto_web import local_settings
        assert not local_settings.PRONTO_DEMO_ENABLED
        assert local_settings.ALLOWED_HOSTS == ['127.0.0.1', 'localhost']
        assert not any('DemoAccessMiddleware' in item for item in local_settings.MIDDLEWARE)

    def test_login_password_change_and_logout_require_csrf_and_keep_access_private(self):
        user = get_user_model().objects.create_user(username='operator', password='test-password-1234')
        client = Client(enforce_csrf_checks=True)
        assert client.post('/accounts/login/', {'username': user.username, 'password': 'test-password-1234'}).status_code == 403
        client.get('/accounts/login/')
        token = client.cookies['csrftoken'].value
        response = client.post('/accounts/login/', {'username': user.username, 'password': 'test-password-1234', 'csrfmiddlewaretoken': token})
        assert response.status_code == 302 and response.url == '/reports/'
        token = client.cookies['csrftoken'].value
        assert client.post('/accounts/password/', {
            'old_password': 'test-password-1234', 'new_password1': 'new-private-password-9876',
            'new_password2': 'new-private-password-9876', 'csrfmiddlewaretoken': token,
        }).status_code == 302
        assert client.get('/reports/').status_code == 200
        assert client.post('/accounts/logout/', {'csrfmiddlewaretoken': token}).status_code == 302
        assert client.get('/reports/').status_code == 302
        user.refresh_from_db()
        assert user.check_password('new-private-password-9876')


def test_restart_reuses_secret_and_refuses_a_missing_saved_database(tmp_path):
    from unittest.mock import patch
    from scripts.start_web import configure
    import json

    state = tmp_path / 'private'
    database = tmp_path / 'existing.sqlite3'
    database.touch()
    with patch('scripts.start_web.STATE', state), patch.dict('os.environ'), patch('sys.path', []):
        selected, port, configuration = configure(str(database), 8771)
        key = (state / 'secret.key').read_bytes()
        configuration.write_text(json.dumps({'database': str(selected), 'port': port}), encoding='utf-8')
        assert configure()[:2] == (selected, 8771)
        assert (state / 'secret.key').read_bytes() == key
        database.unlink()
        import pytest
        with pytest.raises(ValueError):
            configure()
        assert not database.exists()

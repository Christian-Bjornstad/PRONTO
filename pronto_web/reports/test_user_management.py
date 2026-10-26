from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import TestCase, Client

from .models import AdministrationEvent, ReportGrant, ReportRecord
from .team_access import TEAM_GROUP
from .user_management import create_installation_admin, ADMIN_GROUP


class UserManagementTests(TestCase):
    def setUp(self):
        self.team = Group.objects.create(name=TEAM_GROUP)
        self.regular = get_user_model().objects.create_user(username='reviewer')
        self.regular.groups.add(self.team)
        self.report = ReportRecord.objects.create(report_id='team-report', report_data={}, team_shared=True)
        ReportGrant.objects.create(report=self.report, user=self.regular)
        self.private = ReportRecord.objects.create(report_id='private-report', report_data={})
        ReportGrant.objects.create(report=self.private, user=self.regular)
        self.admin = create_installation_admin('manager', 'test-manager-8891')
        self.client.force_login(self.admin)

    def test_setup_is_once_only_and_has_no_django_superuser_privileges(self):
        self.assertFalse(self.admin.is_superuser or self.admin.is_staff)
        self.assertTrue(ReportGrant.objects.filter(user=self.admin, report=self.report).exists())
        self.assertFalse(ReportGrant.objects.filter(user=self.admin, report=self.private).exists())
        with self.assertRaises(ValidationError):
            create_installation_admin('replacement', 'test-new-manager-843')

    def test_normal_users_and_anonymous_cannot_manage_accounts(self):
        self.client.force_login(self.regular)
        self.assertEqual(self.client.get('/accounts/users/').status_code, 403)
        self.assertEqual(self.client.post('/accounts/users/', {'action':'CREATE'}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get('/accounts/users/').status_code, 403)

    def test_create_user_gets_team_reports_and_cannot_inject_admin_role(self):
        response = self.client.post('/accounts/users/', {'action':'CREATE', 'username':'new-user',
            'first_name':'New colleague', 'password':'a-valid-secret-836', 'is_superuser':'true', 'groups':ADMIN_GROUP})
        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(username='new-user')
        self.assertTrue(user.check_password('a-valid-secret-836'))
        self.assertFalse(user.is_staff or user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists())
        self.assertTrue(ReportGrant.objects.filter(user=user, report=self.report).exists())
        self.assertFalse(ReportGrant.objects.filter(user=user, report=self.private).exists())
        self.assertEqual(AdministrationEvent.objects.filter(action='CREATE').count(), 1)

    def test_deactivate_password_reset_and_reactivate(self):
        url = '/accounts/users/'
        self.assertEqual(self.client.post(url, {'action':'DEACTIVATE','user_id':self.regular.pk}).status_code, 302)
        self.regular.refresh_from_db()
        self.assertFalse(self.regular.is_active)
        self.assertEqual(self.client.post(url, {'action':'PASSWORD','user_id':self.regular.pk,
            'password':'new-colleague-pass-843'}).status_code, 302)
        self.assertEqual(self.client.post(url, {'action':'ACTIVATE','user_id':self.regular.pk}).status_code, 302)
        self.regular.refresh_from_db()
        self.assertTrue(self.regular.is_active and self.regular.check_password('new-colleague-pass-843'))

    def test_admin_cannot_be_deactivated_or_reset_through_team_forms(self):
        for action in ('DEACTIVATE','PASSWORD'):
            self.client.post('/accounts/users/', {'action':action,'user_id':self.admin.pk,'password':'another-secret-835'})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active and self.admin.check_password('test-manager-8891'))

    def test_mutation_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post('/accounts/users/', {'action':'DEACTIVATE','user_id':self.regular.pk}).status_code, 403)

    def test_duplicate_and_weak_passwords_show_errors_without_creating_accounts(self):
        self.assertContains(self.client.post('/accounts/users/', {'action':'CREATE','username':'reviewer',
            'first_name':'Reviewer','password':'short'}), 'allerede i bruk')
        self.assertEqual(get_user_model().objects.count(), 2)

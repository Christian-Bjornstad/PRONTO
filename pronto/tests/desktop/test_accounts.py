"""Private bootstrap creates ordinary team accounts without resetting passwords."""
import json

import pytest
from django.contrib.auth.hashers import make_password


@pytest.fixture
def account_file(tmp_path):
    path = tmp_path / 'initial-users.json'
    path.write_text(json.dumps({'schemaVersion': '1.0', 'users': [
        {'username': 'siri', 'firstName': 'Siri', 'passwordHash': make_password('sample-pass-589')},
        {'username': 'anja', 'firstName': 'Anja', 'passwordHash': make_password('other-pass-673')},
    ]}))
    return path


@pytest.mark.django_db
def test_bootstrap_creates_hashed_users_and_never_resets_passwords(account_file, django_user_model):
    from pronto_desktop.accounts import provision_team_accounts, TEAM_GROUP
    assert provision_team_accounts(account_file) == 2
    siri = django_user_model.objects.get(username='siri')
    assert siri.check_password('sample-pass-589')
    assert siri.first_name == 'Siri' and siri.is_active
    assert not siri.is_staff and not siri.is_superuser
    assert siri.groups.filter(name=TEAM_GROUP).exists()
    siri.set_password('changed-by-siri-934')
    siri.is_active = False
    siri.save()
    assert provision_team_accounts(account_file) == 0
    siri.refresh_from_db()
    assert siri.check_password('changed-by-siri-934') and not siri.is_active


@pytest.mark.django_db
def test_existing_unrelated_username_is_not_claimed(account_file, django_user_model):
    from pronto_desktop.accounts import provision_team_accounts, TEAM_GROUP
    existing = django_user_model.objects.create_user(username='siri', password='existing-pass-843')
    with pytest.raises(ValueError):
        provision_team_accounts(account_file)
    existing.refresh_from_db()
    assert existing.check_password('existing-pass-843')
    assert not existing.groups.filter(name=TEAM_GROUP).exists()
    assert not django_user_model.objects.filter(username='anja').exists()


@pytest.mark.django_db
def test_plaintext_or_admin_fields_are_rejected(account_file, django_user_model):
    from pronto_desktop.accounts import provision_team_accounts
    document = json.loads(account_file.read_text())
    document['users'][0]['is_superuser'] = True
    account_file.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        provision_team_accounts(account_file)
    assert not django_user_model.objects.exists()
    document['users'][0].pop('is_superuser')
    document['users'][0]['passwordHash'] = 'plaintext-pass'
    account_file.write_text(json.dumps(document))
    with pytest.raises(ValueError):
        provision_team_accounts(account_file)


@pytest.mark.django_db
def test_team_report_access_excludes_other_users(account_file, django_user_model):
    from pronto_desktop.accounts import provision_team_accounts, grant_imported_report
    from pronto_web.reports.models import ReportRecord, ReportGrant
    provision_team_accounts(account_file)
    outsider = django_user_model.objects.create_user(username='other')
    report = ReportRecord.objects.create(report_id='report-team', report_data={})
    siri = django_user_model.objects.get(username='siri')
    grant_imported_report(report, siri)
    assert set(ReportGrant.objects.filter(report=report).values_list('user__username', flat=True)) == {'siri', 'anja'}
    separate = ReportRecord.objects.create(report_id='report-private', report_data={})
    grant_imported_report(separate, outsider)
    assert list(ReportGrant.objects.filter(report=separate).values_list('user__username', flat=True)) == ['other']


@pytest.mark.django_db
def test_seeded_user_can_login_and_change_password(account_file, client, django_user_model):
    from pronto_desktop.accounts import provision_team_accounts
    provision_team_accounts(account_file)
    assert client.login(username='siri', password='sample-pass-589')
    response = client.post('/accounts/password/', {
        'old_password': 'sample-pass-589', 'new_password1': 'new-own-password-583',
        'new_password2': 'new-own-password-583'})
    assert response.status_code == 302
    assert provision_team_accounts(account_file) == 0
    assert django_user_model.objects.get(username='siri').check_password('new-own-password-583')


@pytest.mark.django_db
def test_private_admin_seed_never_resets_changed_password(account_file, django_user_model):
    from pronto_desktop.accounts import provision_administrator
    from pronto_web.reports.user_management import ADMIN_GROUP
    document=json.loads(account_file.read_text())
    document['users']=document['users'][:1]
    account_file.write_text(json.dumps(document))
    assert provision_administrator(account_file)
    admin=django_user_model.objects.get(username='siri')
    assert admin.groups.filter(name=ADMIN_GROUP).exists()
    assert not admin.is_superuser and not admin.is_staff
    admin.set_password('changed-manager-pass-883')
    admin.save()
    assert not provision_administrator(account_file)
    admin.refresh_from_db()
    assert admin.check_password('changed-manager-pass-883')

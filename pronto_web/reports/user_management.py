"""Installation administrators manage ordinary team accounts, never Django roles."""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .models import AdministrationEvent, ReportGrant, ReportRecord
from .team_access import TEAM_GROUP

ADMIN_GROUP = 'PRONTO administrators'


def is_administrator(user):
    return user.is_authenticated and user.is_active and user.groups.filter(name=ADMIN_GROUP).exists()


def share_team_reports(user):
    reports = ReportRecord.objects.filter(team_shared=True).values_list('pk', flat=True)
    ReportGrant.objects.bulk_create([ReportGrant(report_id=pk, user=user) for pk in reports], ignore_conflicts=True)


@transaction.atomic
def create_installation_admin(username, password):
    # Local desktop setup only; never exposed as an unauthenticated web endpoint.
    group, _ = Group.objects.get_or_create(name=ADMIN_GROUP)
    Group.objects.select_for_update().get(pk=group.pk)
    if group.user_set.exists():
        raise ValidationError('Administrator er allerede opprettet. Logg inn med denne kontoen.')
    users = get_user_model()
    if users.objects.filter(username__iexact=username).exists():
        raise ValidationError('Brukernavnet er allerede i bruk.')
    user = users(username=username, first_name='Administrator', is_active=True)
    users._meta.get_field('username').clean(username, user)
    validate_password(password, user)
    user.set_password(password)
    user.save()
    user.groups.add(group, Group.objects.get_or_create(name=TEAM_GROUP)[0])
    share_team_reports(user)
    AdministrationEvent.objects.create(actor=user, action='ADMIN_SETUP', target_username=username)
    return user


class TeamUserForm(forms.Form):
    username = forms.RegexField(r'^[a-z][a-z0-9._-]{0,31}$', label='Brukernavn', max_length=32)
    first_name = forms.CharField(label='Navn', max_length=100)
    password = forms.CharField(label='Startpassord', widget=forms.PasswordInput(render_value=False), max_length=128)

    def clean(self):
        data = super().clean()
        if 'username' in data:
            username = data['username']
            if get_user_model().objects.filter(username__iexact=data['username']).exists():
                self.add_error('username', 'Brukernavnet er allerede i bruk.')
            if 'password' in data:
                user = get_user_model()(username=username, first_name=data.get('first_name', ''))
                try:
                    validate_password(data['password'], user)
                except ValidationError as error:
                    self.add_error('password', error)
        return data


@never_cache
@require_http_methods(['GET', 'POST'])
def manage_users(request):
    if not is_administrator(request.user):
        raise PermissionDenied
    form = TeamUserForm(request.POST if request.method == 'POST' and request.POST.get('action') == 'CREATE' else None)
    error = ''
    if request.method == 'POST':
        with transaction.atomic():
            # Serialize account mutations and recheck authority under the lock.
            actor = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if not is_administrator(actor):
                raise PermissionDenied
            action = request.POST.get('action')
            target = None
            if action == 'CREATE' and form.is_valid():
                target = get_user_model().objects.create_user(**form.cleaned_data)
                target.groups.add(Group.objects.get_or_create(name=TEAM_GROUP)[0])
                share_team_reports(target)
            elif action in {'DEACTIVATE', 'ACTIVATE', 'PASSWORD'}:
                value = request.POST.get('user_id', '')
                target = get_user_model().objects.select_for_update().filter(
                    pk=value if len(value)<=18 and value.isdecimal() else None,
                    groups__name=TEAM_GROUP).first()
                if target is None or target.groups.filter(name=ADMIN_GROUP).exists() or target.is_staff or target.is_superuser:
                    error = 'Denne kontoen kan ikke endres her.'
                    target = None
                elif action == 'PASSWORD':
                    try:
                        password = request.POST.get('password', '')
                        if len(password) > 128:
                            raise ValidationError('Passordet er for langt.')
                        validate_password(password, target)
                        target.set_password(password)
                        target.save(update_fields=['password'])
                    except ValidationError as exc:
                        error = ' '.join(exc.messages)
                        target = None
                else:
                    target.is_active = action == 'ACTIVATE'
                    target.save(update_fields=['is_active'])
            if target:
                AdministrationEvent.objects.create(actor=actor, action=action, target_username=target.username)
                return redirect('manage-users')
    users = get_user_model().objects.filter(groups__name=TEAM_GROUP).order_by('username')
    return render(request, 'reports/users.html', {'form': form, 'users': users, 'error': error,
        'admin_ids': set(get_user_model().objects.filter(groups__name=ADMIN_GROUP).values_list('pk', flat=True))})

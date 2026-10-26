"""Private installation bootstrap; account passwords are supplied as Django hashes."""
import json
from pathlib import Path
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import identify_hasher
from django.contrib.auth.models import Group
from django.db import transaction

from pronto_web.reports.team_access import TEAM_GROUP, grant_imported_report


def read_initial_accounts(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 64 * 1024:
        raise ValueError('Brukeroppsettet er ugyldig eller for stort.')
    document = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(document, dict) or set(document) != {'schemaVersion', 'users'} or document['schemaVersion'] != '1.0':
        raise ValueError('Brukeroppsettet har ukjent format.')
    users = document['users']
    if not isinstance(users, list) or not 1 <= len(users) <= 50:
        raise ValueError('Brukeroppsettet må ha mellom 1 og 50 brukere.')
    names = set()
    for user in users:
        if not isinstance(user, dict) or set(user) != {'username', 'firstName', 'passwordHash'}:
            raise ValueError('Brukeroppsettet inneholder ukjente felt.')
        name, first_name, password = user['username'], user['firstName'], user['passwordHash']
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9._-]{0,31}', name) or name in names:
            raise ValueError('Brukernavn må være entydige og bruke små bokstaver.')
        if not isinstance(first_name, str) or not 1 <= len(first_name) <= 100 or any(ord(c) < 32 for c in first_name):
            raise ValueError('Visningsnavnet er ugyldig.')
        if not isinstance(password, str) or len(password) > 128:
            raise ValueError('Passordhashen er ugyldig.')
        try:
            hasher = identify_hasher(password)
            decoded = hasher.decode(password)
            valid = hasher.algorithm == 'pbkdf2_sha256' and decoded['iterations'] >= 1_000_000 and len(decoded['salt']) >= 16
        except (ValueError, KeyError, TypeError):
            valid = False
        if not valid:
            raise ValueError('Brukeroppsettet krever en gyldig PBKDF2-passordhash.')
        names.add(name)
    return document


@transaction.atomic
def provision_team_accounts(path):
    """Create once. Never reset passwords, reactivate users or grant admin access."""
    document = read_initial_accounts(path)
    users = get_user_model()
    group, _ = Group.objects.get_or_create(name=TEAM_GROUP)
    created = 0
    for entry in document['users']:
        user = users.objects.filter(username__iexact=entry['username']).first()
        if user is not None:
            if not user.groups.filter(pk=group.pk).exists():
                raise ValueError('Et brukernavn finnes allerede utenfor PRONTO-teamet. Brukeroppsettet ble ikke endret.')
            continue
        user = users.objects.create(username=entry['username'], first_name=entry['firstName'],
            password=entry['passwordHash'], is_active=True, is_staff=False, is_superuser=False)
        user.groups.add(group)
        created += 1
    return created

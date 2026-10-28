"""Shared database location with inherited share access and explicit admin updates."""
import json
import os
from pathlib import Path
import secrets
import stat

LOCATOR_NAME = 'pronto-installation.json'


def _local_web2(program_root):
    """The team's accessible replacement folder; never copy/create patient data."""
    if os.name != 'nt' or not program_root.resolve().anchor.startswith('\\\\'):
        return None
    root = program_root / '.local-web2'
    def is_file(path):
        try:
            return stat.S_ISREG(path.stat().st_mode)
        except (FileNotFoundError, NotADirectoryError):
            return False
    candidates = [path for path in (root/'pronto.sqlite3', root/'pronto.sqlite',
                  root/'database'/'pronto.sqlite3', root/'database'/'pronto.sqlite') if is_file(path)]
    if len(candidates) > 1:
        raise ValueError('Flere databaser i .local-web2. Administrator må velge felles database.')
    if len(candidates) == 1 and is_file(root/'secret.key'):
        return {'data_root':root.resolve(), 'database':candidates[0].resolve()}
    return None


def read_locator(program_root):
    path = program_root / LOCATOR_NAME
    try:
        with path.open('r', encoding='utf-8') as source:
            text = source.read(64 * 1024 + 1)
    except FileNotFoundError:
        return _local_web2(program_root)
    if len(text) > 64 * 1024:
        raise ValueError('Felles databasevalg er for stort.')
    data = json.loads(text)
    if (not isinstance(data, dict) or set(data) not in ({'schemaVersion', 'dataRoot', 'database'},
            {'schemaVersion', 'dataRoot', 'database', 'selectionMode'})
            or data['schemaVersion'] != '1.0'
            or 'selectionMode' in data and data['selectionMode'] != 'ADMIN'
            or any(not isinstance(data[key], str) or not data[key].strip()
                   for key in ('dataRoot', 'database'))):
        raise ValueError('Felles databasevalg har ugyldig format. Behold eksisterende database.')
    def resolve(value):
        path = Path(value)
        return (path if path.is_absolute() else program_root / path).resolve()
    chosen = {'data_root': resolve(data['dataRoot']), 'database': resolve(data['database'])}
    if data.get('selectionMode') != 'ADMIN' and chosen['data_root'] == (program_root / '.local-web').resolve():
        return _local_web2(program_root) or chosen
    return chosen


def publish_locator(program_root, data_root, database, *, replace_existing=False):
    """Publish verified network data, preserving existing choices and private profiles."""
    program_root = program_root.resolve()
    data_root = data_root.resolve()
    database = database.resolve()
    if not program_root.anchor.startswith('\\\\'):
        return False
    if not data_root.anchor.startswith('\\\\') or not database.anchor.startswith('\\\\'):
        return False
    target = program_root / LOCATOR_NAME
    if target.exists() and not replace_existing:
        return False  # Another installation choice is never overwritten on startup.
    if not database.is_file() or not (data_root / 'secret.key').is_file():
        raise ValueError('Eksisterende database og nøkkel må finnes før felles valg publiseres.')
    def location(path):
        return path.relative_to(program_root).as_posix() if path.is_relative_to(program_root) else path.as_posix()
    document = {'schemaVersion': '1.0', 'dataRoot': location(data_root), 'database': location(database)}
    if replace_existing:
        document['selectionMode'] = 'ADMIN'
    temporary = program_root / f'.pronto-installation-{secrets.token_hex(8)}.tmp'
    try:
        # Inherit the program folder's ACL. Do not chmod this non-secret locator
        # to owner-only access as for private profile settings.
        with temporary.open('x', encoding='utf-8') as output:
            json.dump(document, output, indent=2)
            output.flush()
            os.fsync(output.fileno())
        try:
            if replace_existing:
                temporary.replace(target)
            elif os.name == 'nt':
                temporary.rename(target)  # Windows refuses replacing an existing file.
            else:
                os.link(temporary, target)
        except FileExistsError:
            return False
        return True
    finally:
        temporary.unlink(missing_ok=True)

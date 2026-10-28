"""Persistent local configuration, Django setup, accounts and safe SQLite backup."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
from datetime import datetime, timezone

from .server import LocalServer
from .storage_access import create_data_directory

ROOT = Path(__file__).resolve().parents[1]
_SETUP_LOCK = threading.RLock()


class ConfigurationAccessError(PermissionError):
    """The shared legacy locator cannot be read; selecting a DB is explicit recovery."""


def _preferences_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
    return base / "PRONTO" / "desktop.json"


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("PRONTO configuration must be a JSON object.")
    return value


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f"{path.name}.{secrets.token_hex(6)}.tmp")
    try:
        with temporary.open("x", encoding="utf-8") as output:
            os.chmod(temporary, 0o600)
            json.dump(data, output, indent=2)
            output.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def sqlite_readonly_uri(database) -> str:
    """Keep a UNC server in the path, not SQLite's restricted URI authority."""
    from urllib.parse import quote
    if not database.is_absolute():
        raise ValueError('SQLite requires an absolute database path.')
    if database.as_posix().startswith('//'):
        return 'file://localhost' + quote(database.as_posix(), safe='/:') + '?mode=ro'
    return database.as_uri() + '?mode=ro'


def backup_sqlite(database: Path, destination_root: Path) -> Path:
    """Use SQLite's backup API, including committed WAL data, then check integrity."""
    database = Path(database).resolve(strict=True)
    create_data_directory(destination_root)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = destination_root / f"pronto-{stamp}-{secrets.token_hex(3)}.sqlite3"
    try:
        with sqlite3.connect(sqlite_readonly_uri(database), uri=True, timeout=20) as source:
            with sqlite3.connect(destination, timeout=20) as target:
                os.chmod(destination, 0o600)
                source.backup(target, pages=256, sleep=0.05)
                if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise RuntimeError("Database backup did not pass SQLite integrity_check.")
        return destination
    except BaseException:
        destination.unlink(missing_ok=True)
        raise


class DesktopRuntime:
    def __init__(self, data_root: Path | None = None, port: int | None = None,
                 database_path: Path | None = None):
        self.config_path = _preferences_path()
        preferences = _read_json(self.config_path)
        shared = None
        if (data_root is None and database_path is None and not preferences.get('database')
                and not preferences.get('new_database')):
            from .shared_installation import read_locator
            shared = read_locator(ROOT)
            if shared and (not preferences.get('data_root') or
                    Path(preferences['data_root']).expanduser().resolve() == shared['data_root']):
                data_root = shared['data_root']
                database_path = shared['database']
            else:
                shared = None
        selected = data_root if data_root is not None else preferences.get("data_root")
        self._remembered = shared is not None or data_root is None and bool(preferences.get("data_root"))
        self._new_database = bool(self._remembered and preferences.get('new_database'))
        self.data_root = Path(selected).expanduser().resolve() if selected else ROOT / ".local-web"
        self._legacy = not selected or self.data_root == ROOT / ".local-web"
        saved_database = preferences.get('database') if data_root is None else None
        self._selected_database = Path(database_path or saved_database).expanduser().resolve() if database_path or saved_database else None
        if self._selected_database is not None:
            self._legacy = self._legacy or self._selected_database.parent == self.data_root
        self._requested_port = port if port is not None else preferences.get("port")
        self._server = None
        self._initialized = False
        self.startup_warnings = []
        self.biomarker_info = None
        self.database_path = self.data_root / ("pronto.sqlite3" if self._legacy else "database/pronto.sqlite3")
        if self._selected_database is not None:
            self.database_path = self._selected_database
        self.raw_root = self.data_root / "raw_imports"

    @property
    def port(self) -> int:
        return self._server.port if self._server else self._requested_port or 8770

    @property
    def server(self) -> LocalServer:
        if not self._initialized:
            raise RuntimeError("Initialize the PRONTO desktop runtime first.")
        return self._server

    def administrator_exists(self):
        from django.contrib.auth.models import Group
        from pronto_web.reports.user_management import ADMIN_GROUP
        return Group.objects.filter(name=ADMIN_GROUP, user__isnull=False).exists()

    def setup_administrator(self, username, password):
        from pronto_web.reports.user_management import create_installation_admin
        return create_installation_admin(username.strip().lower(), password).username

    def initialize(self) -> None:
        from django.apps import apps
        from django.conf import settings
        with _SETUP_LOCK:
            if self._initialized:
                return
            if self._new_database and self.database_path.exists():
                raise RuntimeError('Den valgte nye databasen finnes allerede. Velg den som eksisterende database.')
            if self._legacy and self._selected_database is None:
                try:
                    config = _read_json(self.data_root / 'config.json')
                except PermissionError as error:
                    raise ConfigurationAccessError('Kan ikke lese felles config.json. Velg eksisterende PRONTO-database; ingen ny database opprettes.') from error
                selected_db = Path(config.get("database") or self.data_root / "pronto.sqlite3")
                self.database_path = (ROOT / selected_db).resolve() if not selected_db.is_absolute() else selected_db.resolve()
                if config.get('database') and not self.database_path.is_file():
                    raise ValueError('Databasen i fellesoppsettet finnes ikke. Velg eksisterende database; ingen erstatning opprettes.')
                self._requested_port = self._requested_port if self._requested_port is not None else config.get("port", 8770)
            if self._selected_database is not None and not self.database_path.is_file():
                raise ValueError('Den valgte databasen finnes ikke. Ingen erstatning opprettes.')
            if self._remembered and not self._new_database and (not self.data_root.is_dir() or not self.database_path.is_file()):
                raise RuntimeError("The remembered PRONTO database is unavailable. Restore its location or restart "
                                   "with an explicit --data-root to create a new empty database.")
            if settings.configured:
                configured_db = Path(settings.DATABASES["default"]["NAME"]).resolve()
                if configured_db != self.database_path:
                    raise RuntimeError("Changing the PRONTO database requires a restart of the application.")
            create_data_directory(self.data_root)
            create_data_directory(self.raw_root)
            create_data_directory(self.database_path.parent)
            key_path = self.data_root / "secret.key"
            if not key_path.exists():
                if self._selected_database is not None and self.database_path.is_file():
                    raise ValueError('Nøkkelen secret.key mangler for eksisterende database. Behold databasen og gjenopprett riktig nøkkel.')
                with key_path.open("x", encoding="utf-8") as key:
                    os.chmod(key_path, 0o600)
                    key.write(secrets.token_urlsafe(48))
            key = key_path.read_text(encoding="utf-8").strip()
            if len(key) < 50:
                raise ValueError("The local secret key is missing or invalid.")
            os.environ.update({"DJANGO_SETTINGS_MODULE": "pronto_web.local_settings",
                               "PRONTO_DJANGO_SECRET_KEY": key, "PRONTO_DJANGO_DB": str(self.database_path)})
            if not apps.ready:
                import django
                django.setup()
            if not self._legacy:
                # External data roots must never inherit legacy .local-web reference
                # discovery. Explicit environment configuration remains supported.
                files, urls = {}, {}
                for build in ("GRCh37", "GRCh38"):
                    fasta = self.data_root / "references" / f"{build}.fa"
                    index = fasta.with_suffix(".fa.fai")
                    explicit_fasta = os.environ.get(f"PRONTO_IGV_{build}_FASTA_PATH")
                    explicit_index = os.environ.get(f"PRONTO_IGV_{build}_FAI_PATH")
                    if explicit_fasta and explicit_index:
                        files[build] = {"fasta": explicit_fasta, "index": explicit_index}
                    elif fasta.is_file() and index.is_file() and not fasta.is_symlink() and not index.is_symlink():
                        files[build] = {"fasta": str(fasta), "index": str(index)}
                    if build in files:
                        urls[build] = {"fastaURL": f"/igv/references/{build}/fasta/",
                                       "indexURL": f"/igv/references/{build}/index/"}
                    else:
                        urls[build] = {"fastaURL": os.environ.get(f"PRONTO_IGV_{build}_FASTA_URL", ""),
                                       "indexURL": os.environ.get(f"PRONTO_IGV_{build}_FAI_URL", "")}
                settings.PRONTO_IGV_REFERENCE_FILES = files
                settings.PRONTO_IGV_REFERENCES = urls
            from django.core.management import call_command
            from django.db import connection
            from django.db.migrations.executor import MigrationExecutor
            existed = self.database_path.exists() and self.database_path.stat().st_size > 0
            executor = MigrationExecutor(connection)
            pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if pending:
                if existed:
                    self.backup()
                call_command("migrate", interactive=False, verbosity=0)
            call_command("check", verbosity=0)
            from .accounts import provision_team_accounts
            from shutil import copyfile
            saved_accounts = self.data_root / 'initial-users.json'
            from hashlib import sha256
            account_cache = self.config_path.parent / 'accounts' / sha256(str(self.database_path).encode()).hexdigest() / 'initial-users.json'
            configured_accounts = os.environ.get('PRONTO_INITIAL_USERS_FILE')
            bundled_accounts = Path(configured_accounts) if configured_accounts else ROOT / 'config' / 'initial-users.json'
            accounts = saved_accounts if saved_accounts.is_file() else bundled_accounts if bundled_accounts.is_file() else account_cache
            if configured_accounts == '':
                accounts = None
            if configured_accounts and not bundled_accounts.is_file():
                raise ValueError('Den valgte filen med startbrukere finnes ikke.')
            if accounts is not None and accounts.is_file():
                provision_team_accounts(accounts)
                if accounts not in (saved_accounts, account_cache):
                    account_cache.parent.mkdir(parents=True, exist_ok=True)
                    copyfile(accounts, account_cache)
                    os.chmod(account_cache, 0o600)
            from django.contrib.staticfiles.handlers import StaticFilesHandler
            from .accounts import provision_administrator
            admin_seed = ROOT / 'config' / 'initial-admin.json'
            if configured_accounts != '' and admin_seed.is_file():
                provision_administrator(admin_seed)
            from django.core.wsgi import get_wsgi_application
            application = StaticFilesHandler(get_wsgi_application())
            self._server = LocalServer(application, secret=settings.SECRET_KEY,
                                       database=self.database_path, port=self._requested_port if self._requested_port is not None else 8770)
            self._initialized = True
            settings.PRONTO_BIOMARKER_GENES = frozenset()
            marker_file = self.data_root / 'biomarker-list.xlsx'
            if marker_file.is_file():
                from pronto_report.review.biomarker_list import read_biomarker_list
                self.biomarker_info = read_biomarker_list(marker_file)
                saved_marker = _read_json(self.data_root / 'biomarker-list.json')
                if saved_marker.get('sha256') == self.biomarker_info['sha256']:
                    self.biomarker_info['name'] = saved_marker.get('name', marker_file.name)
                settings.PRONTO_BIOMARKER_GENES = frozenset(self.biomarker_info['genes'])
            # Ephemeral ports are deliberately not remembered (only tests use port 0).
            _write_json(self.config_path, {"data_root": str(self.data_root), "database": str(self.database_path),
                                           "port": self.port or 8770})
            from .shared_installation import publish_locator
            try:
                publish_locator(ROOT, self.data_root, self.database_path)
            except (OSError, ValueError) as error:
                self.startup_warnings.append('Felles databasevalg kunne ikke publiseres i programmappen. '
                    'Områdets forvalter må gi tilgang for førstegangsoppsettet. ' + str(error))
            from .capabilities import PDF_TOOL_HELP
            if not self.capabilities()['pdf']:
                self.startup_warnings.append(PDF_TOOL_HELP)
            connection.close()

    def capabilities(self) -> dict[str, bool]:
        from .capabilities import capabilities
        return capabilities()

    def prepare_empty_database(self, data_root: Path):
        selected = Path(data_root).expanduser().resolve()
        if selected == self.data_root:
            raise ValueError('Velg en annen tom mappe.')
        if selected.exists() and any(selected.iterdir()):
            raise ValueError('Velg en tom mappe for den nye databasen.')
        create_data_directory(selected)
        _write_json(self.config_path, {'data_root': str(selected), 'port': self.port, 'new_database': True})
        return selected

    def set_biomarker_list(self, path: Path):
        from pronto_report.review.biomarker_list import read_biomarker_list
        from django.conf import settings
        import shutil
        result = read_biomarker_list(path)
        target = self.data_root / 'biomarker-list.xlsx'
        if Path(path).resolve() != target.resolve():
            shutil.copyfile(path, target)
        settings.PRONTO_BIOMARKER_GENES = frozenset(result['genes'])
        self.biomarker_info = result
        _write_json(self.data_root / 'biomarker-list.json', result)
        return result

    def save_next_launch(self, data_root: Path, port: int) -> None:
        """Persist a root selection; never switch Django's database in this process."""
        if isinstance(port, bool) or not isinstance(port, int) or not 1024 <= port <= 65535:
            raise ValueError("Port must be between 1024 and 65535.")
        selected = Path(data_root).expanduser().resolve()
        database = selected / "database" / "pronto.sqlite3"
        if selected == ROOT / ".local-web":
            stored = str(self.database_path) if selected == self.data_root else _read_json(selected / "config.json").get("database")
            database = Path(stored) if stored else selected / "pronto.sqlite3"
            if not database.is_absolute():
                database = ROOT / database
        if not database.is_file():
            raise ValueError("Select an existing PRONTO data root. To create a new empty database, "
                             "start once with an explicit --data-root <folder>.")
        _write_json(self.config_path, {"data_root": str(selected), "database": str(database.resolve()), "port": port})

    def has_users(self) -> bool:
        from django.contrib.auth import get_user_model
        return get_user_model().objects.exists()

    def authenticate(self, username: str, password: str):
        from django.contrib.auth import authenticate
        return authenticate(username=username.strip(), password=password)

    def create_user(self, username: str, password: str):
        """First-account bootstrap, without report grants or administrator rights."""
        from django.contrib.auth import get_user_model
        from django.contrib.auth.password_validation import validate_password
        from django.db import transaction
        users = get_user_model()
        user = users(username=username.strip())
        user.full_clean(exclude=["password"], validate_unique=False)
        validate_password(password, user=user)
        # SQLite serializes writes. Grab its write lock before checking empty users,
        # preventing two concurrent desktop starts from creating bootstrap accounts.
        with transaction.atomic():
            from django.db import connection
            with connection.cursor() as cursor:
                table = connection.ops.quote_name(users._meta.db_table)
                cursor.execute(f"UPDATE {table} SET is_active = is_active WHERE 1=0")
            if users.objects.exists():
                raise ValueError("An account already exists. Use the existing account or administrator tools.")
            user.set_password(password)
            user.save()
        return user

    def backup(self) -> Path:
        return backup_sqlite(self.database_path, self.data_root / "backups")

    def report_counts(self) -> dict:
        from pronto_web.reports.models import ReportRecord, ReviewRevision, WorkingDraft
        return {"reports": ReportRecord.objects.count(), "revisions": ReviewRevision.objects.count(),
                "drafts": WorkingDraft.objects.count()}

    def import_history(self, actor) -> list[dict]:
        """Only the native session's active user may see their recent import items."""
        if not actor or not actor.is_authenticated or not actor.is_active:
            return []
        from django.contrib.auth import get_user_model
        from pronto_web.reports.models import ImportItem
        if not get_user_model().objects.filter(pk=actor.pk, is_active=True).exists():
            return []
        items = ImportItem.objects.filter(batch__actor_id=actor.pk).order_by("-created_at")[:100]
        return [{"time": item.created_at.isoformat(), "sample_id": item.sample_id,
                 "run_id": item.run_id, "status": item.status, "message": item.message,
                 "report_id": item.report_id or ""} for item in items]

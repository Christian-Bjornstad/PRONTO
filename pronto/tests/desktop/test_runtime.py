"""Desktop runtime checks use synthetic databases, never the configured local DB."""
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import threading
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[3]


def test_server_lifecycle_health_reuse_and_port_conflict():
    from pronto_desktop.server import LocalServer

    def app(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"synthetic report app"]

    server = LocalServer(app, secret="synthetic-server-secret", database=Path("synthetic.sqlite3"), port=0)
    assert not server.running
    try:
        url = server.start()
        assert server.running and server.owned
        with urlopen(url) as response:
            assert response.read() == b"synthetic report app"
        duplicate = LocalServer(app, secret="synthetic-server-secret", database=Path("synthetic.sqlite3"), port=server.port)
        assert duplicate.start() == url
        assert duplicate.running and not duplicate.owned
        duplicate.stop()
        assert server.running
        stranger = LocalServer(app, secret="different-secret", database=Path("synthetic.sqlite3"), port=server.port)
        with pytest.raises(RuntimeError, match="port|Port"):
            stranger.start()
        with urlopen(f"http://127.0.0.1:{server.port}/__pronto_health__/?challenge=synthetic") as response:
            health = json.load(response)
        assert health["app"] == "PRONTO"
        assert "synthetic.sqlite3" not in json.dumps(health)
        assert "synthetic-server-secret" not in json.dumps(health)
    finally:
        server.stop()
    assert not server.running


def test_server_stop_drains_in_flight_request():
    from pronto_desktop.server import LocalServer
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def app(environ, start_response):
        entered.set()
        assert release.wait(5)
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"saved"]

    server = LocalServer(app, secret="test-drain", database=Path("synthetic.sqlite3"), port=0)
    url = server.start()
    result = []

    def request():
        with urlopen(url, timeout=5) as response:
            result.append(response.read())

    requester = threading.Thread(target=request)
    requester.start()
    assert entered.wait(5)

    def stop():
        server.stop()
        finished.set()

    stopper = threading.Thread(target=stop)
    stopper.start()
    try:
        assert not finished.wait(0.3)
    finally:
        release.set()
        requester.join(5)
        stopper.join(5)
    assert finished.is_set()
    assert result == [b"saved"]


def test_reused_server_running_is_nonblocking_when_health_check_stalls(monkeypatch):
    from pronto_desktop.server import LocalServer

    def app(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain")])
        return [b"synthetic"]

    owner = LocalServer(app, secret="test-cache", database=Path("synthetic.sqlite3"), port=0)
    owner.start()
    reuse = LocalServer(app, secret="test-cache", database=Path("synthetic.sqlite3"), port=owner.port)
    release, finished = threading.Event(), threading.Event()
    reader = None
    result = []
    try:
        reuse.start()
        monkeypatch.setattr(reuse, "_matches_existing", lambda: release.wait(5))

        def read_status():
            result.append(reuse.running)
            finished.set()

        reader = threading.Thread(target=read_status)
        reader.start()
        assert finished.wait(0.3), "Reading GUI status waited for a remote health check"
        assert result == [True]
    finally:
        release.set()
        if reader:
            reader.join(5)
        reuse.stop()
        owner.stop()


def _runtime_script(tmp_path, code):
    env = os.environ.copy()
    env.pop("DJANGO_SETTINGS_MODULE", None)
    for key in list(env):
        if key.startswith("PRONTO_"):
            env.pop(key)
    env["LOCALAPPDATA"] = str(tmp_path / "local-appdata")
    env["PRONTO_TEST_DATA_ROOT"] = str(tmp_path / "data")
    completed = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, text=True, capture_output=True, timeout=60)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return completed.stdout


def test_runtime_new_root_login_backup_restart_and_static(tmp_path):
    result = _runtime_script(tmp_path, r'''
import json, os, sqlite3
from pathlib import Path
from urllib.request import urlopen
from pronto_desktop.runtime import DesktopRuntime
root = Path(os.environ["PRONTO_TEST_DATA_ROOT"])
references = root / "references"
references.mkdir(parents=True)
(references / "GRCh37.fa").write_text(">chr1\nA\n", encoding="ascii")
(references / "GRCh37.fa.fai").write_text("chr1\t1\t6\t1\t2\n", encoding="ascii")
runtime = DesktopRuntime(data_root=root, port=0)
runtime.initialize()
from django.conf import settings
assert set(settings.PRONTO_IGV_REFERENCE_FILES) == {"GRCh37"}
assert settings.PRONTO_IGV_REFERENCE_FILES["GRCh37"]["fasta"] == str(references / "GRCh37.fa")
assert settings.PRONTO_IGV_REFERENCES["GRCh37"]["fastaURL"] == "/igv/references/GRCh37/fasta/"
assert runtime.database_path == root / "database" / "pronto.sqlite3"
assert runtime.raw_root.is_dir()
assert not runtime.has_users()
try:
    runtime.create_user("reviewer", "short")
except Exception:
    pass
else:
    raise AssertionError("Weak password was accepted")
user = runtime.create_user("reviewer", "Synthetic+Passphrase987!")
assert not user.is_superuser and not user.is_staff
assert runtime.has_users()
assert runtime.authenticate("reviewer", "Synthetic+Passphrase987!").pk == user.pk
assert runtime.authenticate("reviewer", "wrong") is None
try:
    runtime.create_user("second", "Synthetic+Passphrase987!")
except ValueError:
    pass
else:
    raise AssertionError("Second user should require administrator tooling")
backup = runtime.backup()
assert backup.is_file() and backup != runtime.database_path
with sqlite3.connect(backup) as connection:
    assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    assert connection.execute("SELECT username FROM auth_user").fetchone() == ("reviewer",)
assert runtime.report_counts()["reports"] == 0
from django.contrib.auth import get_user_model
from pronto_web.reports.models import ImportBatch, ImportItem
other = get_user_model().objects.create_user(username="other", password="Synthetic+Passphrase987!")
my_batch = ImportBatch.objects.create(actor=user)
other_batch = ImportBatch.objects.create(actor=other)
ImportItem.objects.create(batch=my_batch, sample_id="my-synthetic-sample", run_id="synthetic-run", status="failed", message="synthetic")
ImportItem.objects.create(batch=other_batch, sample_id="other-sample", run_id="synthetic-run", status="failed")
assert [item["sample_id"] for item in runtime.import_history(user)] == ["my-synthetic-sample"]
assert runtime.import_history(None) == []
try:
    url = runtime.server.start()
    with urlopen(url) as response:
        assert response.status == 200
    with urlopen(f"http://127.0.0.1:{runtime.port}/static/igv/igv.esm.min.js") as response:
        assert response.status == 200
finally:
    runtime.server.stop()
second = DesktopRuntime(data_root=root, port=0)
second.initialize()
assert second.has_users()
try:
    DesktopRuntime(data_root=root.parent / "different", port=0).initialize()
except RuntimeError as exc:
    assert "restart" in str(exc).lower()
else:
    raise AssertionError("Django database switched in-process")
print("synthetic-runtime-ok")
''')
    assert "synthetic-runtime-ok" in result


def test_remembered_database_missing_does_not_create_replacement(tmp_path):
    _runtime_script(tmp_path, r'''
import json, os
from pathlib import Path
from pronto_desktop.runtime import DesktopRuntime
root = Path(os.environ["PRONTO_TEST_DATA_ROOT"])
prefs = Path(os.environ["LOCALAPPDATA"]) / "PRONTO" / "desktop.json"
prefs.parent.mkdir(parents=True)
prefs.write_text(json.dumps({"data_root": str(root), "port": 8771}), encoding="utf8")
try:
    DesktopRuntime().initialize()
except RuntimeError as exc:
    assert "unavailable" in str(exc).lower()
else:
    raise AssertionError("A remembered missing database was silently recreated")
assert not root.exists()
''')


def test_existing_database_is_backed_up_before_pending_migration(tmp_path):
    _runtime_script(tmp_path, r'''
import os, sqlite3
from pathlib import Path
from pronto_desktop.runtime import DesktopRuntime
root = Path(os.environ["PRONTO_TEST_DATA_ROOT"])
db = root / "database" / "pronto.sqlite3"
db.parent.mkdir(parents=True)
with sqlite3.connect(db) as conn:
    conn.execute("CREATE TABLE synthetic_source (value TEXT)")
    conn.execute("INSERT INTO synthetic_source VALUES ('preserved')")
runtime = DesktopRuntime(data_root=root, port=0)
runtime.initialize()
backups = list((root / "backups").glob("*.sqlite3"))
assert len(backups) == 1
with sqlite3.connect(backups[0]) as conn:
    assert conn.execute("SELECT value FROM synthetic_source").fetchone() == ("preserved",)
    assert not conn.execute("SELECT name FROM sqlite_master WHERE name='auth_user'").fetchall()
with sqlite3.connect(db) as conn:
    assert conn.execute("SELECT value FROM synthetic_source").fetchone() == ("preserved",)
    assert conn.execute("SELECT name FROM sqlite_master WHERE name='auth_user'").fetchone()
''')


def test_felles_start_does_not_inherit_host_arguments(tmp_path, monkeypatch):
    import start_python_felles
    monkeypatch.setattr(sys, "argv", ["host-shell", "--host-private-flag"])
    received = []
    start_python_felles.start(project_dir=ROOT, user_site=tmp_path,
                             app_main=lambda args: received.append(args))
    assert received == [[]]


def test_felles_install_uses_current_interpreter_and_pinned_requirements(tmp_path, monkeypatch):
    import install_python_felles
    monkeypatch.setattr(sys, "prefix", sys.base_prefix)
    calls = []
    imported = []
    install_python_felles.install(project_dir=ROOT, user_site=tmp_path,
                                 pip_main=lambda args: calls.append(args), importer=imported.append)
    assert calls == [["install", "--user", "--disable-pip-version-check", "-r", str(ROOT / "requirements-desktop.txt")]]
    assert "PyQt6.QtWidgets" in imported


def test_installer_reports_missing_poppler_instead_of_claiming_complete(tmp_path, monkeypatch):
    import install_python_felles
    import shutil
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="Poppler"):
        install_python_felles.install(project_dir=ROOT, user_site=tmp_path,
                                      pip_main=lambda args: 0, importer=lambda name: None)


def test_backup_includes_committed_wal_data(tmp_path):
    from pronto_desktop.runtime import backup_sqlite
    database = tmp_path / "source.sqlite3"
    with sqlite3.connect(database) as source:
        source.execute("PRAGMA journal_mode=WAL")
        source.execute("CREATE TABLE synthetic (value TEXT)")
        source.execute("INSERT INTO synthetic VALUES ('committed-in-wal')")
        source.commit()
        backup = backup_sqlite(database, tmp_path / "backups")
        with sqlite3.connect(backup) as target:
            assert target.execute("SELECT value FROM synthetic").fetchone() == ("committed-in-wal",)
            assert target.execute("PRAGMA integrity_check").fetchone() == ("ok",)


def test_legacy_launcher_database_and_key_selection_are_preserved(tmp_path):
    _runtime_script(tmp_path, r'''
import json, os, sqlite3
from pathlib import Path
import scripts.start_web as launcher
import pronto_desktop.runtime as module
root = Path(os.environ["PRONTO_TEST_DATA_ROOT"])
state = root / ".local-web"
state.mkdir(parents=True)
database = root / "existing-persisted.sqlite3"
with sqlite3.connect(database) as connection:
    connection.execute("CREATE TABLE synthetic_source (value TEXT)")
    connection.execute("INSERT INTO synthetic_source VALUES ('preserved')")
key = "synthetic-preserved-key-" * 4
(state / "secret.key").write_text(key, encoding="utf8")
(state / "config.json").write_text(json.dumps({"database":str(database),"port":8779,"custom":"preserved"}), encoding="utf8")
module.ROOT = launcher.ROOT = root
launcher.STATE = state
runtime = module.DesktopRuntime()
runtime.initialize()
assert runtime.database_path == database
assert runtime.port == 8779
assert (state / "secret.key").read_text(encoding="utf8") == key
assert json.loads((state / "config.json").read_text(encoding="utf8"))["custom"] == "preserved"
assert not (state / "pronto.sqlite3").exists()
with sqlite3.connect(database) as connection:
    assert connection.execute("SELECT value FROM synthetic_source").fetchone() == ("preserved",)
''')

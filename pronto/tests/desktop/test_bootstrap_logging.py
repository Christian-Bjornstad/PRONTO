import sqlite3
from pathlib import Path


def test_bootstrap_log_prints_existing_path_and_explorer_location(tmp_path, monkeypatch, capsys):
    import install_python_felles as bootstrap
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'profile'))
    path = bootstrap.record_failure('start', sqlite3.OperationalError('invalid uri authority: files.example'))
    assert path.is_file()
    assert 'invalid uri authority' in path.read_text(encoding='utf-8')
    output = capsys.readouterr().out
    assert str(path) in output and str(path.parent) in output
    assert 'Filutforsker' in output


def test_bootstrap_log_falls_back_when_profile_is_unwritable(tmp_path, monkeypatch, capsys):
    import install_python_felles as bootstrap
    blocked = tmp_path / 'not-a-folder'
    blocked.write_text('keep')
    monkeypatch.setenv('LOCALAPPDATA', str(blocked))
    monkeypatch.setattr(bootstrap.tempfile, 'gettempdir', lambda: str(tmp_path / 'temp'))
    path = bootstrap.record_failure('start', RuntimeError('synthetic failure'))
    assert path.is_file() and path.is_relative_to(tmp_path / 'temp')
    assert 'synthetic failure' in path.read_text(encoding='utf-8')
    assert blocked.read_text() == 'keep'


def test_start_does_not_prescribe_dependency_reinstall_for_database_errors(monkeypatch, capsys):
    import start_python_felles as launcher
    monkeypatch.setattr(launcher.sys, 'prefix', 'venv')
    monkeypatch.setattr(launcher.sys, 'base_prefix', 'base')
    monkeypatch.setattr(launcher.sys, 'version_info', (3, 14))
    def fail(**kwargs):
        raise sqlite3.OperationalError('invalid uri authority: files.example')
    monkeypatch.setattr(launcher, 'start', fail)
    monkeypatch.setitem(launcher._helpers, 'record_failure', lambda *args: None)
    assert launcher.main() == 1
    output = capsys.readouterr().out
    assert 'PRONTO_INSTALL.cmd' not in output
    assert 'database' in output.lower()

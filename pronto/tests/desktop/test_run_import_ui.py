import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QInputDialog

from pronto.tests.desktop.test_gui import window
from pronto.tests.ingest.test_actual_run_discovery import actual_run,RUN


def test_date_lookup_builds_same_plan_and_saves_only_source_root(window,actual_run,qtbot,monkeypatch):
    saved=[]
    monkeypatch.setattr(window.runtime,'save_import_preferences',lambda root:saved.append(root),raising=False)
    window.navigate(1)
    window.import_mode.setCurrentIndex(0)
    window.run_root.setText(str(actual_run['raw'].parent))
    window.run_query.setText('261001')
    qtbot.mouseClick(window.scan_button,Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda:window.plan is not None,timeout=10000)
    assert window.plan.run_ids==(RUN,)
    assert window.plan.reports[0].ready
    assert saved==[actual_run['raw'].parent]
    assert window.runtime.saved is None
    assert sum(bool(field.text()) for field in window.folder_fields)==4


def test_ambiguous_date_cancel_never_starts_import(window,tmp_path,qtbot,monkeypatch):
    for run in ('261001_A00001_0001_AAAAAAAAA','261001_B00001_0002_BBBBBBBBB'):
        (tmp_path/run).mkdir()
    calls=[]
    monkeypatch.setattr(QInputDialog,'getItem',lambda *args:(calls.append(args[3]) or '',False))
    window.navigate(1);window.import_mode.setCurrentIndex(0)
    window.run_root.setText(str(tmp_path));window.run_query.setText('261001')
    qtbot.mouseClick(window.scan_button,Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda:bool(calls),timeout=5000)
    assert len(calls[0])==2 and window.plan is None
    assert not window.import_button.isEnabled()


def test_source_preferences_do_not_modify_database_selection(tmp_path,monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'profile'))
    from pronto_desktop.runtime import DesktopRuntime
    profile=tmp_path/'profile'/'PRONTO'/'desktop.json'
    profile.parent.mkdir(parents=True)
    original=json.dumps({'data_root':str(tmp_path/'existing'), 'database':str(tmp_path/'existing'/'chosen.sqlite3'),'port':8773})
    profile.write_text(original)
    runtime=DesktopRuntime(data_root=tmp_path/'data')
    runtime.save_import_preferences(tmp_path/'run-sources')
    assert profile.read_text()==original
    assert runtime.import_preferences()=={'source_root':str((tmp_path/'run-sources').resolve())}
    assert not runtime.database_path.exists()

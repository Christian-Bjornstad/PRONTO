"""A real private database and HTTP server exercise the complete app boundary."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('layout', ['legacy', 'actual'])
def test_run_to_authenticated_saved_report_and_exports(tmp_path, layout):
    root = Path(__file__).resolve().parents[3]
    environment = dict(os.environ)
    for name in ('DJANGO_SETTINGS_MODULE', 'PRONTO_DJANGO_DB', 'PRONTO_DJANGO_SECRET_KEY'):
        environment.pop(name, None)
    environment['LOCALAPPDATA'] = str(tmp_path / 'profile')
    script = r'''
import http.cookiejar
import hashlib
import json
from pathlib import Path
import re
import shutil
import socket
import sys
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from urllib.error import HTTPError
from uuid import uuid4

from pronto_desktop.runtime import DesktopRuntime
from pronto_ingest.discovery import discover_folders, set_report_selected
from pronto_ingest.importer import import_plan

target = Path(sys.argv[1])
layout = sys.argv[2]
root = Path.cwd()
fixture = root / 'test_data/ous/251114_A02134_0115_BHCJCKDRX7_TSO_500_LocalApp_postprocessing_results'
if layout == 'actual':
    from scripts.create_desktop_example import create_example, SAMPLE
    create_example(target / 'sources')
    folders = [target / 'sources']
    sample = SAMPLE
else:
    sample = 'IPD2225-D01-P01-A08'
    folders = [target / 'sources' / str(n) for n in range(5)]
    for directory in folders:
        directory.mkdir(parents=True)
    shutil.copy2(fixture / 'InPreD_PRONTO_metadata.txt', folders[0])
    shutil.copy2(next(fixture.glob('*_variant_summary.tsv')), folders[1])
    for path in (fixture / sample).iterdir():
        if path.name.endswith('_small_variant_table_forQC.tsv') or path.name == 'sample_list.tsv':
            shutil.copy2(path, folders[2] / path.name)
        elif path.suffix == '.png' or path.name.endswith('_CNV_overview_plots.pdf'):
            shutil.copy2(path, folders[3] / path.name)
source_hashes = {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in (target / 'sources').rglob('*') if path.is_file()}
with socket.socket() as sock:
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
runtime = DesktopRuntime(data_root=target / 'private', port=port)
runtime.initialize()
user = runtime.create_user('handover-operator', 'Synthetic-workstation-password!742')
plan = discover_folders(folders)
assert len(plan.reports) == 1
assert plan.reports[0].ready, plan.reports[0].issues
if layout == 'actual':
    assert plan.profile == 'tsoppi-run-v1'
    assert not plan.reports[0].selected
    try:
        import_plan(plan, user, runtime.raw_root)
    except ValueError:
        pass
    else:
        raise AssertionError('Unselected metadata must not import')
    plan = set_report_selected(plan, plan.reports[0].key, True)
result = import_plan(plan, user, runtime.raw_root)
assert [item.status for item in result.items] == ['imported'], result
again = import_plan(plan, user, runtime.raw_root)
assert [item.status for item in again.items] == ['already_imported']
assert source_hashes == {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in (target / 'sources').rglob('*') if path.is_file()}
report_id = result.items[0].report_id
jar = http.cookiejar.CookieJar()
client = build_opener(HTTPCookieProcessor(jar))
url = runtime.server.start()
base = url.split('/reports/')[0].rstrip('/')
def get(path):
    return client.open(base + path, timeout=30).read()
def csrf():
    return next(cookie.value for cookie in jar if cookie.name == 'csrftoken')
def post(path, payload):
    request = Request(base + path, data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'X-CSRFToken': csrf()}, method='POST')
    try:
        response = client.open(request, timeout=30)
    except HTTPError as error:
        return error.code, error.read()
    return response.status, response.read()
try:
    get('/accounts/login/')
    login = urlencode({'username':user.username, 'password':'Synthetic-workstation-password!742',
                       'csrfmiddlewaretoken':csrf()}).encode()
    client.open(Request(base + '/accounts/login/', data=login), timeout=30).read()
    html = get('/reports/' + report_id + '/').decode()
    assert sample in html
    def embedded(name):
        return json.loads(re.search(r'<script[^>]*id="' + name + r'"[^>]*>(.*?)</script>', html, re.S)[1])
    draft, config = embedded('review-state-data'), embedded('working-config')
    marker = 'Verified desktop import and saved report'
    draft['notes']['summary'] = marker
    command = {'schemaVersion':'2.0','reportId':report_id,'action':'SAVE',
               'baseRevision':config['revision'],'expectedVersion':config['version'],'draft':draft}
    route = '/reports/' + report_id + '/'
    status, body = post(route + 'working/', command)
    assert status == 201, (status, body)
    saved = json.loads(body)
    assert post(route + 'working/', command)[0] == 409
    final_command = {'schemaVersion':'2.0','reportId':report_id,'action':'FINALIZE',
                     'baseRevision':saved['review']['revision'],'expectedVersion':saved['workingVersion']}
    status, body = post(route + 'working/', final_command)
    assert status == 201, (status, body)
    final = json.loads(body)['review']
    assert final['status'] == 'FINAL'
    assert marker.encode() in get(route + '?revision=' + str(final['revision']))
    for layout in ('ESMO','PRESENTATION'):
        status, payload = post(route + 'pdf-exports/', {'schemaVersion':'1.0','reportId':report_id,
            'revision':final['revision'],'requestId':str(uuid4()),'layout':layout})
        assert status == 200 and payload.startswith(b'%PDF'), (status, payload[:100])
    status, payload = post(route + 'html-exports/', {'schemaVersion':'1.0','reportId':report_id,
        'revision':final['revision'],'requestId':str(uuid4()),'declaredInitials':'QA'})
    assert status == 200 and marker.encode() in payload
    backup = runtime.backup()
    assert backup.is_file()
finally:
    runtime.server.stop()
assert not runtime.server.running
print('DESKTOP_PIPELINE_OK')
'''
    completed = subprocess.run([sys.executable, '-c', script, str(tmp_path), layout], cwd=root,
                               env=environment, capture_output=True, text=True, timeout=180)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert 'DESKTOP_PIPELINE_OK' in completed.stdout

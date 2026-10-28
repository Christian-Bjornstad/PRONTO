from pathlib import Path

import pytest

from pronto_ingest.run_lookup import find_runs, run_query

RUN='261021_A02134_0177_AHVLFCDRX7'


@pytest.mark.parametrize('value',['261021','20261021','2026-10-21',RUN])
def test_run_query_formats(value):
    assert run_query(value)==(RUN if value==RUN else '261021')


@pytest.mark.parametrize('value',['261032','2026-02-30','2610','../261021','261021*',''])
def test_invalid_queries_are_rejected(value):
    with pytest.raises(ValueError): run_query(value)


def test_finds_run_families_but_never_descends_patient_directories(tmp_path):
    for suffix in ('','_CNVs','_report_preQC','_report_preQC_newPRONTO_version','_report_withQC'):
        (tmp_path/'2026'/(RUN+suffix)).mkdir(parents=True)
    (tmp_path/'2026'/RUN/'patient'/'261021_B00001_0001_BBBBBBBBB').mkdir(parents=True)
    found=find_runs(tmp_path,'261021')
    assert len(found)==1 and found[0].run_id==RUN
    assert len(found[0].folders)==5
    assert all(path.parent==tmp_path/'2026' for path in found[0].folders)


def test_date_ambiguity_is_returned_as_separate_runs(tmp_path):
    for run in (RUN,'261021_B00001_0002_BBBBBBBBB'):
        (tmp_path/run).mkdir()
    found=find_runs(tmp_path,'2026-10-21')
    assert len(found)==2
    assert len(find_runs(tmp_path,RUN))==1


def test_same_run_in_two_locations_is_not_merged(tmp_path):
    for parent in ('current','copy'):
        (tmp_path/parent/RUN).mkdir(parents=True)
    with pytest.raises(ValueError,match='flere'):
        find_runs(tmp_path,'261021')


def test_max_depth_and_cancel(tmp_path):
    (tmp_path/'one'/'two'/'three'/'four'/RUN).mkdir(parents=True)
    with pytest.raises(ValueError,match='Fant ingen'):
        find_runs(tmp_path,'261021')
    from pronto_ingest.contracts import ImportCancelled
    with pytest.raises(ImportCancelled):
        find_runs(tmp_path,'261021',cancel=lambda:True)


def test_requires_raw_folder_not_just_a_report_copy(tmp_path):
    (tmp_path/(RUN+'_report_withQC')).mkdir()
    with pytest.raises(ValueError,match='rådata'):
        find_runs(tmp_path,'261021')


def test_denied_subfolder_cannot_make_a_date_seem_unique(tmp_path,monkeypatch):
    import pronto_ingest.run_lookup as lookup
    (tmp_path/RUN).mkdir();denied=tmp_path/'denied';denied.mkdir()
    scan=lookup.os.scandir
    def inaccessible(path):
        if Path(path)==denied: raise PermissionError('Access denied')
        return scan(path)
    monkeypatch.setattr(lookup.os,'scandir',inaccessible)
    with pytest.raises(ValueError,match='lesetilgang'):
        find_runs(tmp_path,'261021')


def test_directory_link_is_not_followed(tmp_path,monkeypatch):
    import pronto_ingest.run_lookup as lookup
    legitimate=tmp_path/RUN;legitimate.mkdir()
    link=tmp_path/'linked';(link/'261021_B00001_0002_BBBBBBBBB').mkdir(parents=True)
    safe=lookup._safe_directory
    monkeypatch.setattr(lookup,'_safe_directory',lambda path:path!=link and safe(path))
    assert [run.run_id for run in find_runs(tmp_path,'261021')]==[RUN]

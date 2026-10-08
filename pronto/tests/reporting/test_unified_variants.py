from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto_report.migration import migrate_review_state_to_v3
from pronto_report.renderers.html import render_html


def test_modern_variants_are_one_table_with_all_source_headers_and_no_details():
    report = build_report()
    html = render_html(report, migrate_review_state_to_v3(draft_review(report)))
    assert '<summary>Details</summary>' not in html
    assert 'All source columns' not in html
    assert '<th scope="col">Genomic location</th>' in html
    assert '<th scope="col">Review comment</th>' in html
    for table in report.source_tables:
        if table['kind'] == 'VARIANTS':
            for header in table['headers']:
                from html import escape
                assert f'<th scope="col">{escape(header)}</th>' in html


def test_source_columns_join_by_occurrence_and_keep_each_table_separate():
    from dataclasses import replace
    from pronto_report.renderers.variant_columns import columns, values
    report = build_report()
    duplicates = [v for v in report.variants if v['gene'] == 'TERT']
    assert duplicates[0]['variantId'] == duplicates[1]['variantId']
    tables = tuple({'kind':'VARIANTS', 'tableId':name, 'headers':['Transcript source'], 'rows':[
        {'occurrenceId':v['occurrenceId'], 'values':[f'{name}-{index}']}
        for index,v in enumerate(duplicates)]} for name in ('first', 'second'))
    report = replace(report, source_tables=tables)
    source_indices = [i for i,(kind,_,_) in enumerate(columns(report)) if kind == 'source']
    for index,variant in enumerate(duplicates):
        row = values(report, variant)
        assert [row[i] for i in source_indices] == [f'first-{index}', f'second-{index}']


def test_signature_selection_is_inside_metric_cards_and_not_a_separate_list():
    from html.parser import HTMLParser
    report = build_report()
    html = render_html(report, migrate_review_state_to_v3(draft_review(report)))
    class Metrics(HTMLParser):
        def __init__(self):
            super().__init__(); self.metric = None; self.selected = {}
        def handle_starttag(self,tag,attrs):
            attrs = dict(attrs)
            if tag == 'article': self.metric = attrs.get('data-metric')
            if 'data-metric-highlight' in attrs:
                self.selected[attrs['data-metric-highlight']] = self.metric
        def handle_endtag(self,tag):
            if tag == 'article': self.metric = None
    parsed = Metrics(); parsed.feed(html)
    assert parsed.selected == {item['metricId']:item['metricId'] for item in report.biomarkers
                               if item['metricId'] in {'tmb','msi','hrd'}}
    assert '<div class="signature-highlights">' not in html

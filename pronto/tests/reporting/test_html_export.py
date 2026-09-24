from dataclasses import replace
from hashlib import sha256

import pytest

from pronto.tests.reporting.test_html_surfaces import ONE_PIXEL_PNG
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto.tests.reporting.test_html_review_state import draft_review
from pronto_report.cli import main
from pronto_report.renderers.html import render_html
from pronto_report.migration import migrate_review_state_v1
from pronto_report.serialization import serialize_report_data, serialize_review_state
from pronto_report.renderers.assets import load_plot_images


def test_self_contained_html_inlines_assets_and_is_deterministic():
    report = build_report()
    first = render_html(report, inline_assets=True)
    second = render_html(report, inline_assets=True)

    assert first == second
    assert '<style>' in first
    assert '<script>' in first
    assert 'Content-Security-Policy' in first
    assert '/pronto_report/static/report.css' not in first
    assert '/pronto_report/static/report.js' not in first
    assert '<script src=' not in first
    assert "Kilde og proveniens" in first
    assert report.schema_version in first
    assert report.provenance["generator"]["version"] in first
    assert report.provenance["sourceFiles"][0]["sha256"] in first


def test_asset_loader_verifies_declared_png_hash(tmp_path):
    report = build_report()
    asset = dict(next(item for item in report.attachments if item["mediaType"] == "image/png"))
    asset["name"] = "sample/qc.png"
    asset["sha256"] = sha256(ONE_PIXEL_PNG).hexdigest()
    report = replace(report, attachments=(asset,))
    path = tmp_path / "sample" / "qc.png"
    path.parent.mkdir()
    path.write_bytes(ONE_PIXEL_PNG)

    images = load_plot_images(report, tmp_path)
    assert images[asset["assetId"]] == (("image/png", ONE_PIXEL_PNG),)

    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        load_plot_images(report, tmp_path)


def test_asset_loader_rejects_path_escape(tmp_path):
    report = build_report()
    asset = dict(report.attachments[0])
    asset["name"] = "../outside.pdf"
    report = replace(report, attachments=(asset,))

    with pytest.raises(ValueError, match="path"):
        load_plot_images(report, tmp_path)


def test_cli_exports_a_self_contained_html_from_validated_report_data(tmp_path):
    input_path = tmp_path / "report-data.json"
    output_path = tmp_path / "report.html"
    input_path.write_bytes(serialize_report_data(replace(build_report(), attachments=())))

    assert main(["render-html", str(input_path), "--output", str(output_path)]) == 0
    html = output_path.read_text(encoding="utf-8")
    assert "14,9 mut/Mb" in html
    assert "report_c5cb34a7fdde3b9d3974c102" in html
    assert '<style>' in html
    first_bytes = output_path.read_bytes()
    assert main(["render-html", str(input_path), "--output", str(output_path)]) == 0
    assert output_path.read_bytes() == first_bytes


def test_cli_requires_all_declared_plot_assets(tmp_path):
    input_path = tmp_path / "report-data.json"
    input_path.write_bytes(serialize_report_data(build_report()))

    with pytest.raises(FileNotFoundError):
        main(["render-html", str(input_path), "--output", str(tmp_path / "report.html")])


def test_read_only_snapshot_keeps_revision_and_notes_without_edit_controls():
    report = replace(build_report(), attachments=())
    review = draft_review(report)
    first = render_html(report, review, inline_assets=True, snapshot=True)
    assert first == render_html(report, review, inline_assets=True, snapshot=True)
    assert f"Revisjon {review.revision}" in first
    assert 'data-review-note=' not in first
    assert '<select aria-label=' not in first
    assert '<textarea' not in first
    assert '<button id="edit-btn"' not in first
    assert '<button id="save-btn"' not in first
    assert '<button id="download-review"' not in first
    assert '<script type="application/json" id="review-state-data"' not in first
    assert 'class="board-note-readonly"' in first
    assert 'Content-Security-Policy' in first


def test_snapshot_requires_embedded_assets():
    with pytest.raises(ValueError, match="inline_assets"):
        render_html(build_report(), snapshot=True)


def test_snapshot_escapes_review_notes_as_text():
    report = replace(build_report(), attachments=())
    review = migrate_review_state_v1(draft_review(report))
    review = replace(review, notes={**review.notes, "summary": '<script>alert("x")</script>'})
    html = render_html(report, review, inline_assets=True, snapshot=True)
    assert '&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;' in html
    assert '<script>alert("x")</script>' not in html


def test_cli_exports_read_only_saved_revision(tmp_path):
    report = replace(build_report(), attachments=())
    review = draft_review(report)
    report_path = tmp_path / "report-data.json"
    review_path = tmp_path / "review-state.json"
    output_path = tmp_path / "report.html"
    report_path.write_bytes(serialize_report_data(report))
    review_path.write_bytes(serialize_review_state(review))
    args = ["render-html", str(report_path), "--review", str(review_path), "--output", str(output_path)]
    assert main(args) == 0
    first = output_path.read_bytes()
    assert b'id="save-btn"' not in first
    assert f"Revisjon {review.revision}".encode() in first
    assert main(args) == 0
    assert output_path.read_bytes() == first

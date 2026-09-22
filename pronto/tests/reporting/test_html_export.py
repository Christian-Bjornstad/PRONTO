from dataclasses import replace
from hashlib import sha256

import pytest

from pronto.tests.reporting.test_html_surfaces import ONE_PIXEL_PNG
from pronto.tests.reporting.test_pronto_output_adapter import build_report
from pronto_report.cli import main
from pronto_report.renderers.html import render_html
from pronto_report.serialization import serialize_report_data
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

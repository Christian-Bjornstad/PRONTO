"""Command-line entry points for contract validation and fixture export."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path

from pronto_report.adapters.pronto_output import adapt_pronto_output
from pronto_report.renderers.assets import load_plot_images
from pronto_report.renderers.html import render_html
from pronto_report.serialization import (
    deserialize_report_data,
    deserialize_review_state,
    serialize_report_data,
)


_REPOSITORY_ROOT = Path(__file__).parents[1]
_APPROVED_FIXTURES = {
    "ous": {
        "root": _REPOSITORY_ROOT
        / "test_data"
        / "ous"
        / "251114_A02134_0115_BHCJCKDRX7_TSO_500_LocalApp_postprocessing_results",
        "sample_id": "IPD2225-D01-P01-A08",
    }
}


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pronto-report")
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Export an approved fixture")
    export.add_argument("--fixture", choices=sorted(_APPROVED_FIXTURES), required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--generated-at", default=None)
    export.add_argument("--generator-version", default="1.0.0")
    html = commands.add_parser("render-html", help="Render an offline HTML report")
    html.add_argument("report_data", type=Path)
    html.add_argument("--output", type=Path, required=True)
    html.add_argument("--review", type=Path)
    html.add_argument("--asset-root", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the report-contract command line interface."""
    arguments = _parser().parse_args(argv)
    if arguments.command == "export":
        fixture = _APPROVED_FIXTURES[arguments.fixture]
        report = adapt_pronto_output(
            fixture["root"],
            sample_id=fixture["sample_id"],
            generated_at=arguments.generated_at or _timestamp_now(),
            generator_version=arguments.generator_version,
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_bytes(serialize_report_data(report))
        return 0
    if arguments.command == "render-html":
        report = deserialize_report_data(arguments.report_data.read_bytes())
        review = (
            deserialize_review_state(arguments.review.read_bytes(), report=report)
            if arguments.review else None
        )
        asset_root = arguments.asset_root or arguments.report_data.parent
        plots = load_plot_images(report, asset_root)
        rendered = render_html(report, review, plot_images=plots, inline_assets=True)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_bytes(rendered.encode("utf-8"))
        return 0
    raise AssertionError("Unknown command")


if __name__ == "__main__":
    raise SystemExit(main())

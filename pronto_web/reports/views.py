"""Authorize first, then validate and render the latest stored snapshot."""

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from pronto_report.renderers.assets import load_plot_images_from_bytes
from pronto_report.renderers.html import render_html
from pronto_report.validation import validate_report_data, validate_review_state
from pronto_web.reports.models import ReportGrant, ReportRecord, ReviewRevision


@require_GET
def report_index(request) -> HttpResponse:
    if not request.user.is_authenticated or not request.user.is_active:
        return HttpResponse(status=401)
    reports = ReportRecord.objects.filter(grants__user=request.user).order_by("report_id")
    response = render(request, "reports/index.html", {"reports": reports})
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def report_detail(request, report_id: str) -> HttpResponse:
    if not request.user.is_authenticated or not request.user.is_active:
        return HttpResponse(status=401)
    grant = get_object_or_404(
        ReportGrant.objects.select_related("report"),
        report_id=report_id,
        user=request.user,
    )
    record = grant.report
    report = validate_report_data(record.report_data)
    if report.report_id != record.report_id:
        raise ValueError("Stored report identifier does not match its record")
    latest = ReviewRevision.objects.filter(report=record).order_by("-revision").first()
    review = validate_review_state(latest.review_data, report=report) if latest else None
    if latest is not None and review.revision != latest.revision:
        raise ValueError("Stored review revision does not match its record")
    blobs = {asset.asset_id: bytes(asset.content) for asset in record.assets.all()}
    plot_images = load_plot_images_from_bytes(report, blobs)
    html = render_html(report, review, plot_images=plot_images, inline_assets=True, snapshot=True)
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-store"
    return response

"""Authorize first, then validate and render the latest stored snapshot."""

from django.http import HttpResponse, StreamingHttpResponse
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from pronto_report.renderers.assets import load_plot_images_from_bytes
from pronto_report.renderers.html import render_html
from pronto_report.validation import validate_report_data, validate_review_state
from pronto_web.reports.models import ReportGrant, ReportRecord, ReviewRevision
from pronto_web.reports.alignment_ranges import RangeNotSatisfiable, iter_range, parse_single_range
from pronto_web.reports.alignment_registry import InvalidAlignmentRegistry, lookup_registered
import os


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
    try:
        pairs = lookup_registered(record.report_id, str(report.sample["sampleId"]), str(report.sample["referenceBuild"]))
    except InvalidAlignmentRegistry:
        pairs = ()
        registry_error = True
    else:
        registry_error = False
    sources = tuple({
        "sourceId": pair.source_id, "role": pair.role, "format": pair.format,
        "referenceBuild": pair.reference_build,
        "dataURL": f"/reports/{record.report_id}/alignments/{pair.source_id}/data/",
        "indexURL": f"/reports/{record.report_id}/alignments/{pair.source_id}/index/",
    } for pair in pairs)
    references = {build: value for build, value in settings.PRONTO_IGV_REFERENCES.items()
                  if all(value.values())}
    html = render_html(report, review, plot_images=plot_images, inline_assets=True,
                       snapshot=True, web_igv=True, igv_sources=sources, igv_references=references,
                       igv_registry_error=registry_error)
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-store"
    return response


@require_GET
def alignment_component(request, report_id: str, source_id: str, component: str) -> HttpResponse:
    if not request.user.is_authenticated or not request.user.is_active:
        return HttpResponse(status=401)
    grant = get_object_or_404(
        ReportGrant.objects.select_related("report"), report_id=report_id, user=request.user,
    )
    if component not in {"data", "index"}:
        return HttpResponse(status=404)
    record = grant.report
    report = validate_report_data(record.report_data)
    if report.report_id != record.report_id:
        return HttpResponse(status=404)
    try:
        pair = next((pair for pair in lookup_registered(
            report_id, str(report.sample["sampleId"]), str(report.sample["referenceBuild"]),
        ) if pair.source_id == source_id), None)
    except InvalidAlignmentRegistry:
        return HttpResponse(status=404)
    if pair is None:
        return HttpResponse(status=404)
    path = pair.data_path if component == "data" else pair.index_path
    try:
        handle = path.open("rb")
        size = os.fstat(handle.fileno()).st_size
    except OSError:
        return HttpResponse(status=404)
    try:
        if not request.headers.get("Range"):
            if component == "data" or size > 8 * 1024 * 1024:
                raise RangeNotSatisfiable("range required")
            start, end = 0, size - 1
            status = 200
        else:
            start, end = parse_single_range(request.headers["Range"], size)
            status = 206
    except RangeNotSatisfiable:
        handle.close()
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{size}"
        response["Accept-Ranges"] = "bytes"
        response["Cache-Control"] = "no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
    response = StreamingHttpResponse(
        iter_range(handle, start, end) if size else iter_range(handle, 0, -1),
        status=status, content_type="application/octet-stream",
    )
    if status == 206:
        response["Content-Range"] = f"bytes {start}-{end}/{size}"
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(end - start + 1)
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response

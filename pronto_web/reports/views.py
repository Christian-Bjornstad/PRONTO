"""Authorize first, then validate and render or save report review snapshots."""

import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from pronto_report.renderers.assets import load_plot_images_from_bytes
from pronto_report.renderers.html import render_html
from pronto_report.review.contracts import FinalizeRequest, ReviewCommandError, SaveDraftRequest
from pronto_report.review.service import ReviewCommandService
from pronto_report.validation import validate_report_data, validate_review_state
from pronto_web.reports.models import ReportGrant, ReportRecord, ReviewRevision
from pronto_web.reports.review_repository import DjangoReviewAuthorizer, DjangoReviewRepository


MAX_REVIEW_COMMAND_BYTES = 1024 * 1024


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
    html = render_html(
        report, review, plot_images=plot_images, inline_assets=True,
        save_url=reverse("review-save", args=[record.report_id]) if review and review.status == "DRAFT" else None,
        finalize_url=reverse("review-finalize", args=[record.report_id]) if review and review.status == "DRAFT" else None,
        csrf_token=get_token(request) if review and review.status == "DRAFT" else None,
        actor_id=str(request.user.pk) if review and review.status == "DRAFT" else None,
    )
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "no-store"
    return response


def _command_request(request, command_type):
    if request.content_type != "application/json":
        raise ReviewCommandError("INVALID_COMMAND", "JSON command required", 422)
    size = request.META.get("CONTENT_LENGTH", "")
    if size.isdecimal() and int(size) > MAX_REVIEW_COMMAND_BYTES:
        raise ReviewCommandError("PAYLOAD_TOO_LARGE", "Review command is too large", 413)
    raw = request.read(MAX_REVIEW_COMMAND_BYTES + 1)
    if len(raw) > MAX_REVIEW_COMMAND_BYTES:
        raise ReviewCommandError("PAYLOAD_TOO_LARGE", "Review command is too large", 413)
    try:
        payload = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewCommandError("INVALID_COMMAND", "Invalid JSON command", 422) from exc
    return command_type.from_dict(payload)


def _review_error(exc: ReviewCommandError) -> JsonResponse:
    response = JsonResponse(exc.as_dict(), status=exc.http_status)
    response["Cache-Control"] = "no-store"
    return response


def _review_command(request, report_id: str, command_type, action: str) -> HttpResponse:
    if not request.user.is_authenticated or not request.user.is_active:
        return _review_error(ReviewCommandError("UNAUTHENTICATED", "Authentication required", 401))
    grant = ReportGrant.objects.select_related("report").filter(
        report_id=report_id, user=request.user,
    ).first()
    if grant is None:
        return _review_error(ReviewCommandError("REVIEW_NOT_FOUND", "Report not found", 404))
    report = validate_report_data(grant.report.report_data)
    if report.report_id != grant.report_id:
        raise ValueError("Stored report identifier does not match its record")
    try:
        command = _command_request(request, command_type)
        service = ReviewCommandService(
            DjangoReviewRepository(grant.report, report), DjangoReviewAuthorizer(request.user),
            clock=timezone.now,
        )
        result = getattr(service, action)(command, actor_id=str(request.user.pk), report=report)
    except ReviewCommandError as exc:
        return _review_error(exc)
    else:
        response = JsonResponse(result.as_dict(), status=201)
    response["Cache-Control"] = "no-store"
    return response


@csrf_protect
@require_POST
def save_review_revision(request, report_id: str) -> HttpResponse:
    return _review_command(request, report_id, SaveDraftRequest, "save")


@csrf_protect
@require_POST
def finalize_review(request, report_id: str) -> HttpResponse:
    return _review_command(request, report_id, FinalizeRequest, "finalize")

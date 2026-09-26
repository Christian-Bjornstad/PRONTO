"""Authorize first, then validate and render or save report review snapshots."""

import json
import os
import stat

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import ObjectDoesNotExist
from django.http import Http404, HttpResponse, JsonResponse, StreamingHttpResponse
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from pronto_report.renderers.assets import load_plot_images_from_bytes
from pronto_report.renderers.html import render_html
from pronto_report.review.contracts import FinalizeRequest, ReviewCommandError, SaveDraftRequest
from pronto_report.review.service import ReviewCommandService
from pronto_report.validation import validate_report_data, validate_review_state
from pronto_web.reports.models import ReportGrant, ReportRecord, ReportWriteGrant, ReviewRevision
from pronto_web.reports.review_repository import DjangoReviewAuthorizer, DjangoReviewRepository
from pronto_web.reports.alignment_config import alignment_saving_enabled
from pronto_web.reports.alignment_ranges import (RangeNotSatisfiable, iter_range,
                                                  parse_single_range, parse_upload_range)
from pronto_web.reports.alignment_registry import (InvalidAlignmentRegistry,
                                                    lookup_registered, lookup_saved)
from pronto_web.reports.alignment_commands import (
    MAX_CHUNK_BYTES, AlignmentConflict, AlignmentSessionClosed, accept_chunk,
    authorized_upload_session, begin_local_save, cancel_local_save,
    complete_local_save, delete_saved, preserve_registered,
    require_alignment_write,
)
from pronto_web.reports.alignment_store import StorageLimitError, UnsafeAlignmentPath


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
    try:
        pairs = lookup_registered(record.report_id, str(report.sample["sampleId"]), str(report.sample["referenceBuild"]))
    except InvalidAlignmentRegistry:
        pairs = ()
        registry_error = True
    else:
        registry_error = False
    try:
        saved_pairs = lookup_saved(record.report_id, str(report.sample["sampleId"]),
                                   str(report.sample["referenceBuild"]))
    except InvalidAlignmentRegistry:
        saved_pairs = ()
        registry_error = True
    sources = tuple({
        "sourceId": pair.source_id, "role": pair.role, "format": pair.format,
        "referenceBuild": pair.reference_build,
        "dataURL": f"/reports/{record.report_id}/alignments/{pair.source_id}/data/",
        "indexURL": f"/reports/{record.report_id}/alignments/{pair.source_id}/index/",
    } for pair in (*pairs, *saved_pairs))
    references = {build: value for build, value in settings.PRONTO_IGV_REFERENCES.items()
                  if all(value.values())}
    csrf_token = get_token(request)
    draft = review is not None and review.status == "DRAFT"
    html = render_html(
        report, review, plot_images=plot_images, inline_assets=True,
        save_url=reverse("review-save", args=[record.report_id]) if draft else None,
        finalize_url=reverse("review-finalize", args=[record.report_id]) if draft else None,
        csrf_token=csrf_token,
        require_initials=getattr(settings, 'PRONTO_REQUIRE_INITIALS', False),
        print_url=reverse('report-print', args=[record.report_id]),
        actor_id=str(request.user.pk) if draft else None,
        web_igv=True, igv_sources=sources, igv_references=references,
        igv_registry_error=registry_error,
        igv_save_enabled=(alignment_saving_enabled(settings)
                          and ReportWriteGrant.objects.filter(report=record, user=request.user).exists()),
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
            require_initials=getattr(settings, 'PRONTO_REQUIRE_INITIALS', False),
        )
        result = getattr(service, action)(command, actor_id=str(request.user.pk), report=report)
    except ReviewCommandError as exc:
        return _review_error(exc)
    else:
        response = JsonResponse(result.as_dict(), status=201)
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
        matching = lookup_saved if source_id.startswith("saved-") else lookup_registered
        pair = next((pair for pair in matching(
            report_id, str(report.sample["sampleId"]), str(report.sample["referenceBuild"]),
        ) if pair.source_id == source_id), None)
    except InvalidAlignmentRegistry:
        return HttpResponse(status=404)
    if pair is None:
        return HttpResponse(status=404)
    path = pair.data_path if component == "data" else pair.index_path
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        handle = os.fdopen(descriptor, "rb")
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            handle.close()
            return HttpResponse(status=404)
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


def _write_report(request, report_id: str) -> ReportRecord:
    if not request.user.is_authenticated or not request.user.is_active:
        raise PermissionDenied
    grant = get_object_or_404(ReportGrant.objects.select_related("report"),
                              report_id=report_id, user=request.user)
    require_alignment_write(request.user, grant.report)
    return grant.report


def _small_json(request) -> dict:
    if request.content_type != "application/json":
        raise ValueError("JSON required")
    raw = request.read(4097)
    if len(raw) > 4096:
        raise StorageLimitError("metadata too large")
    try:
        payload = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    return payload


def _save_error(exc: Exception) -> HttpResponse:
    if isinstance(exc, (AlignmentConflict, AlignmentSessionClosed)):
        status = 409
    elif isinstance(exc, (RangeNotSatisfiable,)):
        status = 416
    elif isinstance(exc, StorageLimitError):
        status = 413
    elif isinstance(exc, PermissionDenied):
        status = 403
    elif isinstance(exc, ObjectDoesNotExist):
        status = 404
    elif isinstance(exc, (OSError, UnsafeAlignmentPath)):
        status = 507
    else:
        status = 400
    response = JsonResponse({"error": {
        400: "invalid_alignment_request", 403: "forbidden", 404: "not_found",
        409: "alignment_conflict", 413: "alignment_too_large",
        416: "invalid_range", 507: "storage_unavailable",
    }[status]}, status=status)
    response["Cache-Control"] = "no-store"
    return response


@csrf_protect
@require_POST
def save_review_revision(request, report_id: str) -> HttpResponse:
    return _review_command(request, report_id, SaveDraftRequest, "save")


@csrf_protect
@require_POST
def start_alignment_save(request, report_id: str) -> HttpResponse:
    report = _write_report(request, report_id)
    try:
        payload = _small_json(request)
        if payload.get("confirmed") is not True:
            raise ValueError("explicit confirmation required")
        session = begin_local_save(
            request.user, report, payload.get("sampleId"), payload.get("referenceBuild"),
            payload.get("role"), payload.get("format"),
            {"data": payload.get("dataSize"), "index": payload.get("indexSize")},
        )
    except (ValueError, PermissionDenied, OSError) as exc:
        return _save_error(exc)
    response = JsonResponse({"sessionId": str(session.id), "expiresAt": session.expires_at.isoformat()}, status=201)
    response["Cache-Control"] = "no-store"
    return response


@csrf_protect
@require_http_methods(["PUT"])
def upload_alignment_chunk(request, report_id: str, session_id, component: str) -> HttpResponse:
    report = _write_report(request, report_id)
    try:
        # Authorization precedes any read of the potentially large request body.
        authorized_upload_session(request.user, report, session_id)
        start, end, total = parse_upload_range(request.headers.get("Content-Range", ""), MAX_CHUNK_BYTES)
        if component not in {"data", "index"}:
            raise Http404
        if request.META.get("CONTENT_LENGTH") != str(end - start + 1):
            raise RangeNotSatisfiable("body length differs from range")
        offset = accept_chunk(request.user, session_id, component, start, total, request,
                              report=report)
    except Http404:
        raise
    except (ValueError, PermissionDenied, ObjectDoesNotExist, OSError) as exc:
        return _save_error(exc)
    response = HttpResponse(status=204)
    response["Upload-Offset"] = str(offset)
    response["Cache-Control"] = "no-store"
    return response


@csrf_protect
@require_POST
def finalize_review(request, report_id: str) -> HttpResponse:
    return _review_command(request, report_id, FinalizeRequest, "finalize")


@csrf_protect
@require_POST
def complete_alignment_save(request, report_id: str, session_id) -> HttpResponse:
    report = _write_report(request, report_id)
    try:
        session = authorized_upload_session(request.user, report, session_id)
        payload = _small_json(request)
        saved = complete_local_save(request.user, session_id, payload.get("referenceBuild"),
                                    report=report)
    except (ValueError, PermissionDenied, ObjectDoesNotExist, OSError) as exc:
        return _save_error(exc)
    response = JsonResponse({"savedId": str(saved.id), "sourceId": f"saved-{saved.id.hex}"},
                            status=200 if session.state == "COMPLETED" else 201)
    response["Cache-Control"] = "no-store"
    return response


@csrf_protect
@require_http_methods(["DELETE"])
def cancel_alignment_save(request, report_id: str, session_id) -> HttpResponse:
    report = _write_report(request, report_id)
    try:
        cancel_local_save(request.user, session_id, report=report)
    except (ValueError, PermissionDenied, ObjectDoesNotExist, OSError) as exc:
        return _save_error(exc)
    return HttpResponse(status=204)


@csrf_protect
@require_POST
def preserve_registered_alignment(request, report_id: str, source_id: str) -> HttpResponse:
    report = _write_report(request, report_id)
    try:
        payload = _small_json(request)
        if payload.get("confirmed") is not True:
            raise ValueError("explicit confirmation required")
        saved = preserve_registered(request.user, report, source_id)
    except (ValueError, PermissionDenied, ObjectDoesNotExist, OSError) as exc:
        return _save_error(exc)
    response = JsonResponse({"savedId": str(saved.id), "sourceId": f"saved-{saved.id.hex}"}, status=201)
    response["Cache-Control"] = "no-store"
    return response


@csrf_protect
@require_http_methods(["DELETE"])
def delete_saved_alignment(request, report_id: str, saved_id) -> HttpResponse:
    report = _write_report(request, report_id)
    try:
        delete_saved(request.user, report, saved_id)
    except (ValueError, PermissionDenied, ObjectDoesNotExist, OSError) as exc:
        return _save_error(exc)
    return HttpResponse(status=204)

"""Audited download of one immutable saved review as offline HTML."""

from __future__ import annotations

import json
import logging
import re
from uuid import UUID

from django.db import DatabaseError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from pronto_report.renderers.summary_html import render_summary_html
from pronto_report.review.attribution import normalize_initials
from pronto_report.review.contracts import ReviewCommandError
from pronto_report.validation import validate_report_data, validate_review_state
from .models import ReportGrant, ReportHtmlExportAudit, ReportRecord, ReviewRevision


_logger = logging.getLogger(__name__)


def _record_and_render(record: ReportRecord, actor, revision: int,
                       request_id: UUID, initials: str) -> str:
    """Return HTML only after a transactionally recorded matching request."""
    with transaction.atomic():
        locked = ReportRecord.objects.select_for_update().get(pk=record.pk)
        if not actor.is_active or not ReportGrant.objects.select_for_update().filter(
                report=locked, user=actor).exists():
            raise ReviewCommandError('FORBIDDEN', 'Report access denied', 403)
        existing = ReportHtmlExportAudit.objects.filter(report=locked, request_id=request_id).first()
        if existing and (existing.actor_id, existing.revision, existing.declared_initials) != (
                actor.pk, revision, initials):
            raise ReviewCommandError('EXPORT_CONFLICT', 'HTML request ID is already used', 409)
        latest = ReviewRevision.objects.filter(report=locked).order_by('-revision').first()
        if not existing and (latest is None or latest.revision != revision):
            raise ReviewCommandError('REVISION_CONFLICT', 'Saved revision has changed', 409,
                                     current_revision=latest.revision if latest else None)
        row = (ReviewRevision.objects.filter(report=locked, revision=revision).first()
               if existing else latest)
        if row is None:
            raise ReviewCommandError('REVISION_NOT_FOUND', 'Saved revision is unavailable', 409)
        report = validate_report_data(locked.report_data)
        if report.report_id != locked.report_id:
            raise ValueError('Stored report identifier mismatch')
        review = validate_review_state(row.review_data, report=report)
        if review.revision != row.revision:
            raise ValueError('Stored review revision mismatch')
        html = render_summary_html(report, review, export_initials=initials)
        if not existing:
            ReportHtmlExportAudit.objects.create(
                report=locked, actor=actor, revision=revision,
                request_id=request_id, declared_initials=initials,
                requested_at=timezone.now(),
            )
        return html


def _error(code: str, status: int) -> JsonResponse:
    response = JsonResponse({'error': {'code': code}}, status=status)
    response['Cache-Control'] = 'no-store'
    return response


@require_POST
@csrf_protect
def html_export_request(request, report_id: str) -> HttpResponse:
    if not request.user.is_authenticated or not request.user.is_active:
        return _error('UNAUTHENTICATED', 401)
    grant = get_object_or_404(ReportGrant.objects.select_related('report'),
                              report_id=report_id, user=request.user)
    try:
        if request.content_type != 'application/json':
            raise ValueError('JSON required')
        body = request.read(4097)
        if len(body) > 4096:
            raise ValueError('Command too large')
        data = json.loads(body)
        if (not isinstance(data, dict)
                or set(data) != {'schemaVersion', 'reportId', 'revision', 'requestId', 'declaredInitials'}
                or data['schemaVersion'] != '1.0'
                or data['reportId'] != report_id
                or type(data['revision']) is not int or data['revision'] < 1
                or not isinstance(data['requestId'], str)):
            raise ValueError('Invalid command')
        request_id = UUID(data['requestId'])
        initials = normalize_initials(data['declaredInitials'])
    except (ValueError, TypeError, UnicodeDecodeError):
        return _error('INVALID_COMMAND', 422)
    except ReviewCommandError as error:
        return _error(error.code, error.http_status)
    try:
        html = _record_and_render(grant.report, request.user, data['revision'], request_id, initials)
    except ReviewCommandError as error:
        return _error(error.code, error.http_status)
    except DatabaseError:
        _logger.exception('HTML export audit unavailable')
        return _error('AUDIT_UNAVAILABLE', 503)
    except Exception:
        # Stored contract or rendering failures must never return partial HTML.
        _logger.exception('HTML export rendering unavailable')
        return _error('REPORT_UNAVAILABLE', 503)
    response = HttpResponse(html, content_type='text/html; charset=utf-8')
    filename_id = re.sub(r'[^A-Za-z0-9_-]', '-', report_id)
    response['Content-Disposition'] = f'attachment; filename="PRONTO-{filename_id}-r{data["revision"]}.html"'
    response['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'no-store'
    return response

"""Record a request to print a saved revision, never claim print completion."""
import json
from uuid import UUID
from django.db import transaction, DatabaseError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from pronto_report.review.attribution import normalize_initials
from pronto_report.review.contracts import ReviewCommandError
from .models import ReportGrant, ReportRecord, ReportPrintAudit, ReviewRevision


def record_print_request(record, actor, revision: int, request_id: UUID, initials: str) -> ReportPrintAudit:
    initials = normalize_initials(initials)
    with transaction.atomic():
        ReportRecord.objects.select_for_update().get(pk=record.pk)
        if not actor.is_active or not ReportGrant.objects.select_for_update().filter(report=record, user=actor).exists():
            raise ReviewCommandError('FORBIDDEN', 'Report access denied', 403)
        existing = ReportPrintAudit.objects.filter(report=record, request_id=request_id).first()
        if existing:
            if (existing.actor_id, existing.revision, existing.declared_initials) != (actor.pk, revision, initials):
                raise ReviewCommandError('PRINT_CONFLICT', 'Print request ID is already used', 409)
            return existing
        latest = ReviewRevision.objects.filter(report=record).order_by('-revision').first()
        if latest is None or latest.revision != revision:
            raise ReviewCommandError('REVISION_CONFLICT', 'Saved revision has changed', 409)
        return ReportPrintAudit.objects.create(report=record, actor=actor, revision=revision,
            request_id=request_id, declared_initials=initials, requested_at=timezone.now())


@require_POST
@csrf_protect
def print_request(request, report_id):
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({'error': {'code': 'UNAUTHENTICATED'}}, status=401)
    grant = get_object_or_404(ReportGrant.objects.select_related('report'), report_id=report_id, user=request.user)
    try:
        if request.content_type != 'application/json':
            raise ValueError()
        body = request.read(4097)
        if len(body) > 4096:
            raise ValueError()
        data = json.loads(body)
        if (not isinstance(data, dict) or set(data) != {'schemaVersion', 'revision', 'requestId', 'declaredInitials'}
                or data['schemaVersion'] != '1.0' or type(data['revision']) is not int or data['revision'] < 1
                or not isinstance(data['requestId'], str)):
            raise ValueError()
        event = record_print_request(grant.report, request.user, data['revision'], UUID(data['requestId']), data['declaredInitials'])
        response = JsonResponse({'requestId': str(event.request_id), 'reportId': report_id, 'revision': event.revision,
            'declaredInitials': event.declared_initials, 'method': event.attribution_method,
            'action': event.action, 'requestedAt': event.requested_at.isoformat()}, status=201)
    except (ValueError, TypeError, UnicodeDecodeError):
        response = JsonResponse({'error': {'code': 'INVALID_COMMAND'}}, status=422)
    except ReviewCommandError as error:
        response = JsonResponse(error.as_dict(), status=error.http_status)
    except DatabaseError:
        response = JsonResponse({'error': {'code': 'AUDIT_UNAVAILABLE'}}, status=503)
    response['Cache-Control'] = 'no-store'
    return response

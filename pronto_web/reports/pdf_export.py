"""Attributed PDFs rendered from an immutable saved revision, with audit atomically."""
import json
import logging
import re
from hashlib import sha256
from uuid import UUID

from django.db import DatabaseError, transaction
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from pronto_report.renderers.report_pdf import render_report_pdf, TEMPLATE_VERSION
from pronto_report.review.attribution import normalize_initials
from pronto_report.review.contracts import ReviewCommandError
from pronto_report.validation import validate_report_data, validate_review_state
from .html_export_audit import _error
from .models import ReportGrant, ReportRecord, ReviewRevision, ReportPdfExportAudit, PresentationFigure

logger=logging.getLogger(__name__)


def record_and_render(record,actor,data,request_id,initials):
    actor_label = initials if initials is not None else actor.get_username()
    method = 'SELF_REPORTED' if initials is not None else 'AUTHENTICATED'
    with transaction.atomic():
        locked=ReportRecord.objects.select_for_update().get(pk=record.pk)
        if not actor.is_active or not ReportGrant.objects.filter(report=locked,user=actor).exists():
            raise ReviewCommandError('FORBIDDEN','Report access denied',403)
        existing=ReportPdfExportAudit.objects.filter(report=locked,request_id=request_id).first()
        identity=(actor.pk,data['revision'],initials,actor_label if method=='AUTHENTICATED' else None,method,data['layout'],TEMPLATE_VERSION)
        if existing and (existing.actor_id,existing.revision,existing.declared_initials,existing.actor_label,existing.attribution_method,existing.layout,existing.template_version)!=identity:
            raise ReviewCommandError('EXPORT_CONFLICT','Request ID already used',409)
        latest=ReviewRevision.objects.filter(report=locked).order_by('-revision').first()
        if not existing and (latest is None or latest.revision!=data['revision']):
            raise ReviewCommandError('REVISION_CONFLICT','Saved revision has changed',409)
        row=ReviewRevision.objects.filter(report=locked,revision=data['revision']).first()
        if row is None: raise ReviewCommandError('REVISION_NOT_FOUND','Revision unavailable',409)
        report=validate_report_data(locked.report_data)
        review=validate_review_state(row.review_data,report=report)
        if report.report_id!=locked.pk or review.revision!=row.revision: raise ValueError('Stored identity mismatch')
        assets={}
        if data['layout']=='PRESENTATION':
            ids=[item['figureId'] for item in review.presentation_figures]
            for figure in PresentationFigure.objects.filter(report=locked,pk__in=ids):
                payload=bytes(figure.content)
                if sha256(payload).hexdigest()!=figure.sha256: raise ValueError('Figure hash mismatch')
                assets[str(figure.pk)]=payload
        pdf=render_report_pdf(report,review,layout=data['layout'],export_initials=actor_label,figure_assets=assets)
        if not existing:
            ReportPdfExportAudit.objects.create(report=locked,actor=actor,revision=row.revision,
                request_id=request_id,declared_initials=initials,layout=data['layout'],
                actor_label=actor_label if method=='AUTHENTICATED' else None,attribution_method=method,
                template_version=TEMPLATE_VERSION,requested_at=timezone.now())
        return pdf


@require_POST
@csrf_protect
def pdf_export_request(request,report_id):
    if not request.user.is_authenticated or not request.user.is_active: return _error('UNAUTHENTICATED',401)
    grant=get_object_or_404(ReportGrant.objects.select_related('report'),report_id=report_id,user=request.user)
    try:
        if request.content_type!='application/json': raise ValueError('JSON required')
        raw=request.read(4097)
        if len(raw)>4096: raise ValueError('Command too large')
        data=json.loads(raw)
        required={'schemaVersion','reportId','revision','requestId','layout'}
        if (not isinstance(data,dict) or not required <= set(data) or set(data)-required-{'declaredInitials'}
                or data['schemaVersion']!='1.0' or data['reportId']!=report_id
                or type(data['revision']) is not int or data['revision']<1
                or not isinstance(data['requestId'],str) or data['layout'] not in ('ESMO','PRESENTATION')):
            raise ValueError('Invalid command')
        identifier=UUID(data['requestId'])
        initials=normalize_initials(data.get('declaredInitials')) if getattr(settings,'PRONTO_REQUIRE_INITIALS',False) else None
    except (ValueError,TypeError,UnicodeError,ReviewCommandError): return _error('INVALID_COMMAND',422)
    try:
        pdf=record_and_render(grant.report,request.user,data,identifier,initials)
    except ReviewCommandError as error: return _error(error.code,error.http_status)
    except DatabaseError:
        logger.exception('PDF audit unavailable');return _error('AUDIT_UNAVAILABLE',503)
    except Exception:
        logger.exception('PDF rendering unavailable');return _error('REPORT_UNAVAILABLE',503)
    response=HttpResponse(pdf,content_type='application/pdf')
    safe=re.sub(r'[^A-Za-z0-9_-]','-',report_id)
    response['Content-Disposition']=f'attachment; filename="InPreD-{safe}-r{data["revision"]}-{data["layout"].lower()}.pdf"'
    response['Cache-Control']='no-store';response['X-Content-Type-Options']='nosniff'
    return response

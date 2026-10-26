"""Administrators hide redundant drafts while preserving audit and export history."""
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .models import (AdministrationEvent, HiddenRevision, ReportGrant, ReportRecord,
                     ReviewRevision, WorkingDraft, ReportPdfExportAudit,
                     ReportHtmlExportAudit, ReportPrintAudit)
from .user_management import is_administrator


def protected_revisions(record):
    protected = set()
    for model in (ReportPdfExportAudit, ReportHtmlExportAudit, ReportPrintAudit):
        protected.update(model.objects.filter(report=record).values_list('revision', flat=True))
    working = WorkingDraft.objects.filter(report=record).first()
    if working and working.source_revision:
        protected.add(working.source_revision)
    latest = record.reviews.order_by('-revision').first()
    if latest:
        protected.add(latest.revision)
    return protected


@never_cache
@require_http_methods(['GET', 'POST'])
def manage_revisions(request, report_id):
    if not is_administrator(request.user):
        raise PermissionDenied
    get_object_or_404(ReportGrant, report_id=report_id, user=request.user)
    error = ''
    with transaction.atomic():
        record = get_object_or_404(ReportRecord.objects.select_for_update(), pk=report_id)
        protected = protected_revisions(record)
        if request.method == 'POST':
            value = request.POST.get('revision', '')
            row = get_object_or_404(ReviewRevision, report=record, revision=int(value) if len(value)<=10 and value.isdecimal() else 0)
            if row.review_data['status'] != 'DRAFT' or row.revision in protected:
                error = 'Gjeldende, ferdigstilte og eksporterte revisjoner beholdes.'
            elif request.POST.get('action') == 'HIDE':
                _, created = HiddenRevision.objects.get_or_create(review=row, defaults={'actor': request.user})
                if created:
                    AdministrationEvent.objects.create(actor=request.user, action='HIDE_REVISION',
                        report_id=report_id, revision=row.revision)
                return redirect('manage-revisions', report_id=report_id)
            elif request.POST.get('action') == 'RESTORE':
                if HiddenRevision.objects.filter(review=row).delete()[0]:
                    AdministrationEvent.objects.create(actor=request.user, action='RESTORE_REVISION',
                        report_id=report_id, revision=row.revision)
                return redirect('manage-revisions', report_id=report_id)
        rows = list(record.reviews.order_by('-revision'))
        hidden = set(HiddenRevision.objects.filter(review__report=record).values_list('review_id', flat=True))
    return render(request, 'reports/revisions.html', {'record': record, 'rows': rows,
        'protected': protected, 'hidden': hidden, 'error': error})

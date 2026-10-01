"""Append a bounded synthetic cohort using the normal save/finalize services."""
from datetime import datetime, timedelta
import json

from django.core.management import CommandError
from django.db import transaction

from pronto_report.review.contracts import SaveDraftRequest, FinalizeRequest
from pronto_report.review.service import ReviewCommandService
from pronto_report.serialization import serialize_report_data, serialize_review_state
from .models import ReportRecord, ReviewRevision, ReportAsset, ReportGrant
from .review_repository import DjangoReviewAuthorizer, DjangoReviewRepository
from .synthetic_data import GENERATOR, build_synthetic_case


def seed_synthetic_cohort(user, *, count=30, seed=20261001):
    if (type(count) is not int or not 1 <= count <= 200 or type(seed) is not int or not 0 <= seed <= 2**31 - 1
            or user.username != 'local-demo-service' or not user.is_active or user.is_staff or user.is_superuser):
        raise CommandError('Use 1-200 cases, a nonnegative 32-bit seed and the restricted demo principal.')
    created, existing = 0, 0
    with transaction.atomic():
        for index in range(count):
            case = build_synthetic_case(index, seed=seed)
            document = json.loads(serialize_report_data(case.report))
            record = ReportRecord.objects.filter(pk=case.report.report_id).first()
            if record:
                generator = record.report_data.get('provenance', {}).get('generator', {})
                if (generator.get('name') != GENERATOR
                        or generator != document['provenance']['generator']
                        or not ReportGrant.objects.filter(report=record, user=user).exists()
                        or not ReviewRevision.objects.filter(report=record).exists()):
                    raise CommandError('Synthetic report ID collision; no reports were changed.')
                existing += 1
                continue
            record = ReportRecord.objects.create(report_id=case.report.report_id, report_data=document)
            ReportGrant.objects.create(report=record, user=user)
            ReviewRevision.objects.create(report=record, revision=1,
                review_data=json.loads(serialize_review_state(case.initial_review)))
            ReportAsset.objects.bulk_create([ReportAsset(report=record, asset_id=key, content=value)
                                             for key, value in case.assets.items()])
            if index % 3:
                now = datetime.fromisoformat(case.initial_review.created_at) + timedelta(hours=1)
                service = ReviewCommandService(DjangoReviewRepository(record, case.report),
                    DjangoReviewAuthorizer(user), clock=lambda: now, require_initials=True)
                draft = json.loads(serialize_review_state(case.prepared_review))
                saved = service.save(SaveDraftRequest('1.0', record.pk, 1, draft, 'SM'),
                                     actor_id=str(user.pk), report=case.report).review
                if index % 2:
                    now += timedelta(hours=1)
                    draft = json.loads(serialize_review_state(saved))
                    draft['notes']['additional'] += '\nSimulated second save: version history demonstration.'
                    saved = service.save(SaveDraftRequest('1.0', record.pk, saved.revision, draft, 'SM'),
                                         actor_id=str(user.pk), report=case.report).review
                if index % 3 == 2:
                    now += timedelta(minutes=15)
                    service.finalize(FinalizeRequest('1.0', record.pk, saved.revision,
                        json.loads(serialize_review_state(saved)), 'SM'), actor_id=str(user.pk), report=case.report)
            created += 1
    return {'created': created, 'existing': existing}

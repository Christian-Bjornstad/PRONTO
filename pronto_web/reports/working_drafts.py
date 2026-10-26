"""Overwrite a working copy using compare-and-swap; preserve published snapshots."""
import json
from dataclasses import replace

from django.conf import settings
from django.db import transaction, IntegrityError, OperationalError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from pronto_report.review.source_defaults import upgrade_review
from pronto_report.review.service import ReviewCommandService
from pronto_report.review.contracts import SaveDraftRequest, ReviewCommandError
from pronto_report.serialization import serialize_review_state
from pronto_report.validation import validate_report_data, validate_review_state, ContractValidationError
from .models import ReportRecord, ReportGrant, WorkingDraft, WorkingDraftEvent, ReviewRevision, PresentationFigure
from .review_repository import DjangoReviewAuthorizer


def document(review):
    return json.loads(serialize_review_state(review))


def current_working(record, report):
    working = WorkingDraft.objects.filter(report=record).first()
    if working:
        return validate_review_state(working.review_data, report=report), working.version
    latest = ReviewRevision.objects.filter(report=record).order_by('-revision').first()
    if latest is None:
        return None, 0
    review = validate_review_state(latest.review_data, report=report)
    if review.status == 'DRAFT':
        review = replace(upgrade_review(report, review), revision=latest.revision + 1)
    return review, 0


class ValidationRepository:
    def __init__(self, current): self.current = current
    def latest(self, identifier): return self.current
    def commit(self, *args): return True


def reject_constant(value):
    raise ValueError('Non-finite JSON number')


def conflict():
    raise ReviewCommandError('REVISION_CONFLICT', 'Working draft changed. Reload before saving.', 409)


def freeze_draft(record, revision, version):
    """Called inside the export transaction; retry uses the frozen revision."""
    working = WorkingDraft.objects.select_for_update().filter(report=record).first()
    if not working or working.revision != revision or type(version) is not int or working.version != version:
        conflict()
    latest = ReviewRevision.objects.filter(report=record).order_by('-revision').first()
    if latest and ({key:value for key,value in latest.review_data.items() if key!='revision'} ==
                   {key:value for key,value in working.review_data.items() if key!='revision'}):
        return version, revision, latest.revision
    ReviewRevision.objects.create(report=record, revision=revision, review_data=working.review_data)
    new = {**working.review_data, 'revision': revision + 1}
    if not WorkingDraft.objects.filter(pk=working.pk, version=version).update(
            revision=revision+1, version=version+1, review_data=new):
        conflict()
    return version + 1, revision + 1, revision


@never_cache
@require_POST
@csrf_protect
def working_command(request, report_id):
    if not request.user.is_authenticated or not request.user.is_active:
        return JsonResponse({'error':{'code':'UNAUTHENTICATED'}},status=401)
    if not settings.PRONTO_WORKING_DRAFTS:
        return JsonResponse({'error':{'code':'WORKING_DISABLED'}},status=404)
    try:
        if request.content_type != 'application/json':
            raise ReviewCommandError('INVALID_COMMAND','JSON required',422)
        raw=request.read(1024*1024+1)
        if len(raw)>1024*1024: raise ReviewCommandError('PAYLOAD_TOO_LARGE','Command too large',413)
        data=json.loads(raw,parse_constant=reject_constant)
        required={'schemaVersion','reportId','action','baseRevision','expectedVersion'}
        if (not isinstance(data,dict) or not required <= data.keys() or
            data.keys()-required-{'draft','sourceRevision','replaceWorking'} or
            data['schemaVersion']!='2.0' or data['reportId']!=report_id or
            not isinstance(data['action'],str) or data['action'] not in {'SAVE','FINALIZE','REOPEN','RESET'} or
            type(data['baseRevision']) is not int or data['baseRevision']<1 or
            type(data['expectedVersion']) is not int or data['expectedVersion']<0):
            raise ReviewCommandError('INVALID_COMMAND','Invalid command',422)
        with transaction.atomic():
            record=ReportRecord.objects.select_for_update().filter(pk=report_id).first()
            if record is None or not ReportGrant.objects.filter(report=record,user=request.user).exists():
                raise ReviewCommandError('REVIEW_NOT_FOUND','Report unavailable',404)
            report=validate_report_data(record.report_data)
            current, version=current_working(record,report)
            working=WorkingDraft.objects.filter(report=record).first()
            if version != data['expectedVersion'] or current is None or current.revision != data['baseRevision']:
                conflict()
            now=timezone.now(); action=data['action']
            source=None
            if action=='REOPEN':
                if working and data.get('replaceWorking') is not True:
                    raise ReviewCommandError('DRAFT_EXISTS','Confirm replacing the active draft.',409)
                source=data.get('sourceRevision')
                if type(source) is not int or source<1:
                    raise ReviewCommandError('INVALID_COMMAND','Source revision required',422)
                row=ReviewRevision.objects.filter(report=record,revision=source).first()
                if row is None and working and working.revision==source:
                    copied=working.review_data
                    ReviewRevision.objects.create(report=record,revision=source,review_data=copied)
                elif row: copied=row.review_data
                else: raise ReviewCommandError('REVISION_NOT_FOUND','Source revision unavailable',404)
                review=upgrade_review(report,validate_review_state(copied,report=report))
                latest=ReviewRevision.objects.filter(report=record).order_by('-revision').first()
                next_revision=max(current.revision,latest.revision if latest else 0)+1
                saved=document(review)
                for key in ('finalizedAt','finalizedBy','finalizationAttribution'): saved.pop(key,None)
                saved.update(status='DRAFT',revision=next_revision)
            else:
                if current.status!='DRAFT':
                    raise ReviewCommandError('FINAL_LOCKED','Start a new revision before editing.',409)
                current=upgrade_review(report,current)
                service=ReviewCommandService(ValidationRepository(current),DjangoReviewAuthorizer(request.user),
                    clock=lambda:now,actor_label=request.user.get_username())
                if action=='SAVE':
                    if not isinstance(data.get('draft'),dict) or data['draft'].get('schemaVersion')!='4.0':
                        raise ReviewCommandError('INVALID_DRAFT','Expected current draft',422)
                    result=service.save(SaveDraftRequest('1.0',report_id,current.revision,data['draft']),
                                        actor_id=str(request.user.pk),report=report)
                    saved=document(replace(result.review,revision=current.revision))
                elif action=='RESET':
                    from pronto_report.review.contracts import ResetDraftRequest
                    result=service.reset(ResetDraftRequest('1.0',report_id,current.revision),actor_id=str(request.user.pk),report=report)
                    saved=document(replace(result.review,revision=current.revision,manual_cnv_rows=()))
                else:
                    if working is None: raise ReviewCommandError('UNSAVED_CHANGES','Save before finalizing.',409)
                    included={i['findingId'] for i in current.finding_reviews if i['reportingDecision']=='INCLUDE'}
                    if any(not r['geneSymbol'].strip() and r['findingId'] in included for r in current.manual_cnv_rows):
                        raise ReviewCommandError('INVALID_DRAFT','Included manual CNV requires a gene.',422)
                    saved=document(current)
                    saved.update(status='FINAL',finalizedAt=now.isoformat(),finalizedBy=str(request.user.pk))
                    saved['finalizationAttribution']={'actorId':str(request.user.pk),'actorLabel':request.user.get_username(),'method':'AUTHENTICATED'}
            saved['updatedAt']=now.isoformat()
            saved['reviewer']={'reviewerId':str(request.user.pk)}
            saved['lastSavedAttribution']={'actorId':str(request.user.pk),'actorLabel':request.user.get_username(),'method':'AUTHENTICATED'}
            validate_review_state(saved,report=report)
            ids=[item['figureId'] for item in saved.get('presentationFigures',[])]
            if len(ids)!=len(set(ids)) or PresentationFigure.objects.filter(report=record,pk__in=ids).count()!=len(ids):
                raise ReviewCommandError('INVALID_DRAFT','Unknown or duplicate presentation figure',422)
            if action=='FINALIZE':
                ReviewRevision.objects.create(report=record,revision=saved['revision'],review_data=saved)
                if not WorkingDraft.objects.filter(report=record,version=version).delete()[0]: conflict()
                new_version=0
            else:
                new_version=version+1
                if working:
                    if not WorkingDraft.objects.filter(pk=working.pk,version=version).update(
                        review_data=saved,revision=saved['revision'],version=new_version,
                        source_revision=source if action=='REOPEN' else working.source_revision): conflict()
                else:
                    WorkingDraft.objects.create(report=record,review_data=saved,revision=saved['revision'],
                                                version=new_version,source_revision=source)
            WorkingDraftEvent.objects.create(report=record,actor=request.user,action=action,
                revision=saved['revision'],version=new_version,source_revision=source,occurred_at=now)
        return JsonResponse({'review':saved,'workingVersion':new_version},status=201)
    except (ValueError,UnicodeError):
        return JsonResponse({'error':{'code':'INVALID_COMMAND'}},status=422)
    except ContractValidationError:
        return JsonResponse({'error':{'code':'INVALID_DRAFT'}},status=422)
    except ReviewCommandError as error:
        return JsonResponse(error.as_dict(),status=error.http_status)
    except (IntegrityError,OperationalError):
        return JsonResponse({'error':{'code':'REVISION_CONFLICT'}},status=409)

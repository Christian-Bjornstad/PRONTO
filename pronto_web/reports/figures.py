"""Bounded, decoded and re-encoded images. No public upload directory."""
from hashlib import sha256
from io import BytesIO
import warnings

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import PresentationFigure, ReportGrant, ReportRecord, ReviewRevision

MAX_IMAGE_BYTES=8*1024*1024
MAX_REPORT_BYTES=64*1024*1024
MAX_PIXELS=16_000_000
MAX_SOURCE_PIXELS=64_000_000


def _grant(request,report_id):
    if not request.user.is_authenticated or not request.user.is_active:
        return None
    return get_object_or_404(ReportGrant.objects.select_related('report'),report_id=report_id,user=request.user)


@require_POST
@csrf_protect
def upload_figure(request,report_id):
    grant=_grant(request,report_id)
    if grant is None: return HttpResponse(status=401)
    uploaded=request.FILES.get('image')
    if uploaded is None: return JsonResponse({'error':{'code':'IMAGE_REQUIRED'}},status=422)
    if uploaded.size>MAX_IMAGE_BYTES: return HttpResponse(status=413)
    try:
        payload=uploaded.read(MAX_IMAGE_BYTES+1)
        if len(payload)>MAX_IMAGE_BYTES: return HttpResponse(status=413)
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as source:
                if source.format not in {'PNG','JPEG','WEBP'} or source.width*source.height>MAX_SOURCE_PIXELS:
                    raise ValueError('Unsupported image')
                ImageOps.exif_transpose(source,in_place=True)
                if source.width*source.height>MAX_PIXELS:
                    scale=(MAX_PIXELS/(source.width*source.height))**0.5
                    width=max(1,int(source.width*scale));height=max(1,int(source.height*scale))
                    if width*height>MAX_PIXELS:
                        if width>height: width=MAX_PIXELS//height
                        else: height=MAX_PIXELS//width
                    source.thumbnail((width,height),Image.Resampling.LANCZOS)
                rgba=source.convert('RGBA')
                image=Image.new('RGB',rgba.size,'white');image.paste(rgba,mask=rgba.getchannel('A'))
                image.info.clear()
                output=BytesIO();image.save(output,'PNG');payload=output.getvalue()
        if len(payload)>MAX_IMAGE_BYTES: return HttpResponse(status=413)
    except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombWarning,Image.DecompressionBombError):
        return JsonResponse({'error':{'code':'INVALID_IMAGE'}},status=422)
    with transaction.atomic():
        record=ReportRecord.objects.select_for_update().get(pk=report_id)
        if not ReportGrant.objects.filter(report=record,user=request.user).exists(): return HttpResponse(status=403)
        latest=ReviewRevision.objects.filter(report=record).order_by('-revision').first()
        if latest is None or latest.review_data['status']!='DRAFT': return HttpResponse(status=409)
        assets=list(PresentationFigure.objects.filter(report=record).values_list('content',flat=True))
        if len(assets)>=100 or sum(len(item) for item in assets)+len(payload)>MAX_REPORT_BYTES:
            return HttpResponse(status=413)
        figure=PresentationFigure.objects.create(report=record,content=payload,sha256=sha256(payload).hexdigest(),uploaded_by=request.user)
    response=JsonResponse({'figureId':str(figure.pk),'url':reverse('presentation-figure',args=[report_id,figure.pk])},status=201)
    response['Cache-Control']='no-store'
    return response


@require_GET
def figure_content(request,report_id,figure_id):
    grant=_grant(request,report_id)
    if grant is None: return HttpResponse(status=401)
    figure=get_object_or_404(PresentationFigure,report=grant.report,pk=figure_id)
    response=HttpResponse(bytes(figure.content),content_type='image/png')
    response['Cache-Control']='no-store';response['X-Content-Type-Options']='nosniff'
    response['Content-Security-Policy']="default-src 'none'"
    return response

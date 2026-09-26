"""Explicit loopback demonstration access, never a production auth fallback."""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin


def demo_principal(request, report_id: str | None):
    if not getattr(settings, 'PRONTO_DEMO_ENABLED', False):
        return None
    reports = getattr(settings, 'PRONTO_DEMO_REPORTS', ())
    if not reports or (report_id is not None and report_id not in reports):
        return None
    if request.resolver_match.url_name not in {'report-index', 'report-detail', 'review-save', 'review-finalize', 'report-print'}:
        return None
    if request.META.get('REMOTE_ADDR') != '127.0.0.1' or request.get_host().split(':')[0] not in {'127.0.0.1', 'localhost'}:
        return None
    return get_user_model().objects.filter(pk=getattr(settings, 'PRONTO_DEMO_USER_ID', None),
        is_active=True, is_staff=False, is_superuser=False).first()


class DemoAccessMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not getattr(settings, 'PRONTO_DEMO_ENABLED', False):
            return None
        if (request.META.get('REMOTE_ADDR') != '127.0.0.1'
                or request.get_host().split(':')[0] not in {'127.0.0.1', 'localhost'}
                or any(key in request.META for key in ('HTTP_FORWARDED', 'HTTP_X_FORWARDED_FOR', 'HTTP_X_FORWARDED_HOST'))):
            return HttpResponse(status=403)

    def process_view(self, request, view, args, kwargs):
        user = demo_principal(request, kwargs.get('report_id'))
        if user is not None:
            request.user = user

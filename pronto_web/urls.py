"""Only the authenticated read route is exposed in this slice."""

from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from pronto_web.reports.views import alignment_component, report_detail, report_index


urlpatterns = [
    path("accounts/login/", LoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(next_page="/accounts/login/"), name="logout"),
    path("reports/", report_index, name="report-index"),
    path("reports/<str:report_id>/alignments/<str:source_id>/<str:component>/", alignment_component, name="alignment-component"),
    path("reports/<str:report_id>/", report_detail, name="report-detail"),
]

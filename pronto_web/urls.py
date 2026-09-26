"""Only the authenticated read route is exposed in this slice."""

from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from pronto_web.reports.print_audit import print_request

from pronto_web.reports.views import (
    alignment_component, cancel_alignment_save, complete_alignment_save,
    delete_saved_alignment, finalize_review, preserve_registered_alignment,
    report_detail, report_index, save_review_revision, start_alignment_save,
    upload_alignment_chunk,
)


urlpatterns = [
    path('reports/<str:report_id>/print-requests/', print_request, name='report-print'),
    path("accounts/login/", LoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(next_page="/accounts/login/"), name="logout"),
    path("reports/", report_index, name="report-index"),
    path("reports/<str:report_id>/revisions/", save_review_revision, name="review-save"),
    path("reports/<str:report_id>/finalizations/", finalize_review, name="review-finalize"),
    path("reports/<str:report_id>/alignments/save-sessions/", start_alignment_save,
         name="alignment-save-start"),
    path("reports/<str:report_id>/alignments/save-sessions/<uuid:session_id>/complete/",
         complete_alignment_save, name="alignment-save-complete"),
    path("reports/<str:report_id>/alignments/save-sessions/<uuid:session_id>/<str:component>/",
         upload_alignment_chunk, name="alignment-save-chunk"),
    path("reports/<str:report_id>/alignments/save-sessions/<uuid:session_id>/",
         cancel_alignment_save, name="alignment-save-cancel"),
    path("reports/<str:report_id>/alignments/<uuid:saved_id>/",
         delete_saved_alignment, name="alignment-saved-delete"),
    path("reports/<str:report_id>/alignments/<str:source_id>/preserve/",
         preserve_registered_alignment, name="alignment-preserve-registered"),
    path("reports/<str:report_id>/alignments/<str:source_id>/<str:component>/", alignment_component, name="alignment-component"),
    path("reports/<str:report_id>/", report_detail, name="report-detail"),
]

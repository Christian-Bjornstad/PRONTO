"""Private persisted inputs; contract validation still occurs on retrieval."""

from django.conf import settings
from django.db import models
from django.db.models import F, Q
import uuid


def opaque_alignment_key() -> str:
    return uuid.uuid4().hex


ALIGNMENT_BUILDS = [("GRCh37", "GRCh37"), ("GRCh38", "GRCh38")]
ALIGNMENT_ROLES = [
    ("TUMOUR_DNA", "TUMOUR_DNA"), ("NORMAL_DNA", "NORMAL_DNA"),
    ("TUMOUR_RNA", "TUMOUR_RNA"), ("NORMAL_RNA", "NORMAL_RNA"),
]
ALIGNMENT_FORMATS = [("bam", "bam"), ("cram", "cram")]


class ReportRecord(models.Model):
    report_id = models.CharField(max_length=128, primary_key=True)
    report_data = models.JSONField()


class ReportGrant(models.Model):
    report = models.ForeignKey(ReportRecord, on_delete=models.CASCADE, related_name="grants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["report", "user"], name="unique_report_grant")]


class ReportWriteGrant(models.Model):
    """Permission to preserve/delete alignments, independent of report reading."""

    report = models.ForeignKey(ReportRecord, on_delete=models.CASCADE, related_name="alignment_write_grants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["report", "user"], name="unique_report_write_grant")]


class ReviewRevision(models.Model):
    report = models.ForeignKey(ReportRecord, on_delete=models.CASCADE, related_name="reviews")
    revision = models.PositiveIntegerField()
    review_data = models.JSONField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["report", "revision"], name="unique_review_revision")]


class ReportAsset(models.Model):
    report = models.ForeignKey(ReportRecord, on_delete=models.CASCADE, related_name="assets")
    asset_id = models.CharField(max_length=128)
    content = models.BinaryField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["report", "asset_id"], name="unique_report_asset")]


class SavedAlignment(models.Model):
    """READY metadata only; complete bytes live outside the database/web root."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(ReportRecord, on_delete=models.PROTECT, related_name="saved_alignments")
    sample_id = models.CharField(max_length=128)
    reference_build = models.CharField(max_length=16, choices=ALIGNMENT_BUILDS)
    role = models.CharField(max_length=16, choices=ALIGNMENT_ROLES)
    format = models.CharField(max_length=4, choices=ALIGNMENT_FORMATS)
    data_key = models.CharField(max_length=64, unique=True)
    index_key = models.CharField(max_length=64, unique=True)
    data_size = models.PositiveBigIntegerField()
    index_size = models.PositiveBigIntegerField()
    data_sha256 = models.CharField(max_length=64)
    index_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=8, default="READY", choices=[("READY", "READY")])
    saved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["report", "sample_id", "reference_build", "role"],
                                    condition=Q(status="READY"), name="unique_ready_alignment_identity"),
            models.CheckConstraint(condition=Q(status="READY"), name="saved_alignment_ready_only"),
            models.CheckConstraint(condition=Q(data_size__gt=0) & Q(index_size__gt=0), name="saved_alignment_sizes_positive"),
        ]


class AlignmentUploadSession(models.Model):
    """Private, bounded staging lifecycle; no byte fields or filenames."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(ReportRecord, on_delete=models.PROTECT, related_name="alignment_uploads")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    sample_id = models.CharField(max_length=128)
    reference_build = models.CharField(max_length=16, choices=ALIGNMENT_BUILDS)
    role = models.CharField(max_length=16, choices=ALIGNMENT_ROLES)
    format = models.CharField(max_length=4, choices=ALIGNMENT_FORMATS)
    expected_data_size = models.PositiveBigIntegerField()
    expected_index_size = models.PositiveBigIntegerField()
    received_data_bytes = models.PositiveBigIntegerField(default=0)
    received_index_bytes = models.PositiveBigIntegerField(default=0)
    staging_data_key = models.CharField(max_length=64, default=opaque_alignment_key, unique=True)
    staging_index_key = models.CharField(max_length=64, default=opaque_alignment_key, unique=True)
    expires_at = models.DateTimeField()
    state = models.CharField(max_length=12, default="OPEN", choices=[
        ("OPEN", "OPEN"), ("VALIDATING", "VALIDATING"), ("COMPLETED", "COMPLETED"),
        ("CANCELLED", "CANCELLED"), ("FAILED", "FAILED"),
    ])
    saved_alignment = models.ForeignKey(SavedAlignment, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(state__in=["OPEN", "VALIDATING", "COMPLETED", "CANCELLED", "FAILED"]),
                                   name="upload_state_valid"),
            models.CheckConstraint(condition=Q(expected_data_size__gt=0) & Q(expected_index_size__gt=0),
                                   name="upload_expected_sizes_positive"),
            models.CheckConstraint(condition=Q(received_data_bytes__lte=F("expected_data_size"))
                                   & Q(received_index_bytes__lte=F("expected_index_size")),
                                   name="upload_offsets_in_bounds"),
        ]


class AlignmentEvent(models.Model):
    """Minimal audit record that survives saved-pair deletion."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(ReportRecord, on_delete=models.PROTECT, related_name="alignment_events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    saved_id = models.UUIDField()
    action = models.CharField(max_length=6, choices=[("SAVE", "SAVE"), ("COPY", "COPY"), ("DELETE", "DELETE")])
    created_at = models.DateTimeField(auto_now_add=True)

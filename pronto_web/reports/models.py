"""Private persisted inputs; contract validation still occurs on retrieval."""

from django.conf import settings
from django.db import models


class ReportRecord(models.Model):
    report_id = models.CharField(max_length=128, primary_key=True)
    report_data = models.JSONField()


class ReportGrant(models.Model):
    report = models.ForeignKey(ReportRecord, on_delete=models.CASCADE, related_name="grants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["report", "user"], name="unique_report_grant")]


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

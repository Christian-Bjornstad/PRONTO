from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="ReportRecord",
            fields=[
                ("report_id", models.CharField(max_length=128, primary_key=True, serialize=False)),
                ("report_data", models.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name="ReportAsset",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("asset_id", models.CharField(max_length=128)),
                ("content", models.BinaryField()),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="assets", to="reports.reportrecord")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("report", "asset_id"), name="unique_report_asset")]},
        ),
        migrations.CreateModel(
            name="ReportGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="grants", to="reports.reportrecord")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("report", "user"), name="unique_report_grant")]},
        ),
        migrations.CreateModel(
            name="ReviewRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("revision", models.PositiveIntegerField()),
                ("review_data", models.JSONField()),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="reviews", to="reports.reportrecord")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("report", "revision"), name="unique_review_revision")]},
        ),
    ]

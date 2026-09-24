from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReviewAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                            serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=16, choices=[
                    ("SAVE_DRAFT", "SAVE_DRAFT"), ("FINALIZE", "FINALIZE"),
                ])),
                ("revision", models.PositiveIntegerField()),
                ("occurred_at", models.DateTimeField()),
                ("report", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                              related_name="review_audits", to="reports.reportrecord")),
                ("actor", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             to=settings.AUTH_USER_MODEL)),
            ],
            options={"constraints": [
                models.UniqueConstraint(fields=("report", "revision"),
                                        name="unique_review_audit_revision"),
            ]},
        ),
    ]

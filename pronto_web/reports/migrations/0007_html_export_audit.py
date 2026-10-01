import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('reports', '0006_reset_draft'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportHtmlExportAudit',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name='ID')),
                ('revision', models.PositiveIntegerField()),
                ('request_id', models.UUIDField()),
                ('declared_initials', models.CharField(max_length=8)),
                ('attribution_method', models.CharField(max_length=16, default='SELF_REPORTED')),
                ('action', models.CharField(max_length=24, default='HTML_DOWNLOAD_REQUESTED')),
                ('requested_at', models.DateTimeField()),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            to=settings.AUTH_USER_MODEL)),
                ('report', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                             to='reports.reportrecord')),
            ],
            options={'constraints': [models.UniqueConstraint(
                fields=('report', 'request_id'), name='unique_report_html_request')]},
        ),
    ]

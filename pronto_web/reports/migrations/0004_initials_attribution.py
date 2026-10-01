from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('reports', '0003_merge_review_alignment')]
    operations = [
        migrations.AddField(model_name='reviewaudit', name='declared_initials', field=models.CharField(max_length=8, null=True, blank=True)),
        migrations.AddField(model_name='reviewaudit', name='attribution_method', field=models.CharField(max_length=16, null=True, blank=True)),
    ]

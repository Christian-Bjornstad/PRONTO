"""Join the independently reviewed audit and alignment migration histories."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("reports", "0002_review_audit"),
        ("reports", "0002_alignment_storage"),
    ]

    operations = []

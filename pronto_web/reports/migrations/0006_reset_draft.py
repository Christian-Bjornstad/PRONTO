from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("reports", "0005_print_audit")]

    operations = [
        migrations.AlterField(
            model_name="reviewaudit",
            name="action",
            field=models.CharField(max_length=16, choices=[
                ("SAVE_DRAFT", "SAVE_DRAFT"),
                ("FINALIZE", "FINALIZE"),
                ("RESET_DRAFT", "RESET_DRAFT"),
            ]),
        ),
    ]

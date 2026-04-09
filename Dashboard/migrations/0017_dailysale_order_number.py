from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0016_claim"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailysale",
            name="order_number",
            field=models.CharField(
                blank=True,
                help_text="Optional external reference; if empty, an internal # is shown in lists.",
                max_length=50,
            ),
        ),
    ]

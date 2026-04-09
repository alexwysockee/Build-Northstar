from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0014_inventory_order_cancel_audit"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailysale",
            name="entered_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="daily_sales_entered",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

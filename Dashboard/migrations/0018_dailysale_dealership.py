"""
DailySale.dealership was in models but never migrated; backfill existing rows.
"""

import django.db.models.deletion
from django.db import migrations, models


def assign_default_dealership(apps, schema_editor):
    DailySale = apps.get_model("Dashboard", "DailySale")
    Dealership = apps.get_model("Dashboard", "Dealership")
    default = Dealership.objects.order_by("pk").first()
    if not default:
        default = Dealership.objects.create(name="Default Dealership")
    DailySale.objects.filter(dealership_id__isnull=True).update(dealership_id=default.pk)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0017_dailysale_order_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="dailysale",
            name="dealership",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="daily_sales",
                to="Dashboard.dealership",
            ),
        ),
        migrations.RunPython(assign_default_dealership, noop_reverse),
        migrations.AlterField(
            model_name="dailysale",
            name="dealership",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="daily_sales",
                to="Dashboard.dealership",
            ),
        ),
    ]

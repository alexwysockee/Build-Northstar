from django.db import migrations


def backfill_order_numbers(apps, schema_editor):
    DailySale = apps.get_model("Dashboard", "DailySale")
    for row in DailySale.objects.all().only("pk", "order_number").iterator():
        if not (row.order_number or "").strip():
            DailySale.objects.filter(pk=row.pk).update(order_number=f"NS-{row.pk:06d}")


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0018_dailysale_dealership"),
    ]

    operations = [
        migrations.RunPython(backfill_order_numbers, noop_reverse),
    ]

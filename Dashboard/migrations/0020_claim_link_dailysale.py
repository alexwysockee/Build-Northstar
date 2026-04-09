from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q


def link_claims_to_sales(apps, schema_editor):
    Claim = apps.get_model("Dashboard", "Claim")
    DailySale = apps.get_model("Dashboard", "DailySale")

    for c in Claim.objects.all().iterator():
        deal_id = c.dealership_id
        prod_id = c.product_id
        on_raw = (getattr(c, "order_number", None) or "").strip()
        base = DailySale.objects.filter(dealership_id=deal_id, product_id=prod_id)
        sale = None

        if on_raw:
            sale = base.filter(order_number__iexact=on_raw).first()
            if sale is None and on_raw.isdigit():
                sale = base.filter(pk=int(on_raw)).first()
            if sale is None:
                ru = on_raw.upper()
                if ru.startswith("NS-") and ru[3:].strip().isdigit():
                    sale = base.filter(pk=int(ru[3:].strip())).first()
            if sale is None:
                q_norm = on_raw.lstrip("#").strip()
                q_filter = Q(order_number__icontains=on_raw)
                if q_norm != on_raw:
                    q_filter |= Q(order_number__icontains=q_norm)
                candidates = list(base.filter(q_filter).order_by("-date", "-id")[:2])
                if len(candidates) == 1:
                    sale = candidates[0]

        if sale:
            Claim.objects.filter(pk=c.pk).update(daily_sale_id=sale.pk)

    Claim.objects.filter(daily_sale__isnull=True).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0019_backfill_dailysale_order_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="claim",
            name="daily_sale",
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="claims",
                to="Dashboard.dailysale",
            ),
        ),
        migrations.RunPython(link_claims_to_sales, noop_reverse),
        migrations.RemoveField(model_name="claim", name="dealership"),
        migrations.RemoveField(model_name="claim", name="product"),
        migrations.RemoveField(model_name="claim", name="order_number"),
        migrations.AlterField(
            model_name="claim",
            name="daily_sale",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="claims",
                to="Dashboard.dailysale",
            ),
        ),
    ]

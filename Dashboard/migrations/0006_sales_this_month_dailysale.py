from django.db import migrations, models
from django.utils import timezone


def migrate_to_daily_sales(apps, schema_editor):
    SalesProduct = apps.get_model("Dashboard", "SalesProduct")
    DailySale = apps.get_model("Dashboard", "DailySale")
    today = timezone.now().date()
    for product in SalesProduct.objects.all():
        if product.this_week > 0:
            DailySale.objects.create(
                product=product,
                date=today,
                amount=product.this_week,
            )


def reverse_migrate(apps, schema_editor):
    DailySale = apps.get_model("Dashboard", "DailySale")
    DailySale.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0005_add_sales_product"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailySale",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("amount", models.PositiveIntegerField(default=0)),
                ("product", models.ForeignKey(on_delete=models.CASCADE, to="Dashboard.salesproduct")),
            ],
            options={
                "ordering": ["-date", "id"],
            },
        ),
        migrations.RunPython(migrate_to_daily_sales, reverse_migrate),
        migrations.RemoveField(
            model_name="salesproduct",
            name="today",
        ),
        migrations.RemoveField(
            model_name="salesproduct",
            name="this_week",
        ),
    ]

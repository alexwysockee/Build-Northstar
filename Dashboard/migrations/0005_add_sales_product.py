from django.db import migrations, models


def seed_sales_products(apps, schema_editor):
    SalesProduct = apps.get_model("Dashboard", "SalesProduct")
    if SalesProduct.objects.exists():
        return
    defaults = [
        ("Rust Protection", 6, 32, 35, 1),
        ("Extended Warranty", 3, 18, 16, 2),
        ("Paint Protection", 2, 12, 15, 3),
        ("Fabric Guard", 1, 6, 13, 4),
    ]
    for order, (name, today, this_week, goal, product_id) in enumerate(defaults):
        SalesProduct.objects.create(
            name=name, today=today, this_week=this_week, goal=goal,
            display_order=order, product_id=product_id,
        )


def remove_sales_products_seed(apps, schema_editor):
    SalesProduct = apps.get_model("Dashboard", "SalesProduct")
    SalesProduct.objects.filter(
        name__in=["Rust Protection", "Extended Warranty", "Paint Protection", "Fabric Guard"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0004_add_user_groups"),
    ]

    operations = [
        migrations.CreateModel(
            name="SalesProduct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200)),
                ("today", models.PositiveIntegerField(default=0)),
                ("this_week", models.PositiveIntegerField(default=0)),
                ("goal", models.PositiveIntegerField(default=1)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("product_id", models.PositiveIntegerField(blank=True, null=True)),
            ],
            options={
                "ordering": ["display_order", "id"],
            },
        ),
        migrations.RunPython(seed_sales_products, remove_sales_products_seed),
    ]

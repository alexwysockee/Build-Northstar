# Aligns DB with models (tracks_inventory, ProductInventory, field help_text updates).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0021_inspection_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesproduct",
            name="tracks_inventory",
            field=models.BooleanField(
                default=True,
                help_text="If False (e.g. warranties), item is excluded from inventory and stock checks.",
            ),
        ),
        migrations.AlterField(
            model_name="claim",
            name="quantity",
            field=models.PositiveIntegerField(
                help_text="Units covered by this claim; must not exceed the units on the linked sale.",
            ),
        ),
        migrations.AlterField(
            model_name="dailysale",
            name="order_number",
            field=models.CharField(
                blank=True,
                help_text="Set automatically when the sale is saved (NS-######). Not exposed on portal forms.",
                max_length=50,
            ),
        ),
        migrations.AlterField(
            model_name="salesproduct",
            name="goal",
            field=models.PositiveIntegerField(default=1, help_text="Monthly sales goal"),
        ),
        migrations.CreateModel(
            name="ProductInventory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=0)),
                ("last_updated", models.DateTimeField(auto_now=True)),
                (
                    "dealership",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_levels",
                        to="Dashboard.dealership",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inventory_levels",
                        to="Dashboard.salesproduct",
                    ),
                ),
            ],
            options={
                "ordering": ["dealership__name", "product__display_order", "product__id"],
            },
        ),
        migrations.AddConstraint(
            model_name="productinventory",
            constraint=models.UniqueConstraint(fields=("product", "dealership"), name="unique_product_dealership_inventory"),
        ),
    ]

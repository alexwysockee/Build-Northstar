from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0006_sales_this_month_dailysale"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesproduct",
            name="price",
            field=models.DecimalField(decimal_places=2, default=0, help_text="Product price", max_digits=10),
        ),
    ]

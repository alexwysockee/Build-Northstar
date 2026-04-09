import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0009_dealership_badge_and_default_home"),
        ("Profile", "0001_userprofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="dealership",
            field=models.ForeignKey(
                blank=True,
                help_text="Sales Rep / Dealership User home dealership for inventory scope.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="assigned_users",
                to="Dashboard.dealership",
            ),
        ),
    ]

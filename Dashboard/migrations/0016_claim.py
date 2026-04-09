from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0015_dailysale_entered_by"),
    ]

    operations = [
        migrations.CreateModel(
            name="Claim",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("customer_name", models.CharField(max_length=200)),
                ("order_number", models.CharField(blank=True, max_length=50)),
                ("quantity", models.PositiveIntegerField()),
                ("reason", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("approved", "Approved"),
                            ("rejected", "Rejected"),
                            ("received", "Received"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("date_submitted", models.DateTimeField(auto_now_add=True)),
                (
                    "dealership",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="claims",
                        to="Dashboard.dealership",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="claims",
                        to="Dashboard.salesproduct",
                    ),
                ),
                (
                    "submitted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="claims_submitted",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-date_submitted", "-id"],
            },
        ),
    ]

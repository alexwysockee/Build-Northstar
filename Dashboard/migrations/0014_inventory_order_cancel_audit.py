from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def _table_columns(connection, table_name):
    with connection.cursor() as cursor:
        if table_name not in connection.introspection.table_names(cursor):
            return set()
        desc = connection.introspection.get_table_description(cursor, table_name)
        return {c.name for c in desc}


def add_inventory_order_audit_columns(apps, schema_editor):
    """Table may pre-exist without migration history; add new columns if missing."""
    connection = schema_editor.connection
    table = "Dashboard_inventoryorder"
    existing = _table_columns(connection, table)
    if not existing:
        return
    with connection.cursor() as cursor:
        if "delivered_by_id" not in existing:
            cursor.execute(
                f"ALTER TABLE {connection.ops.quote_name(table)} "
                f"ADD COLUMN {connection.ops.quote_name('delivered_by_id')} "
                f"INTEGER NULL REFERENCES {connection.ops.quote_name('auth_user')} "
                f"({connection.ops.quote_name('id')})"
            )
        if "cancelled_at" not in existing:
            cursor.execute(
                f"ALTER TABLE {connection.ops.quote_name(table)} "
                f"ADD COLUMN {connection.ops.quote_name('cancelled_at')} "
                f"DATETIME NULL"
            )
        if "cancelled_by_id" not in existing:
            cursor.execute(
                f"ALTER TABLE {connection.ops.quote_name(table)} "
                f"ADD COLUMN {connection.ops.quote_name('cancelled_by_id')} "
                f"INTEGER NULL REFERENCES {connection.ops.quote_name('auth_user')} "
                f"({connection.ops.quote_name('id')})"
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0013_c3_lachute_dark_red"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="InventoryOrder",
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
                        ("quantity_requested", models.PositiveIntegerField()),
                        (
                            "status",
                            models.CharField(
                                choices=[
                                    ("pending", "Pending"),
                                    ("delivered", "Delivered"),
                                    ("cancelled", "Cancelled"),
                                ],
                                default="pending",
                                max_length=20,
                            ),
                        ),
                        ("notes", models.TextField(blank=True)),
                        ("date_requested", models.DateTimeField(auto_now_add=True)),
                        ("date_received", models.DateTimeField(blank=True, null=True)),
                        (
                            "product",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="inventory_orders",
                                to="Dashboard.salesproduct",
                            ),
                        ),
                        (
                            "dealership",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="inventory_orders",
                                to="Dashboard.dealership",
                            ),
                        ),
                        (
                            "requested_by",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="inventory_orders_submitted",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        (
                            "delivered_by",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="fulfilled_inventory_orders",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                        ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                        (
                            "cancelled_by",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="cancelled_inventory_orders",
                                to=settings.AUTH_USER_MODEL,
                            ),
                        ),
                    ],
                    options={
                        "ordering": ["-date_requested", "-id"],
                    },
                ),
            ],
            database_operations=[
                migrations.RunPython(add_inventory_order_audit_columns, noop_reverse),
            ],
        ),
    ]

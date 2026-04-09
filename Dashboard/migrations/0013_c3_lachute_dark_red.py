from django.db import migrations


def add_lachute(apps, schema_editor):
    Dealership = apps.get_model("Dashboard", "Dealership")
    Dealership.objects.get_or_create(
        name="C3 Lachute",
        defaults={"badge_css_class": "ns-badge-dealership-lachute"},
    )


def remove_lachute(apps, schema_editor):
    Dealership = apps.get_model("Dashboard", "Dealership")
    Dealership.objects.filter(name="C3 Lachute").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0012_dealership_badge_colors_by_location"),
    ]

    operations = [
        migrations.RunPython(add_lachute, remove_lachute),
    ]

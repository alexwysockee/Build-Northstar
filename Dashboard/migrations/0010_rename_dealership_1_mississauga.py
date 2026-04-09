from django.db import migrations


def rename_main_office(apps, schema_editor):
    Dealership = apps.get_model("Dashboard", "Dealership")
    Dealership.objects.filter(pk=1).update(name="C3 Mississauga")


def reverse_rename(apps, schema_editor):
    Dealership = apps.get_model("Dashboard", "Dealership")
    Dealership.objects.filter(pk=1, name="C3 Mississauga").update(name="Default Dealership")


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0009_dealership_badge_and_default_home"),
    ]

    operations = [
        migrations.RunPython(rename_main_office, reverse_rename),
    ]

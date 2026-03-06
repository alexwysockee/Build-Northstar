# Generated for Build-Northstar user groups

from django.db import migrations


def create_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    groups = [
        "Management",
        "Back Office",
        "Sales Rep",
        "Dealership User",
    ]
    for name in groups:
        Group.objects.get_or_create(name=name)


def remove_groups(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(
        name__in=[
            "Management",
            "Back Office",
            "Sales Rep",
            "Dealership User",
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_groups, remove_groups),
    ]

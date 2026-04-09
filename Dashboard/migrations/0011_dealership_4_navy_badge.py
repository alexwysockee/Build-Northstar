from django.db import migrations


def set_navy_badge_for_pk4(apps, schema_editor):
    Dealership = apps.get_model("Dashboard", "Dealership")
    Dealership.objects.filter(pk=4).update(badge_css_class="ns-badge-navy")


def reverse_badge(apps, schema_editor):
    Dealership = apps.get_model("Dashboard", "Dealership")
    d = Dealership.objects.filter(pk=4).first()
    if d and d.badge_css_class == "ns-badge-navy":
        d.badge_css_class = "ns-badge-c3-toronto"
        d.save(update_fields=["badge_css_class"])


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0010_rename_dealership_1_mississauga"),
    ]

    operations = [
        migrations.RunPython(set_navy_badge_for_pk4, reverse_badge),
    ]

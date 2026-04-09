from django.db import migrations


def set_badge_colors(apps, schema_editor):
    Dealership = apps.get_model("Dashboard", "Dealership")
    by_name = {
        "C3 Mississauga": "ns-badge-dealership-mississauga",
        "C3 Edmonton": "ns-badge-dealership-edmonton",
        "C3 Calgary": "ns-badge-dealership-calgary",
        "C3 Toronto": "ns-badge-dealership-toronto",
    }
    for name, badge_class in by_name.items():
        Dealership.objects.filter(name=name).update(badge_css_class=badge_class)


def reverse_badges(apps, schema_editor):
    Dealership = apps.get_model("Dashboard", "Dealership")
    Dealership.objects.all().update(badge_css_class="bg-dark")


class Migration(migrations.Migration):

    dependencies = [
        ("Dashboard", "0011_dealership_4_navy_badge"),
    ]

    operations = [
        migrations.RunPython(set_badge_colors, reverse_badges),
    ]

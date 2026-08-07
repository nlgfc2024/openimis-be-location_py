from django.db import migrations

from core.utils import insert_role_right_for_system, remove_role_right_for_system


IMIS_ADMINISTRATOR_ROLE_IS_SYSTEM = 64
CATCHMENT_RIGHTS = [121911, 121912, 121913, 121914]


def add_rights(apps, schema_editor):
    for right_id in CATCHMENT_RIGHTS:
        insert_role_right_for_system(
            IMIS_ADMINISTRATOR_ROLE_IS_SYSTEM,
            right_id,
            apps,
        )


def remove_rights(apps, schema_editor):
    for right_id in CATCHMENT_RIGHTS:
        remove_role_right_for_system(
            IMIS_ADMINISTRATOR_ROLE_IS_SYSTEM,
            right_id,
            apps,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("location", "0028_catchment_catchmentdistrict_and_more"),
    ]

    operations = [
        migrations.RunPython(add_rights, remove_rights),
    ]
from django.db import migrations

from core.utils import insert_role_right_for_system, remove_role_right_for_system


IMIS_ADMINISTRATOR_ROLE_IS_SYSTEM = 64
CLUSTER_ZONE_RIGHTS = [121921, 121922, 121923, 121924]


def add_rights(apps, schema_editor):
    for right_id in CLUSTER_ZONE_RIGHTS:
        insert_role_right_for_system(IMIS_ADMINISTRATOR_ROLE_IS_SYSTEM, right_id, apps)


def remove_rights(apps, schema_editor):
    for right_id in CLUSTER_ZONE_RIGHTS:
        remove_role_right_for_system(IMIS_ADMINISTRATOR_ROLE_IS_SYSTEM, right_id, apps)


class Migration(migrations.Migration):
    dependencies = [("location", "0034_register_zone_menu")]

    operations = [migrations.RunPython(add_rights, remove_rights)]

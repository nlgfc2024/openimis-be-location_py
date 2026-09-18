"""Include Clusters in configured Administration submenus."""
import json

from django.db import migrations


def add_cluster_menu(config):
    for menu in config.get("menus", []):
        if menu.get("id") != "AdminMainMenu":
            continue
        submenus = menu.setdefault("submenus", [])
        if any(item.get("id") == "location.clusters" for item in submenus):
            return False
        location_positions = [
            item["position"] for item in submenus
            if item.get("id") in {"admin.locations", "location.microCatchments", "location.catchments", "admin.zones"}
            and isinstance(item.get("position"), (int, float))
        ]
        position = max(location_positions, default=0) + 1
        for item in submenus:
            if isinstance(item.get("position"), (int, float)) and item["position"] >= position:
                item["position"] += 1
        submenus.append({"id": "location.clusters", "position": position})
        return True
    return False


def register_cluster_menu(apps, schema_editor):
    configurations = apps.get_model("core", "ModuleConfiguration")
    for row in configurations.objects.using(schema_editor.connection.alias).filter(layer="fe", module="fe-core"):
        config = json.loads(row.config or "{}")
        if add_cluster_menu(config):
            row.config = json.dumps(config)
            row.save(update_fields=["config"], using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [("location", "0031_cluster")]
    operations = [migrations.RunPython(register_cluster_menu, migrations.RunPython.noop)]

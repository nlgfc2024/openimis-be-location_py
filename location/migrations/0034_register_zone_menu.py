import json

from django.db import migrations


def rename_zone_menu(apps, schema_editor):
    configurations = apps.get_model("core", "ModuleConfiguration")
    for configuration in configurations.objects.using(schema_editor.connection.alias).filter(layer="fe", module="fe-core"):
        config = json.loads(configuration.config or "{}")
        changed = False
        for menu in config.get("menus", []):
            if menu.get("id") != "AdminMainMenu":
                continue
            for item in menu.get("submenus", []):
                if item.get("id") == "admin.hotspots":
                    item["id"] = "admin.zones"
                    item["position"] = item.get("position", 0)
                    changed = True
        if changed:
            configuration.config = json.dumps(config)
            configuration.save(update_fields=["config"], using=schema_editor.connection.alias)


def reverse_zone_menu(apps, schema_editor):
    configurations = apps.get_model("core", "ModuleConfiguration")
    for configuration in configurations.objects.using(schema_editor.connection.alias).filter(layer="fe", module="fe-core"):
        config = json.loads(configuration.config or "{}")
        changed = False
        for menu in config.get("menus", []):
            for item in menu.get("submenus", []):
                if item.get("id") == "admin.zones":
                    item["id"] = "admin.hotspots"
                    changed = True
        if changed:
            configuration.config = json.dumps(config)
            configuration.save(update_fields=["config"], using=schema_editor.connection.alias)


class Migration(migrations.Migration):
    dependencies = [("location", "0033_zone_cluster")]
    operations = [migrations.RunPython(rename_zone_menu, reverse_zone_menu)]

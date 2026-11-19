"""Place the dashboard entry in a configured CoreMIS menu allowlist."""
import json

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from core.models import ModuleConfiguration

ENTRY_ID = "location.geospatial"
DASHBOARD_MENU = "OpenSearchReportsMenu"


def place_geospatial_menu(config):
    menus = config.get("menus")
    if not menus:
        return False  # No allowlist: the frontend contribution provides the link.
    original = json.dumps(menus, sort_keys=True)
    existing = next((item.copy() for menu in menus for item in menu.get("submenus", [])
                     if item.get("id") == ENTRY_ID), {"id": ENTRY_ID})
    dashboard = next((menu for menu in menus if menu.get("id") == DASHBOARD_MENU), None)
    if dashboard is None:
        dashboard = {"id": DASHBOARD_MENU, "submenus": []}
        menus.append(dashboard)
    current = next((item.copy() for item in dashboard.get("submenus", []) if item.get("id") == ENTRY_ID), None)
    for menu in menus:
        if "submenus" in menu:
            menu["submenus"] = [item for item in menu["submenus"] if item.get("id") != ENTRY_ID]
    items = dashboard.setdefault("submenus", [])
    entry = current or existing
    if current is None or not isinstance(entry.get("position"), (int, float)) or entry["position"] <= 0:
        entry["position"] = max((item["position"] for item in items
                                 if isinstance(item.get("position"), (int, float))), default=0) + 1
    items.append(entry)
    return json.dumps(menus, sort_keys=True) != original


class Command(BaseCommand):
    help = "Place Geospatial dashboard under Dashboards, preserving other menu entries and permissions."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Save the updated menu configuration.")

    @transaction.atomic
    def handle(self, *args, **options):
        row = ModuleConfiguration.objects.select_for_update().filter(
            Q(is_disabled_until__isnull=True) | Q(is_disabled_until__lt=timezone.now()),
            module="fe-core", layer="fe",
        ).first()
        if row is None:
            self.stdout.write("No custom menu allowlist; the default dashboard contribution will be used.")
            return
        config = json.loads(row.config)
        changed = place_geospatial_menu(config)
        if changed and options["apply"]:
            row.config = json.dumps(config)
            row.save(update_fields=["config"])
        self.stdout.write("Geospatial dashboard menu: " + (
            "updated under Dashboards." if changed and options["apply"] else
            "update available; use --apply to save." if changed else "already configured."))

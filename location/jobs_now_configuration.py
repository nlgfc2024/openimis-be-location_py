"""Explicit Jobs-Now configuration; never executed by schema migrations."""

LOCATION_RIGHTS = {
    "clusters": (121921, 121922, 121923, 121924),
    "hotspots": (121925, 121926, 121927, 121928),
    "zones": (121931, 121932, 121933, 121934),
}


def add_jobs_now_menus(config):
    changed = False
    for menu in config.get("menus", []):
        if menu.get("id") != "AdminMainMenu":
            continue
        items = menu.setdefault("submenus", [])
        for menu_id in ("location.clusters", "admin.zones"):
            if any(item.get("id") == menu_id for item in items):
                continue
            position = max(
                (item["position"] for item in items if isinstance(item.get("position"), (int, float))),
                default=0,
            ) + 1
            items.append({"id": menu_id, "position": position})
            changed = True
    return changed

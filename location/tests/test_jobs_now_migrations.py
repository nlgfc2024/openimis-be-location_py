from importlib import import_module

from django.apps import apps
from django.db import migrations
from django.db.migrations.state import ProjectState
from django.test import SimpleTestCase


class JobsNowMigrationTest(SimpleTestCase):
    def test_schema_changes_only_create_new_entities(self):
        expected = {"0031_cluster": ["Cluster"], "0032_zone": ["Zone", "ZoneVillage"]}
        for name, models in expected.items():
            migration = import_module(f"location.migrations.{name}").Migration(name, "location")
            self.assertEqual([operation.name for operation in migration.operations], models)
            self.assertTrue(all(isinstance(operation, migrations.CreateModel) for operation in migration.operations))
            self.assertTrue(all(operation.reversible for operation in migration.operations))

    def test_state_does_not_repurpose_hotspots_or_add_a_micro_catchment_parent_to_zones(self):
        state = ProjectState.from_apps(apps)
        hotspot = state.models[("location", "hotspot")].clone()
        villages = state.models[("location", "hotspotvillage")].clone()
        for name in ("zonevillage", "zone", "cluster"):
            state.remove_model("location", name)
        for name in ("0031_cluster", "0032_zone"):
            migration = import_module(f"location.migrations.{name}").Migration(name, "location")
            state = migration.mutate_state(state)
        self.assertEqual(state.models[("location", "hotspot")], hotspot)
        self.assertEqual(state.models[("location", "hotspotvillage")], villages)
        self.assertNotIn("micro_catchment", state.models[("location", "zone")].fields)

from copy import deepcopy
from importlib import import_module
from unittest import TestCase

add_cluster_menu = import_module("location.migrations.0032_register_cluster_menu").add_cluster_menu


class ClusterMenuTest(TestCase):
    def test_adds_cluster_after_locations_preserving_other_configuration(self):
        config = {"otherSetting": True, "menus": [{"id": "AdminMainMenu", "submenus": [
            {"id": "location.microCatchments", "position": 4},
            {"id": "location.catchments", "position": 5},
            {"id": "admin.hotspots", "position": 6},
            {"id": "profile.myProfile", "position": 7},
            {"App.enablePublicPage": True},
        ]}]}
        self.assertTrue(add_cluster_menu(config))
        entries = config["menus"][0]["submenus"]
        self.assertIn({"id": "location.clusters", "position": 7}, entries)
        self.assertIn({"id": "profile.myProfile", "position": 8}, entries)
        self.assertIn({"App.enablePublicPage": True}, entries)
        self.assertTrue(config["otherSetting"])
        once = deepcopy(config)
        self.assertFalse(add_cluster_menu(config))
        self.assertEqual(config, once)

    def test_default_menu_and_other_menus_remain_unchanged(self):
        for config in ({}, {"menus": [{"id": "TasksMainMenu", "submenus": []}]}):
            original = deepcopy(config)
            self.assertFalse(add_cluster_menu(config))
            self.assertEqual(config, original)

    def test_existing_cluster_placement_is_preserved(self):
        config = {"menus": [{"id": "AdminMainMenu", "submenus": [{"id": "location.clusters", "position": 2}]}]}
        original = deepcopy(config)
        self.assertFalse(add_cluster_menu(config))
        self.assertEqual(config, original)

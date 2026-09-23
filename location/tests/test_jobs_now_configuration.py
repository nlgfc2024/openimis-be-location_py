from copy import deepcopy
from unittest import TestCase

from location.jobs_now_configuration import LOCATION_RIGHTS, add_jobs_now_menus


class JobsNowConfigurationTest(TestCase):
    def test_additive_idempotent_menu_setup_preserves_hotspots_and_existing_positions(self):
        original = [{"id": "admin.hotspots", "position": 4}, {"id": "profile.myProfile", "position": 5}, {"App.enablePublicPage": True}]
        config = {"other": True, "menus": [{"id": "AdminMainMenu", "submenus": deepcopy(original)}]}
        self.assertTrue(add_jobs_now_menus(config))
        items = config["menus"][0]["submenus"]
        self.assertEqual(items[:3], original)
        self.assertEqual(items[3:], [{"id": "location.clusters", "position": 6}, {"id": "admin.zones", "position": 7}])
        once = deepcopy(config)
        self.assertFalse(add_jobs_now_menus(config))
        self.assertEqual(config, once)

    def test_unconfigured_menus_are_not_replaced(self):
        for config in ({}, {"menus": [{"id": "OtherMenu", "submenus": []}]}):
            original = deepcopy(config)
            self.assertFalse(add_jobs_now_menus(config))
            self.assertEqual(config, original)

    def test_each_entity_has_separate_permissions(self):
        rights = [right for values in LOCATION_RIGHTS.values() for right in values]
        self.assertEqual(len(rights), 12)
        self.assertEqual(len(set(rights)), 12)

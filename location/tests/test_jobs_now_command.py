import json
from io import StringIO

from django.core.management import call_command, CommandError
from django.test import TestCase

from core.models import ModuleConfiguration, Role, RoleRight


class JobsNowConfigurationCommandTest(TestCase):
    def setUp(self):
        self.config = {"menus": [{"id": "AdminMainMenu", "submenus": [{"id": "admin.hotspots", "position": 3}]}]}
        self.row = ModuleConfiguration.objects.create(layer="fe", module="fe-core", version="1", config=json.dumps(self.config))
        self.role = Role.objects.create(name="Jobs Now test", is_system=0, is_blocked=False)

    def test_default_preview_does_not_write_configuration_or_rights(self):
        call_command("configure_jobs_now_locations", role_id=self.role.pk, stdout=StringIO())
        self.row.refresh_from_db()
        self.assertEqual(json.loads(self.row.config), self.config)
        self.assertFalse(RoleRight.objects.filter(role=self.role).exists())

    def test_apply_is_idempotent_and_only_grants_the_selected_role(self):
        other = Role.objects.create(name="Other role", is_system=0, is_blocked=False)
        for _ in range(2):
            call_command("configure_jobs_now_locations", apply=True, role_id=self.role.pk, stdout=StringIO())
        self.row.refresh_from_db()
        items = json.loads(self.row.config)["menus"][0]["submenus"]
        self.assertEqual(items[0], self.config["menus"][0]["submenus"][0])
        self.assertEqual(len(items), 3)
        self.assertEqual(RoleRight.objects.filter(role=self.role).count(), 12)
        self.assertFalse(RoleRight.objects.filter(role=other).exists())

    def test_invalid_role_does_not_write_menus(self):
        with self.assertRaises(CommandError):
            call_command("configure_jobs_now_locations", apply=True, role_id=-999999, stdout=StringIO())
        self.row.refresh_from_db()
        self.assertEqual(json.loads(self.row.config), self.config)

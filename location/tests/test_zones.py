from types import SimpleNamespace

from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError

from location.clusters import Cluster
from location.gql_mutations import update_or_create_zone
from location.models import Location, Zone


@override_settings(ROW_SECURITY=False)
class ZoneCodeGenerationTest(TestCase):
    def setUp(self):
        self.user = SimpleNamespace(
            id_for_audit=1,
            is_anonymous=False,
            has_perms=lambda permissions: True,
        )
        self.district = Location.objects.create(code="10", name="District", type="R", audit_user_id=1)
        self.ta = Location.objects.create(code="102938", name="TA", type="D", parent=self.district, audit_user_id=1)
        self.cluster = Cluster.objects.create(code="10293801", name="Cluster", traditional_authority=self.ta, audit_user_id=1)
        self.gvh = Location.objects.create(code="10293801", name="GVH", type="W", parent=self.ta, audit_user_id=1)

    def payload(self, name):
        village = Location.objects.create(code="V" + str(Location.objects.count()), name=name, type="V", parent=self.gvh, audit_user_id=1)
        return {
            "name": name,
            "description": "",
            "cluster_uuid": str(self.cluster.uuid),
            "village_uuids": [str(village.uuid)],
            "audit_user_id": 1,
        }

    def test_zone_code_uses_cluster_prefix_and_increments(self):
        first = update_or_create_zone(self.payload("First"), self.user)
        second = update_or_create_zone(self.payload("Second"), self.user)
        self.assertEqual(first.code, "1029380101")
        self.assertEqual(second.code, "1029380102")

    def test_zone_code_is_immutable_on_update(self):
        first = update_or_create_zone(self.payload("First"), self.user)
        updated = update_or_create_zone({**self.payload("Renamed"), "uuid": str(first.uuid)}, self.user)
        self.assertEqual(updated.code, "1029380101")
        self.assertEqual(updated.name, "Renamed")

    def test_zone_requires_villages(self):
        with self.assertRaises(ValidationError):
            update_or_create_zone({**self.payload("Empty"), "village_uuids": []}, self.user)

    def test_village_cannot_be_assigned_to_two_zones(self):
        payload = self.payload("First")
        update_or_create_zone(dict(payload), self.user)
        with self.assertRaises(ValidationError):
            update_or_create_zone({**payload, "name": "Second"}, self.user)

    def test_changing_cluster_revalidates_retained_villages(self):
        zone = update_or_create_zone(self.payload("First"), self.user)
        other_ta = Location.objects.create(code="OTHER", name="Other TA", type="D", parent=self.district, audit_user_id=1)
        other_cluster = Cluster.objects.create(code="OTHER01", name="Other", traditional_authority=other_ta, audit_user_id=1)
        with self.assertRaises(ValidationError):
            update_or_create_zone({"uuid": str(zone.uuid), "name": "Moved", "cluster_uuid": str(other_cluster.uuid)}, self.user)
        zone.refresh_from_db()
        self.assertEqual(zone.cluster_id, self.cluster.id)

    def test_edit_preserves_villages_when_omitted(self):
        zone = update_or_create_zone(self.payload("First"), self.user)
        village_ids = list(zone.villages.values_list("id", flat=True))
        update_or_create_zone({"uuid": str(zone.uuid), "name": "Renamed", "cluster_uuid": str(self.cluster.uuid)}, self.user)
        self.assertEqual(list(zone.villages.values_list("id", flat=True)), village_ids)

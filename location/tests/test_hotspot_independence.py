from types import SimpleNamespace

from django.test import TestCase, override_settings

from location.gql_mutations import update_or_create_hotspot, update_or_create_zone
from location.models import Cluster, Hotspot, Location, MicroCatchment, MicroCatchmentGVH, Zone


@override_settings(ROW_SECURITY=False)
class HotspotIndependenceTest(TestCase):
    def test_hotspot_and_zone_can_use_the_same_village_without_changing_each_other(self):
        user = SimpleNamespace(is_anonymous=False, is_superuser=True, id_for_audit=1)
        district = Location.objects.create(type="R", code="INDEP-R", name="District", audit_user_id=1)
        ta = Location.objects.create(type="D", code="INDEP-D", name="TA", parent=district, audit_user_id=1)
        gvh = Location.objects.create(type="W", code="INDEP-W", name="GVH", parent=ta, audit_user_id=1)
        village = Location.objects.create(type="V", code="INDEP-V", name="Village", parent=gvh, audit_user_id=1)
        micro = MicroCatchment.objects.create(code="INDEP-M", name="Micro", district=district, audit_user_id=1)
        MicroCatchmentGVH.objects.create(micro_catchment=micro, location=gvh, audit_user_id=1)
        cluster = Cluster.objects.create(code="INDEP-C", name="Cluster", traditional_authority=ta, audit_user_id=1)
        zone = update_or_create_zone(dict(name="Zone", cluster_uuid=cluster.uuid, village_uuids=[village.uuid]), user)
        hotspot = update_or_create_hotspot(dict(name="Hotspot", micro_catchment_uuid=micro.uuid, village_uuids=[village.uuid]), user)
        self.assertEqual(zone.cluster_id, cluster.id)
        self.assertEqual(hotspot.micro_catchment_id, micro.id)
        self.assertFalse(Zone.objects.filter(uuid=hotspot.uuid).exists())
        self.assertFalse(Hotspot.objects.filter(uuid=zone.uuid).exists())
        hotspot.delete()
        zone.refresh_from_db()
        self.assertEqual(zone.cluster_id, cluster.id)
        self.assertTrue(zone.villages.filter(pk=village.pk).exists())

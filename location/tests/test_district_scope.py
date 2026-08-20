from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings

from core.test_helpers import create_manager_role, create_test_interactive_user
from location.apps import LocationConfig
from location.gql_mutations import update_or_create_hotspot
from location.models import Hotspot, Location, MicroCatchment, UserDistrict
from location.services import MicroCatchmentService


@override_settings(ROW_SECURITY=True)
class DistrictScopeTest(TestCase):
    def setUp(self):
        self.previous_no_location_check = LocationConfig.no_location_check
        LocationConfig.no_location_check = False
        self.user = create_test_interactive_user(
            username="district-scope-user",
            password="Q7!vN2@pL9#x",
            roles=[create_manager_role().id],
        )

        self.allowed_district, self.allowed_ta, self.allowed_gvh, self.allowed_village = self._hierarchy("A")
        self.other_district, self.other_ta, self.other_gvh, self.other_village = self._hierarchy("B")
        UserDistrict.objects.create(
            user=self.user.i_user,
            location=self.allowed_ta,
            audit_user_id=-1,
        )
        self.allowed_catchment = self._catchment("A", self.allowed_district)
        self.other_catchment = self._catchment("B", self.other_district)
        self.allowed_hotspot = self._hotspot("A", self.allowed_catchment)
        self.other_hotspot = self._hotspot("B", self.other_catchment)

    def tearDown(self):
        LocationConfig.no_location_check = self.previous_no_location_check

    def _location(self, location_type, code, parent=None):
        return Location.objects.create(
            type=location_type,
            code=f"SCOPE-{code}",
            name=f"Scope {code}",
            parent=parent,
            audit_user_id=-1,
        )

    def _hierarchy(self, suffix):
        district = self._location("R", f"R{suffix}")
        ta = self._location("D", f"D{suffix}", district)
        gvh = self._location("W", f"W{suffix}", ta)
        village = self._location("V", f"V{suffix}", gvh)
        return district, ta, gvh, village

    def _catchment(self, suffix, district):
        return MicroCatchment.objects.create(
            code=f"MC-SCOPE-{suffix}",
            name=f"Catchment {suffix}",
            district=district,
            audit_user_id=-1,
        )

    def _hotspot(self, suffix, micro_catchment):
        return Hotspot.objects.create(
            code=f"HS-SCOPE-{suffix}",
            name=f"Hotspot {suffix}",
            micro_catchment=micro_catchment,
            audit_user_id=-1,
        )

    def test_micro_catchment_queryset_is_limited_to_assigned_district(self):
        result = MicroCatchment.get_queryset(None, self.user)

        self.assertTrue(result.filter(id=self.allowed_catchment.id).exists())
        self.assertFalse(result.filter(id=self.other_catchment.id).exists())

    def test_location_queryset_follows_the_assigned_hierarchy(self):
        result = Location.get_queryset(None, self.user)

        for location in (
            self.allowed_district,
            self.allowed_ta,
            self.allowed_gvh,
            self.allowed_village,
        ):
            self.assertTrue(result.filter(id=location.id).exists())
        self.assertFalse(result.filter(id=self.other_district.id).exists())
        self.assertFalse(result.filter(id=self.other_village.id).exists())

    def test_hotspot_queryset_is_limited_to_assigned_district(self):
        result = Hotspot.get_queryset(None, self.user)

        self.assertTrue(result.filter(id=self.allowed_hotspot.id).exists())
        self.assertFalse(result.filter(id=self.other_hotspot.id).exists())

    def test_micro_catchment_creation_rejects_another_district(self):
        with self.assertRaises(PermissionDenied):
            MicroCatchmentService(self.user).update_or_create(
                {
                    "name": "Unauthorized catchment",
                    "district_id": self.other_district.id,
                    "ta_ids": [self.other_ta.id],
                    "gvh_ids": [self.other_gvh.id],
                    "audit_user_id": -1,
                }
            )

    def test_hotspot_creation_rejects_another_district(self):
        with self.assertRaises(ValidationError):
            update_or_create_hotspot(
                {
                    "name": "Unauthorized hotspot",
                    "micro_catchment_uuid": self.other_catchment.uuid,
                    "village_uuids": [self.other_village.uuid],
                    "audit_user_id": -1,
                },
                self.user,
            )

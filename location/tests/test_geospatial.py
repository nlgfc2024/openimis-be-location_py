from types import SimpleNamespace
from unittest.mock import Mock, patch

import graphene
from django.test import TestCase

from location.geospatial import GeospatialQuery
from location.models import Location, MsrLocationReference
from location.msr_reference import MsrReferenceWriter


class GeospatialQueryTests(TestCase):
    def setUp(self):
        self.user = Mock(is_anonymous=False)
        self.user.has_perms.return_value = True
        self.context = SimpleNamespace(user=self.user)
        self.schema = graphene.Schema(query=GeospatialQuery)
        self.loc = Location.objects.bulk_create([Location(code="213", name="Dedza", type="R", audit_user_id=1)])[0]
        for source in ("allowed-msr", "other-msr"):
            MsrReferenceWriter(source).push([{"type": "districts", "id": 13, "district_id": 13,
                "code": "213" if source == "allowed-msr" else "999", "name": "District",
                "parents": [], "revision": 1}])
        self.reference = MsrLocationReference.objects.get(source_instance="allowed-msr")

    def query(self, query):
        return self.schema.execute(query, context_value=self.context)

    def test_unauthorized_list_and_count_denied(self):
        self.user.has_perms.return_value = False
        result = self.query("{msrGeoReferences{totalCount items{id}}}")
        self.assertTrue(result.errors)
        self.assertIsNone(result.data["msrGeoReferences"])

    def test_anonymous_denied_even_when_permission_mock_returns_true(self):
        self.user.is_anonymous = True
        self.assertTrue(self.query("{msrGeoReferences{totalCount}}").errors)

    def test_district_scope_is_source_specific(self):
        with patch("location.geospatial.allowed_micro_catchment_district_ids", return_value={self.loc.pk}):
            result = self.query("{msrGeoReferences{totalCount items{sourceInstance msrId code matched}}}")
        self.assertFalse(result.errors)
        self.assertEqual(result.data["msrGeoReferences"]["totalCount"], 1)
        self.assertEqual(result.data["msrGeoReferences"]["items"][0]["sourceInstance"], "allowed-msr")

    def test_no_assignments_exposes_no_rows_or_counts(self):
        with patch("location.geospatial.allowed_micro_catchment_district_ids", return_value=set()):
            result = self.query("{msrGeoReferences{totalCount items{id}}}")
        self.assertEqual(result.data["msrGeoReferences"], {"totalCount": 0, "items": []})

    def test_filters_and_page_limits(self):
        with patch("location.geospatial.allowed_micro_catchment_district_ids", return_value=None):
            result = self.query('{msrGeoReferences(sourceInstance:"allowed-msr",districtMsrId:"13",limit:1){totalCount items{msrId code revision}}}')
            invalid = self.query("{msrGeoReferences(limit:201){totalCount}}")
        self.assertEqual(result.data["msrGeoReferences"]["items"], [{"msrId": "13", "code": "213", "revision": "1"}])
        self.assertTrue(invalid.errors)

    @patch("msr_etl.geometry_access.load_geometry")
    def test_direct_id_cannot_bypass_scope(self, load):
        other = MsrLocationReference.objects.get(source_instance="other-msr")
        with patch("location.geospatial.allowed_micro_catchment_district_ids", return_value={self.loc.pk}):
            result = self.query('{msrGeoGeometry(referenceId:"%s"){status}}' % other.pk)
        self.assertTrue(result.errors)
        load.assert_not_called()

    @patch("msr_etl.geometry_access.load_geometry", return_value={"status": "unavailable", "revision": "2"})
    def test_authorized_refresh_returns_current_removal_status(self, load):
        with patch("location.geospatial.allowed_micro_catchment_district_ids", return_value={self.loc.pk}):
            result = self.query('{msrGeoGeometry(referenceId:"%s"){status revision geojson}}' % self.reference.pk)
        self.assertFalse(result.errors)
        self.assertEqual(result.data["msrGeoGeometry"], {"status": "unavailable", "revision": "2", "geojson": None})

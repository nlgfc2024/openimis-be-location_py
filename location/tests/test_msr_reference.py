from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from location.models import Location, MicroCatchment, MsrLocationReference
from location.msr_reference import MsrReferenceWriter


def district(**changes):
    return {"id": 13, "type": "districts", "code": "213", "name": "Dedza",
            "district_id": 13, "parents": [], "revision": 1, **changes}


def ta(**changes):
    return {"id": 24, "type": "traditional_authorities", "code": "TA24", "name": "TA",
            "district_id": 13, "parents": [{"type": "districts", "id": 13}], "revision": 1, **changes}


def catchment(**changes):
    return {"id": 667, "type": "catchments", "code": "MC667", "name": "Pilot",
            "district_id": 13, "parents": [{"type": "traditional_authorities", "id": 24},
                                             {"type": "districts", "id": 13}],
            "is_micro": True, "revision": 1, **changes}


class MsrReferenceTests(TestCase):
    def setUp(self):
        self.writer = MsrReferenceWriter("msr-malawi")

    def test_idempotent_and_separate_source_identity(self):
        first = self.writer.push([district()])[0]
        second = self.writer.push([district(name="Updated")])[0]
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(second.name, "Updated")
        self.assertEqual(second.msr_id, 13)
        self.assertEqual(second.code, "213")
        other = MsrReferenceWriter("another-msr").push([district()])[0]
        self.assertNotEqual(first.pk, other.pk)

    def test_parent_first_and_micro_catchment_match(self):
        loc = Location.objects.bulk_create([Location(code="213", name="Dedza", type="R", audit_user_id=1)])[0]
        micro = MicroCatchment.objects.bulk_create([
            MicroCatchment(code="MC667", name="Pilot", district=loc, audit_user_id=1),
        ])[0]
        self.writer.push([catchment(), ta(), district()])
        ref = MsrLocationReference.objects.get(msr_type="catchments")
        self.assertEqual(ref.micro_catchment_id, micro.pk)
        self.assertIsNone(ref.location_id)
        self.assertEqual(MsrLocationReference.objects.get(msr_type="districts").location_id, loc.pk)

    def test_missing_parent_rolls_back_entire_batch(self):
        with self.assertRaises(ValidationError):
            self.writer.push([district(), catchment()])
        self.assertFalse(MsrLocationReference.objects.exists())

    def test_stale_revision_cannot_restore_removed_geometry(self):
        self.writer.push([district(revision=3, boundary_status="unavailable", geometry_sha256=None)])
        self.writer.push([district(revision=2, boundary_status="available", geometry_sha256="a" * 64)])
        ref = MsrLocationReference.objects.get()
        self.assertEqual(ref.revision, 3)
        self.assertIsNone(ref.geometry_sha256)
        self.assertEqual(ref.boundary_status, "unavailable")

    def test_omitted_fields_preserved_explicit_null_removed(self):
        self.writer.push([district(geometry_sha256="a" * 64, geometry_relation="boundary")])
        self.writer.push([district(revision=2, boundary_status="delivery_unavailable")])
        self.assertEqual(MsrLocationReference.objects.get().geometry_sha256, "a" * 64)
        self.writer.push([district(revision=3, geometry_sha256=None, geometry_relation=None)])
        self.assertIsNone(MsrLocationReference.objects.get().geometry_sha256)

    def test_signed_url_is_not_persisted(self):
        ref = self.writer.push([district(geojson_url="http://msr/secret?signature=temporary")])[0]
        self.assertFalse(hasattr(ref, "geojson_url"))

    def test_ward_does_not_match_gvh(self):
        constituency = {**ta(), "type": "constituencies", "id": 99}
        ward = {"id": 44, "type": "wards", "code": "WARD44", "name": "Ward", "revision": 1,
                "district_id": 13, "parents": [{"type": "constituencies", "id": 99}, {"type": "districts", "id": 13}]}
        Location.objects.bulk_create([Location(code="WARD44", name="GVH", type="W", audit_user_id=1)])
        self.writer.push([ward, district(), constituency])
        self.assertIsNone(MsrLocationReference.objects.get(msr_type="wards").location_id)

    def test_ambiguous_matching_rejected(self):
        Location.objects.bulk_create([
            Location(code="213", name="One", type="R", audit_user_id=1),
            Location(code="213", name="Two", type="R", audit_user_id=1),
        ])
        with self.assertRaisesRegex(ValidationError, "Ambiguous"):
            self.writer.push([district()])
        self.assertFalse(MsrLocationReference.objects.exists())

    def test_regular_catchment_does_not_match_micro(self):
        self.writer.push([district(), ta(), catchment(is_micro=False)])
        self.assertIsNone(MsrLocationReference.objects.get(msr_type="catchments").micro_catchment_id)

    def test_invalid_hierarchy_and_coordinates_rejected(self):
        for row in (district(id="213"), district(latitude=100), district(latitude=float("nan")),
                    district(latitude=-14), district(district_id=99), ta(parents=[]),
                    district(revision=-1), district(is_micro="false")):
            with self.subTest(row=row), self.assertRaises(ValidationError):
                self.writer.push([row])
        self.assertFalse(MsrLocationReference.objects.exists())

    def test_database_rejects_duplicate_identity(self):
        self.writer.push([district()])
        with self.assertRaises(IntegrityError), transaction.atomic():
            MsrLocationReference.objects.create(source_instance="msr-malawi", msr_type="districts",
                                                msr_id=13, code="different", name="Duplicate")

    def test_partial_update_cannot_change_district_without_parent_chain(self):
        self.writer.push([district(), ta()])
        row = ta(district_id=99, revision=2)
        del row["parents"]
        with self.assertRaises(ValidationError):
            self.writer.push([row])
        self.assertEqual(MsrLocationReference.objects.get(msr_type="traditional_authorities").district_msr_id, 13)

    def test_extra_parent_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.writer.push([district(parents=[{"id": 1, "type": None}])])

    def test_timestamp_and_coordinate_removal(self):
        self.writer.push([district(latitude=-14, longitude=34, geojson_updated_at="2026-11-12T10:00:00Z")])
        ref = self.writer.push([district(latitude=None, longitude=None, revision=2)])[0]
        self.assertIsNone(ref.latitude)
        self.assertIsNone(ref.longitude)
        self.assertEqual(ref.geojson_updated_at.year, 2026)

    def test_database_rejects_two_coremis_targets(self):
        loc = Location.objects.bulk_create([Location(code="213", name="Dedza", type="R", audit_user_id=1)])[0]
        micro = MicroCatchment.objects.bulk_create([
            MicroCatchment(code="MC667", name="Pilot", district=loc, audit_user_id=1),
        ])[0]
        with self.assertRaises(IntegrityError), transaction.atomic():
            MsrLocationReference.objects.create(source_instance="msr-malawi", msr_type="districts",
                                                msr_id=13, code="213", name="Dedza",
                                                location=loc, micro_catchment=micro)

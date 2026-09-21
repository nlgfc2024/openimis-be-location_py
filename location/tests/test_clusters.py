from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings

from location.clusters import delete_cluster, save_cluster
from location.apps import LocationConfig
from location.models import Cluster, Location


class ClusterModelTest(TestCase):
    def setUp(self):
        self.district = Location.objects.create(
            code="101", name="District", type="R", audit_user_id=1
        )
        self.ta = Location.objects.create(
            code="10101", name="TA", type="D", parent=self.district,
            audit_user_id=1,
        )

    def create_cluster(self, code, authority):
        return Cluster.objects.create(
            code=code, name=code, traditional_authority=authority,
            audit_user_id=1,
        )

    def test_authority_can_have_multiple_clusters(self):
        first = self.create_cluster("CL01", self.ta)
        second = self.create_cluster("CL02", self.ta)
        self.assertEqual(first.traditional_authority_id, self.ta.pk)
        self.assertEqual(second.traditional_authority_id, self.ta.pk)
        self.assertEqual(self.ta.clusters.count(), 2)

    def test_authority_is_required(self):
        with self.assertRaises(ValidationError):
            self.create_cluster("CL01", None)

    def test_other_location_types_are_rejected(self):
        for location_type in ("R", "W", "V"):
            with self.subTest(location_type=location_type):
                location = Location.objects.create(
                    code="CL" + location_type, name="Other location",
                    type=location_type, audit_user_id=1,
                )
                with self.assertRaises(ValidationError):
                    self.create_cluster("CL01", location)

    def test_update_cannot_assign_a_district(self):
        cluster = self.create_cluster("CL01", self.ta)
        cluster.traditional_authority = self.district
        with self.assertRaises(ValidationError):
            cluster.save()
        cluster.refresh_from_db()
        self.assertEqual(cluster.traditional_authority_id, self.ta.pk)


@override_settings(ROW_SECURITY=False)
class ClusterSelectionTest(ClusterModelTest):
    def setUp(self):
        super().setUp()
        self.user = SimpleNamespace(
            is_anonymous=False, is_authenticated=True,
            has_perms=lambda permissions: True, id_for_audit=1,
        )

    def payload(self):
        return {
            "code": "CL01", "name": "Cluster One",
            "traditional_authority_uuid": self.ta.uuid,
            "district_uuid": self.district.uuid,
        }

    def test_cluster_permissions_are_registered(self):
        from core.utils import collect_all_gql_permissions
        permissions = collect_all_gql_permissions()["location"]
        self.assertEqual(permissions["gql_query_clusters_perms"], ["121921"])
        self.assertEqual(permissions["gql_mutation_create_clusters_perms"], ["121922"])
        self.assertEqual(permissions["gql_mutation_edit_clusters_perms"], ["121923"])
        self.assertEqual(permissions["gql_mutation_delete_clusters_perms"], ["121924"])

    def test_location_permissions_do_not_grant_cluster_access(self):
        import graphene
        from location.schema import Query
        self.user.has_perms = lambda permissions: set(permissions).issubset({"121901", "121902", "121903", "121904"})
        with self.assertRaises(PermissionDenied):
            save_cluster(self.user, **self.payload())
        result = graphene.Schema(query=Query).execute(
            "{ clusters(first: 1) { edges { node { uuid } } } }",
            context_value=SimpleNamespace(user=self.user, dataloaders={}, headers={}),
        )
        self.assertTrue(result.errors)

    def test_cluster_actions_require_their_own_permissions(self):
        rights = set(LocationConfig.gql_mutation_create_clusters_perms)
        self.user.has_perms = lambda permissions: set(permissions).issubset(rights)
        cluster = save_cluster(self.user, **self.payload())
        with self.assertRaises(PermissionDenied):
            save_cluster(self.user, uuid=str(cluster.uuid), **self.payload())
        with self.assertRaises(PermissionDenied):
            delete_cluster(self.user, str(cluster.uuid))
        rights.update(LocationConfig.gql_mutation_edit_clusters_perms)
        save_cluster(self.user, uuid=str(cluster.uuid), **{**self.payload(), "name": "Edited"})
        rights.update(LocationConfig.gql_mutation_delete_clusters_perms)
        delete_cluster(self.user, str(cluster.uuid))

    def test_save_uses_authority_without_storing_district(self):
        cluster = save_cluster(self.user, **{key: value for key, value in self.payload().items() if key != "code"})
        self.assertEqual(cluster.traditional_authority.parent_id, self.district.pk)
        self.assertEqual(cluster.code, "1010101")
        self.assertNotIn("district", {field.name for field in Cluster._meta.fields})

    def test_cluster_code_increments_from_traditional_authority(self):
        payload = {key: value for key, value in self.payload().items() if key != "code"}
        first = save_cluster(self.user, **payload)
        second = save_cluster(self.user, **{**payload, "name": "Cluster Two"})
        self.assertEqual(first.code, "1010101")
        self.assertEqual(second.code, "1010102")

    def test_cluster_code_does_not_reuse_history(self):
        payload = {key: value for key, value in self.payload().items() if key != "code"}
        first = save_cluster(self.user, **payload)
        delete_cluster(self.user, str(first.uuid))
        second = save_cluster(self.user, **{**payload, "name": "Cluster Two"})
        self.assertEqual(second.code, "1010102")

    def test_cross_district_selection_is_rejected(self):
        other = Location.objects.create(code="102", name="Other", type="R", audit_user_id=1)
        with self.assertRaises(ValidationError):
            save_cluster(self.user, **{**self.payload(), "district_uuid": other.uuid})
        self.assertFalse(Cluster.objects.exists())

    def test_inactive_authority_is_rejected(self):
        from core.utils import TimeUtils
        self.ta.validity_to = TimeUtils.now()
        self.ta.save()
        with self.assertRaises(ValidationError):
            save_cluster(self.user, **self.payload())

    def test_missing_permission_is_rejected(self):
        self.user.has_perms = lambda permissions: False
        with self.assertRaises(PermissionDenied):
            save_cluster(self.user, **self.payload())

    def test_authority_outside_user_district_is_rejected(self):
        with patch("location.clusters.allowed_micro_catchment_district_ids", return_value=set()):
            with self.assertRaises(ValidationError):
                save_cluster(self.user, **self.payload())

    def test_update_preserves_history(self):
        cluster = save_cluster(self.user, **self.payload())
        save_cluster(self.user, **{**self.payload(), "uuid": str(cluster.uuid), "name": "Updated"})
        cluster.refresh_from_db()
        self.assertEqual(cluster.name, "Updated")
        self.assertTrue(Cluster.objects.filter(legacy_id=cluster.pk, name="Cluster One").exists())

    def test_graphql_lists_cluster_with_derived_district(self):
        import graphene
        from location.schema import Query, Mutation
        cluster = save_cluster(self.user, **self.payload())
        schema = graphene.Schema(query=Query, mutation=Mutation)
        result = schema.execute(
            """query { clusters(first: 20) { edges { node {
              uuid name traditionalAuthority { name parent { name } }
            } } } }""",
            context_value=SimpleNamespace(user=self.user, dataloaders={}, headers={}),
        )
        self.assertIsNone(result.errors)
        node = result.data["clusters"]["edges"][0]["node"]
        self.assertEqual(node["uuid"], str(cluster.uuid))
        self.assertEqual(node["traditionalAuthority"]["parent"]["name"], self.district.name)

    def test_graphql_mutation_accepts_ui_variables(self):
        import graphene
        from location.schema import Query, Mutation
        schema = graphene.Schema(query=Query, mutation=Mutation)
        result = schema.execute(
            """mutation ($code: String!, $name: String!, $districtUuid: String!,
                $traditionalAuthorityUuid: String!) {
              saveCluster(code: $code, name: $name, districtUuid: $districtUuid,
                traditionalAuthorityUuid: $traditionalAuthorityUuid) {
                cluster { name traditionalAuthority { uuid } }
              }
            }""",
            variable_values={
                "code": "CL02", "name": 'Cluster "Two"',
                "districtUuid": str(self.district.uuid),
                "traditionalAuthorityUuid": str(self.ta.uuid),
            },
            context_value=SimpleNamespace(user=self.user, dataloaders={}, headers={}),
        )
        self.assertIsNone(result.errors)
        self.assertEqual(result.data["saveCluster"]["cluster"]["name"], 'Cluster "Two"')

    def test_delete_preserves_history_and_authority(self):
        cluster = save_cluster(self.user, **self.payload())
        self.user.id_for_audit = 2
        self.assertEqual(delete_cluster(self.user, str(cluster.uuid)), str(cluster.uuid))
        cluster.refresh_from_db()
        self.assertIsNotNone(cluster.validity_to)
        self.assertEqual(cluster.audit_user_id, 2)
        self.assertTrue(Cluster.objects.filter(legacy_id=cluster.pk, audit_user_id=1).exists())
        self.assertTrue(Location.objects.filter(pk=self.ta.pk).exists())

    def test_delete_requires_permission(self):
        cluster = save_cluster(self.user, **self.payload())
        self.user.has_perms = lambda permissions: False
        with self.assertRaises(PermissionDenied):
            delete_cluster(self.user, str(cluster.uuid))
        cluster.refresh_from_db()
        self.assertIsNone(cluster.validity_to)

    def test_delete_respects_district_scope(self):
        cluster = save_cluster(self.user, **self.payload())
        with patch("location.models.allowed_micro_catchment_district_ids", return_value=set()):
            with self.assertRaises(ValidationError):
                delete_cluster(self.user, str(cluster.uuid))
        cluster.refresh_from_db()
        self.assertIsNone(cluster.validity_to)

    def test_cannot_delete_twice_or_update_deleted_cluster(self):
        cluster = save_cluster(self.user, **self.payload())
        delete_cluster(self.user, str(cluster.uuid))
        with self.assertRaises(ValidationError):
            delete_cluster(self.user, str(cluster.uuid))
        with self.assertRaises(ValidationError):
            save_cluster(self.user, uuid=str(cluster.uuid), **self.payload())

    def test_graphql_detail_and_delete(self):
        import graphene
        from location.schema import Query, Mutation
        cluster = save_cluster(self.user, **self.payload())
        schema = graphene.Schema(query=Query, mutation=Mutation)
        context = SimpleNamespace(user=self.user, dataloaders={}, headers={})
        query = """query ($uuid: String!) {
          clusters(uuid: $uuid, first: 1) { edges { node { uuid code name } } }
        }"""
        variables = {"uuid": str(cluster.uuid)}
        before = schema.execute(query, variable_values=variables, context_value=context)
        self.assertIsNone(before.errors)
        self.assertEqual(len(before.data["clusters"]["edges"]), 1)
        deleted = schema.execute(
            "mutation ($uuid: String!) { deleteCluster(uuid: $uuid) { uuid } }",
            variable_values=variables, context_value=context,
        )
        self.assertIsNone(deleted.errors)
        self.assertEqual(deleted.data["deleteCluster"]["uuid"], str(cluster.uuid))
        after = schema.execute(query, variable_values=variables, context_value=context)
        self.assertIsNone(after.errors)
        self.assertEqual(after.data["clusters"]["edges"], [])

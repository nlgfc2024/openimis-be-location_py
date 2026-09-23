from types import SimpleNamespace

import graphene
from django.test import SimpleTestCase

from core.utils import collect_all_gql_permissions
from location.apps import LocationConfig
from location.gql_mutations import CreateZoneMutation, UpdateZoneMutation, DeleteZoneMutation
from location.schema import Query


class ZonePermissionsTest(SimpleTestCase):
    def test_zone_rights_are_registered_separately(self):
        permissions = collect_all_gql_permissions()["location"]
        self.assertEqual(permissions["gql_query_zones_perms"], ["121931"])
        self.assertEqual(permissions["gql_mutation_create_zones_perms"], ["121932"])
        self.assertNotEqual(LocationConfig.gql_query_zones_perms, LocationConfig.gql_query_clusters_perms)

    def test_cluster_rights_do_not_authorize_zone_queries_or_mutations(self):
        user = SimpleNamespace(id=1, is_anonymous=False, id_for_audit=1,
                               has_perms=lambda perms: set(perms).issubset({"121921", "121922", "121923", "121924"}))
        response = graphene.Schema(query=Query).execute(
            "{ zones(first: 1) { edges { node { uuid } } } }",
            context_value=SimpleNamespace(user=user, headers={}, dataloaders={}),
        )
        self.assertTrue(response.errors)
        for mutation in (CreateZoneMutation, UpdateZoneMutation, DeleteZoneMutation):
            self.assertIsNotNone(mutation.async_mutate(user, uuid="denied", code="denied", name="Denied"))

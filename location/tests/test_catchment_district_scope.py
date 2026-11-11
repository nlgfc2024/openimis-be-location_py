from types import SimpleNamespace
from unittest.mock import patch

import graphene
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings
from graphql_relay import to_global_id

from core.test_helpers import create_test_interactive_user, create_test_role
from core.utils import TimeUtils
from location.apps import LocationConfig
from location.gql_mutations import (
    CreateCatchmentMutation, UpdateCatchmentMutation, DeleteCatchmentMutation,
)
from location.models import Catchment, CatchmentDistrict, Location, UserDistrict
from location.schema import Query as LocationQuery
from location.services import CatchmentService


class Query(LocationQuery, graphene.ObjectType):
    node = graphene.relay.Node.Field()


@override_settings(ROW_SECURITY=True, MODE="dev")
class CatchmentDistrictScopeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        role = create_test_role(
            perm_names=[
                "gql_query_catchments_perms",
                "gql_mutation_create_catchments_perms",
                "gql_mutation_edit_catchments_perms",
                "gql_mutation_delete_catchments_perms",
            ],
            name="Catchment district scope",
        )
        cls.user = create_test_interactive_user(
            username="catchment-scope", roles=[role.id],
        )
        cls.a = Location.objects.create(code="SCOPE-A", name="A", type="R", audit_user_id=-1)
        cls.b = Location.objects.create(code="SCOPE-B", name="B", type="R", audit_user_id=-1)
        cls.ta = Location.objects.create(code="SCOPE-TA", name="TA", type="D", parent=cls.a, audit_user_id=-1)
        cls.assignment = UserDistrict.objects.create(user=cls.user.i_user, location=cls.a, audit_user_id=-1)
        cls.only_a = cls.catchment("SCOPE-CA", cls.a)
        cls.only_b = cls.catchment("SCOPE-CB", cls.b)
        cls.shared = cls.catchment("SCOPE-SHARED", cls.a, cls.b)

    @classmethod
    def catchment(cls, code, *districts):
        obj = Catchment.objects.create(code=code, name=code, audit_user_id=-1)
        for district in districts:
            CatchmentDistrict.objects.create(catchment=obj, location=district, audit_user_id=-1)
        return obj

    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(LocationConfig, "no_location_check", False).start()
        self.service = CatchmentService(self.user)

    def request(self, user=None):
        request = RequestFactory().get("/graphql")
        request.user = user or self.user
        return request

    def query(self, selection, user=None):
        result = graphene.Schema(query=Query).execute(selection, context_value=self.request(user))
        self.assertIsNone(result.errors, result.errors)
        return result.data

    def payload(self, obj=None, district_ids=None):
        data = {
            "code": obj.code if obj else "SCOPE-NEW",
            "name": "Updated catchment",
            "district_ids": district_ids if district_ids is not None else [self.a.id],
            "audit_user_id": self.user.id_for_audit,
            "validity_from": TimeUtils.now(),
        }
        if obj:
            data["uuid"] = obj.uuid
        return data

    def test_unfiltered_list_and_nested_district_links_are_scoped(self):
        data = self.query("""{ catchments {
            totalCount edges { node { code districts { code } districtLinks { location { code } } } }
        } }""")
        self.assertEqual(data["catchments"]["totalCount"], 2)
        rows = {e["node"]["code"]: e["node"] for e in data["catchments"]["edges"]}
        self.assertEqual(set(rows), {self.only_a.code, self.shared.code})
        self.assertEqual(rows[self.shared.code]["districts"], [{"code": self.a.code}])
        self.assertEqual(rows[self.shared.code]["districtLinks"], [{"location": {"code": self.a.code}}])

    def test_search_and_explicit_other_district_cannot_broaden_access(self):
        for args in [f'search: "{self.only_b.code}"', f'districtUuid: "{self.b.uuid}"', f'uuid: "{self.only_b.uuid}"']:
            with self.subTest(args=args):
                data = self.query(f'{{ catchments({args}) {{ edges {{ node {{ code }} }} }} }}')
                self.assertEqual(data["catchments"]["edges"], [])

    def test_relay_node_rejects_other_district(self):
        node_id = to_global_id("CatchmentGQLType", self.only_b.pk)
        self.assertIsNone(self.query(f'{{ node(id: "{node_id}") {{ id }} }}')["node"])

    def test_relay_node_requires_catchment_search_permission(self):
        node_id = to_global_id("CatchmentGQLType", self.only_a.pk)
        with patch.object(type(self.user), "has_perms", return_value=False):
            result = graphene.Schema(query=Query).execute(
                f'{{ node(id: "{node_id}") {{ id }} }}',
                context_value=self.request(),
            )
        self.assertTrue(result.errors)
        self.assertIsNone(result.data["node"])

    def test_multiple_assignments_do_not_duplicate_shared_catchments(self):
        UserDistrict.objects.create(user=self.user.i_user, location=self.b, audit_user_id=-1)
        result = Catchment.get_queryset(None, self.user)
        self.assertCountEqual(list(result), [self.only_a, self.only_b, self.shared])

    def test_ta_assignment_uses_parent_district(self):
        self.assignment.location = self.ta
        self.assignment.save()
        self.assertCountEqual(Catchment.get_queryset(None, self.user), [self.only_a, self.shared])

    def test_missing_or_expired_assignment_grants_no_records(self):
        self.assignment.validity_to = TimeUtils.now()
        self.assignment.save()
        self.assertFalse(Catchment.get_queryset(None, self.user).exists())
        self.assignment.delete()
        self.assertFalse(Catchment.get_queryset(None, self.user).exists())

    def test_inactive_assigned_district_grants_no_records(self):
        self.a.validity_to = TimeUtils.now()
        self.a.save()
        self.assertFalse(Catchment.get_queryset(None, self.user).exists())

    def test_expired_catchment_links_grant_no_access(self):
        self.only_a.district_links.update(validity_to=TimeUtils.now())
        self.assertFalse(Catchment.get_queryset(None, self.user).filter(pk=self.only_a.pk).exists())

    def test_anonymous_user_has_no_records(self):
        self.assertFalse(Catchment.get_queryset(None, AnonymousUser()).exists())

    def test_existing_unrestricted_modes_remain_unrestricted(self):
        for row_security, no_location_check in [(False, False), (True, True)]:
            with self.subTest(row_security=row_security), override_settings(ROW_SECURITY=row_security):
                with patch.object(LocationConfig, "no_location_check", no_location_check):
                    self.assertEqual(Catchment.get_queryset(None, self.user).count(), 3)
        admin = SimpleNamespace(is_superuser=True, is_anonymous=False)
        self.assertEqual(Catchment.get_queryset(None, admin).count(), 3)

    def test_create_rejects_unassigned_district(self):
        with self.assertRaises(PermissionDenied):
            self.service.update_or_create(self.payload(district_ids=[self.a.id, self.b.id]))
        self.assertFalse(Catchment.objects.filter(code="SCOPE-NEW").exists())

    def test_create_and_update_work_inside_assigned_district(self):
        created = self.service.update_or_create(self.payload())
        self.assertEqual(created.district_links.get(validity_to__isnull=True).location_id, self.a.id)
        updated = self.service.update_or_create(self.payload(self.only_a))
        self.assertEqual(updated.name, "Updated catchment")

    def test_update_cannot_move_inaccessible_record_into_scope(self):
        with self.assertRaises(Catchment.DoesNotExist):
            self.service.update_or_create(self.payload(self.only_b))
        self.only_b.refresh_from_db()
        self.assertEqual(self.only_b.name, self.only_b.code)

    def test_update_cannot_move_owned_record_outside_scope(self):
        with self.assertRaises(PermissionDenied):
            self.service.update_or_create(self.payload(self.only_a, [self.b.id]))

    def test_restricted_user_cannot_edit_or_delete_shared_catchment(self):
        with self.assertRaises(PermissionDenied):
            self.service.update_or_create(self.payload(self.shared))
        with self.assertRaises(PermissionDenied):
            self.service.delete(self.shared.uuid)
        self.shared.refresh_from_db()
        self.assertIsNone(self.shared.validity_to)
        self.assertEqual(self.shared.district_links.filter(validity_to__isnull=True).count(), 2)

    def test_delete_rejects_other_district_and_allows_own(self):
        with self.assertRaises(Catchment.DoesNotExist):
            self.service.delete(self.only_b.uuid)
        self.service.delete(self.only_a.uuid)
        self.only_a.refresh_from_db()
        self.assertIsNotNone(self.only_a.validity_to)

    def test_user_assigned_every_district_can_edit_and_delete_shared(self):
        UserDistrict.objects.create(user=self.user.i_user, location=self.b, audit_user_id=-1)
        self.service.update_or_create(self.payload(self.shared, [self.a.id, self.b.id]))
        self.service.delete(self.shared.uuid)
        self.shared.refresh_from_db()
        self.assertIsNotNone(self.shared.validity_to)

    def test_mutation_entrypoints_reject_other_district(self):
        create_data = self.payload(district_ids=[self.b.id])
        update_data = self.payload(self.only_b)
        for mutation, data in [
            (CreateCatchmentMutation, create_data),
            (UpdateCatchmentMutation, update_data),
            (DeleteCatchmentMutation, {"uuid": self.only_b.uuid, "code": self.only_b.code}),
        ]:
            with self.subTest(mutation=mutation.__name__):
                result = mutation.async_mutate(self.user, **data)
                self.assertTrue(result)
                self.assertIn("detail", result[0])
        self.only_b.refresh_from_db()
        self.assertIsNone(self.only_b.validity_to)

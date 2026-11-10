import json
import uuid

from core.models.openimis_graphql_test_case import (
    BaseTestContext,
    openIMISGraphQLTestCase,
)
from core.test_helpers import create_test_interactive_user
from location.models import Location, MicroCatchment
from location.test_helpers import create_test_village
from project_social_protection.models import Activity, Project
from social_protection.models import BenefitPlan


class MicroCatchmentBenefitPlanFilterTest(openIMISGraphQLTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = create_test_interactive_user(
            username=f"mc-phase-user-{uuid.uuid4().hex[:8]}"
        )
        cls.token = BaseTestContext(user=cls.user).get_jwt()
        username = cls.user.username

        cls.plan_a = cls._benefit_plan("A")
        cls.plan_b = cls._benefit_plan("B")
        cls.plan_without_projects = cls._benefit_plan("EMPTY")
        cls.activity = Activity(name=f"MC Phase Activity {uuid.uuid4().hex[:8]}")
        cls.activity.save(username=username)
        cls.project_location = create_test_village(
            {"code": f"MCPF{uuid.uuid4().hex[:6]}"}
        )

        cls.district_a = cls._district("A")
        cls.district_b = cls._district("B")
        cls.alpha = cls._micro_catchment("ALPHA", "Alpha Catchment", cls.district_a)
        cls.beta = cls._micro_catchment("BETA", "Beta Catchment", cls.district_a)
        cls.other_district = cls._micro_catchment(
            "OTHER", "Other District Catchment", cls.district_b
        )
        cls.deleted_only = cls._micro_catchment(
            "DELETED", "Deleted Project Catchment", cls.district_a
        )

        cls._project("Alpha Project 1", cls.plan_a, cls.alpha)
        cls._project("Alpha Project 2", cls.plan_a, cls.alpha)
        cls._project("Other District Project", cls.plan_a, cls.other_district)
        cls._project("Beta Project", cls.plan_b, cls.beta)
        cls._project(
            "Deleted Project", cls.plan_a, cls.deleted_only, is_deleted=True
        )

    @classmethod
    def _benefit_plan(cls, suffix):
        benefit_plan = BenefitPlan(
            code=f"MC{uuid.uuid4().hex[:7]}",
            name=f"MC Phase {suffix} {uuid.uuid4().hex[:8]}",
        )
        benefit_plan.save(username=cls.user.username)
        return benefit_plan

    @classmethod
    def _district(cls, suffix):
        return Location.objects.create(
            type="R",
            code=f"MC-PHASE-DISTRICT-{suffix}-{uuid.uuid4().hex[:6]}",
            name=f"MC Phase District {suffix}",
            audit_user_id=-1,
        )

    @classmethod
    def _micro_catchment(cls, code, name, district):
        return MicroCatchment.objects.create(
            code=f"MC-PHASE-{code}-{uuid.uuid4().hex[:6]}",
            name=name,
            district=district,
            audit_user_id=-1,
        )

    @classmethod
    def _project(cls, name, benefit_plan, micro_catchment, is_deleted=False):
        project = Project(
            name=f"{name} {uuid.uuid4().hex[:6]}",
            benefit_plan=benefit_plan,
            activity=cls.activity,
            location=cls.project_location,
            micro_catchment=micro_catchment,
            target_beneficiaries=10,
            working_days=5,
            is_deleted=is_deleted,
        )
        project.save(username=cls.user.username)
        return project

    def _query_codes(self, arguments="", authenticated=True):
        response = self.query(
            f"""
            query {{
              microCatchments({arguments}) {{
                edges {{
                  node {{ code }}
                }}
              }}
            }}
            """,
            headers=(
                {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}
                if authenticated
                else {}
            ),
        )
        content = json.loads(response.content)
        return response, content

    def test_filters_by_benefit_plan_without_duplicates(self):
        response, content = self._query_codes(
            f'benefitPlanId: "{self.plan_a.id}"'
        )

        self.assertResponseNoErrors(response)
        codes = [
            edge["node"]["code"]
            for edge in content["data"]["microCatchments"]["edges"]
        ]
        self.assertCountEqual(codes, [self.alpha.code, self.other_district.code])
        self.assertEqual(codes.count(self.alpha.code), 1)
        self.assertNotIn(self.deleted_only.code, codes)

    def test_combines_benefit_plan_and_district_filters(self):
        response, content = self._query_codes(
            f'benefitPlanId: "{self.plan_a.id}", '
            f'district_Uuid: "{self.district_a.uuid}"'
        )

        self.assertResponseNoErrors(response)
        codes = [
            edge["node"]["code"]
            for edge in content["data"]["microCatchments"]["edges"]
        ]
        self.assertEqual(codes, [self.alpha.code])

    def test_combines_benefit_plan_and_search_filters(self):
        response, content = self._query_codes(
            f'benefitPlanId: "{self.plan_a.id}", name_Icontains: "Alpha"'
        )

        self.assertResponseNoErrors(response)
        codes = [
            edge["node"]["code"]
            for edge in content["data"]["microCatchments"]["edges"]
        ]
        self.assertEqual(codes, [self.alpha.code])

    def test_returns_no_results_when_plan_has_no_projects(self):
        response, content = self._query_codes(
            f'benefitPlanId: "{self.plan_without_projects.id}"'
        )

        self.assertResponseNoErrors(response)
        self.assertEqual(content["data"]["microCatchments"]["edges"], [])

    def test_omitting_benefit_plan_preserves_existing_results(self):
        response, content = self._query_codes('name_Icontains: "Catchment"')

        self.assertResponseNoErrors(response)
        codes = [
            edge["node"]["code"]
            for edge in content["data"]["microCatchments"]["edges"]
        ]
        for micro_catchment in (
            self.alpha,
            self.beta,
            self.other_district,
            self.deleted_only,
        ):
            self.assertIn(micro_catchment.code, codes)

    def test_existing_authentication_requirement_is_preserved(self):
        response, content = self._query_codes(
            f'benefitPlanId: "{self.plan_a.id}"', authenticated=False
        )

        self.assertResponseHasErrors(response)
        self.assertIsNone(content["data"]["microCatchments"])

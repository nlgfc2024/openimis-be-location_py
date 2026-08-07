from core.gql.custom_lookup import NotEqual
import graphene
import base64
from graphene_django import DjangoObjectType
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _
from core import prefix_filterset, ExtendedConnection
from location.apps import LocationConfig
from location.models import (
    HealthFacilityLegalForm,
    Location,
    HealthFacilitySubLevel,
    HealthFacilityCatchment,
    HealthFacility,
    UserDistrict,
    OfficerVillage,
    MicroCatchment,
    MicroCatchmentTA,
    MicroCatchmentGVH,
    Hotspot,
    Catchment,
    CatchmentDistrict,
)
from django.db.models import Field


class LocationGQLType(DjangoObjectType):
    client_mutation_id = graphene.String()
    Field.register_lookup(NotEqual)

    def resolve_parent(self, info):
        if not info.context.user.is_authenticated:
            raise PermissionDenied(_("unauthorized"))
        if "location_loader" in info.context.dataloaders and self.parent_id:
            return info.context.dataloaders["location_loader"].load(self.parent_id)
        return self.parent

    class Meta:
        model = Location
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "uuid": ["exact", "in"],
            "code": ["exact", "istartswith", "icontains", "iexact", "ne"],
            "name": ["exact", "istartswith", "icontains", "iexact", "ne"],
            "type": ["exact"],
            "parent__uuid": ["exact", "in"],  # can't import itself!
            "parent__parent__uuid": ["exact", "in"],  # can't import itself!
            # can't import itself!
            "parent__parent__parent__uuid": ["exact", "in"],
            "parent__id": ["exact", "in"],  # can't import itself!
        }

    def resolve_client_mutation_id(self, info):
        if not info.context.user.is_authenticated:
            raise PermissionDenied(_("unauthorized"))
        location_mutation = (
            self.mutations.select_related("mutation").filter(mutation__status=0).first()
        )
        return (
            location_mutation.mutation.client_mutation_id if location_mutation else None
        )

    @classmethod
    def get_queryset(cls, queryset, info):
        if info.field_name == "locationsAll":
            return queryset
        else:
            return Location.get_queryset(queryset, info.context.user)


class HealthFacilityLegalFormGQLType(DjangoObjectType):
    class Meta:
        model = HealthFacilityLegalForm


class HealthFacilitySubLevelGQLType(DjangoObjectType):
    class Meta:
        model = HealthFacilitySubLevel


class HealthFacilityCatchmentGQLType(DjangoObjectType):
    class Meta:
        model = HealthFacilityCatchment


class HealthFacilityGQLType(DjangoObjectType):
    client_mutation_id = graphene.String()

    class Meta:
        model = HealthFacility
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "uuid": ["exact"],
            "code": ["exact", "istartswith", "icontains", "iexact"],
            "fax": ["exact", "istartswith", "icontains", "iexact", "isnull"],
            "email": ["exact", "istartswith", "icontains", "iexact", "isnull"],
            "name": ["exact", "istartswith", "icontains", "iexact"],
            "level": ["exact"],
            "sub_level": ["exact", "isnull"],
            "care_type": ["exact"],
            "legal_form__code": ["exact"],
            "phone": ["exact", "istartswith", "icontains", "iexact"],
            "status": ["exact"],
            **prefix_filterset("location__", LocationGQLType._meta.filter_fields),
        }
        connection_class = ExtendedConnection

    def resolve_location(self, info):
        if not info.context.user.is_authenticated:
            raise PermissionDenied(_("unauthorized"))
        if "location_loader" in info.context.dataloaders:
            return info.context.dataloaders["location_loader"].load(self.location_id)

    def resolve_catchments(self, info):
        if not info.context.user.has_perms(
            LocationConfig.gql_query_health_facilities_perms
        ):
            raise PermissionDenied(_("unauthorized"))
        return self.catchments.filter(validity_to__isnull=True)

    def resolve_client_mutation_id(self, info):
        if not info.context.user.has_perms(
            LocationConfig.gql_query_health_facilities_perms
        ):
            raise PermissionDenied(_("unauthorized"))
        health_facility_mutation = (
            self.mutations.select_related("mutation").filter(mutation__status=0).first()
        )
        return (
            health_facility_mutation.mutation.client_mutation_id
            if health_facility_mutation
            else None
        )


class HotspotGQLType(DjangoObjectType):
    client_mutation_id = graphene.String()
    villages = graphene.List(LocationGQLType)

    class Meta:
        model = Hotspot
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "uuid": ["exact"],
            "code": ["exact", "istartswith", "icontains", "iexact", "ne"],
            "name": ["exact", "istartswith", "icontains", "iexact", "ne"],
            # Micro-Catchment (mandatory link)
            "micro_catchment__uuid": ["exact", "in"],
            "micro_catchment__name": ["exact", "istartswith", "icontains", "iexact"],
            # District = the micro-catchment's district (Location type R, top level of the Malawi mapping)
            "micro_catchment__district__uuid": ["exact", "in"],
            # Villages attached to the hotspot (through the HotspotVillage link table)
            "village_links__location__uuid": ["exact", "in"],
            "village_links__location__parent__uuid": ["exact", "in"],
            "village_links__location__parent__parent__uuid": ["exact", "in"],
            "village_links__location__parent__parent__parent__uuid": ["exact", "in"],
        }
        connection_class = ExtendedConnection

    def resolve_villages(self, info):
        if not info.context.user.is_authenticated:
            raise PermissionDenied(_("unauthorized"))
        return self.villages

    def resolve_client_mutation_id(self, info):
        if not info.context.user.is_authenticated:
            raise PermissionDenied(_("unauthorized"))
        return None

    @classmethod
    def get_queryset(cls, queryset, info):
        return Hotspot.get_queryset(queryset, info.context.user)


class UserRegionGQLType(graphene.ObjectType):
    id = graphene.String()
    uuid = graphene.String()
    code = graphene.String()
    name = graphene.String()

    def __init__(self, region):
        if region:
            self.id = str(
                base64.b64encode(f"LocationGQLType:{region.id}".encode()), "utf-8"
            )
            self.uuid = region.uuid
            self.code = region.code
            self.name = region.name


class UserDistrictGQLType(graphene.ObjectType):
    id = graphene.String()
    uuid = graphene.String()
    code = graphene.String()
    name = graphene.String()
    parent = graphene.Field(UserRegionGQLType)

    def __init__(self, district):
        if district:
            self.id = str(
                base64.b64encode(f"LocationGQLType:{district.location_id}".encode()),
                "utf-8",
            )
            self.uuid = district.location.uuid
            self.code = district.location.code
            self.name = district.location.name
            self.parent = UserRegionGQLType(district.location.parent)


class UserDistrictType(DjangoObjectType):
    class Meta:
        model = UserDistrict
        filter_fields = {
            "id": ["exact"],
            "user": ["exact"],
            "location": ["exact"],
        }
        connection_class = ExtendedConnection

    @classmethod
    def get_queryset(cls, queryset, info):
        return UserDistrict.get_queryset(queryset, info)


class OfficerVillageGQLType(DjangoObjectType):
    class Meta:
        model = OfficerVillage

    @classmethod
    def get_queryset(cls, queryset, info):
        return OfficerVillage.get_queryset(queryset, info).filter(
            validity_to__isnull=True
        )


class MicroCatchmentTAGQLType(DjangoObjectType):
    class Meta:
        model = MicroCatchmentTA
        filter_fields = {
            "id": ["exact"],
            "micro_catchment": ["exact"],
            "location": ["exact"],
        }


class MicroCatchmentGVHGQLType(DjangoObjectType):
    class Meta:
        model = MicroCatchmentGVH
        filter_fields = {
            "id": ["exact"],
            "micro_catchment": ["exact"],
            "location": ["exact"],
        }


class MicroCatchmentGQLType(DjangoObjectType):
    client_mutation_id = graphene.String()

    class Meta:
        model = MicroCatchment
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "uuid": ["exact", "in"],
            "code": ["exact", "istartswith", "icontains", "iexact"],
            "name": ["exact", "istartswith", "icontains", "iexact"],
            "type": ["exact"],
            "date_from": ["exact", "lte", "gte"],
            "date_to": ["exact", "lte", "gte"],
            "district__uuid": ["exact"],
            "traditional_authorities__location__uuid": ["exact"],
        }
        connection_class = ExtendedConnection

    def resolve_client_mutation_id(self, info):
        if not info.context.user.is_authenticated:
            raise PermissionDenied(_("unauthorized"))
        return None

    @classmethod
    def get_queryset(cls, queryset, info):
        return MicroCatchment.get_queryset(queryset, info.context.user)

class CatchmentDistrictGQLType(DjangoObjectType):
    class Meta:
        model = CatchmentDistrict
        filter_fields = {
            "id": ["exact"],
            "catchment": ["exact"],
            "location": ["exact"],
        }


class CatchmentGQLType(DjangoObjectType):
    districts = graphene.List(LocationGQLType)

    class Meta:
        model = Catchment
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            "id": ["exact"],
            "uuid": ["exact", "in"],
            "code": ["exact", "iexact", "icontains", "istartswith"],
            "name": ["exact", "iexact", "icontains", "istartswith"],
        }
        connection_class = ExtendedConnection

    def resolve_districts(self, info):
        if not info.context.user.is_authenticated:
            raise PermissionDenied(_("unauthorized"))
        return Location.objects.filter(
            catchment_links__catchment=self,
            catchment_links__validity_to__isnull=True,
            type="R",
            validity_to__isnull=True,
        ).order_by("code")

    @classmethod
    def get_queryset(cls, queryset, info):
        return Catchment.get_queryset(queryset, info.context.user)
import graphene_django_optimizer as gql_optimizer

from core.models import Officer
from core.schema import OrderedDjangoFilterConnectionField
from core.schema import signal_mutation_module_validate
from django.utils.translation import gettext as _
from django.core.exceptions import PermissionDenied
from graphene_django.filter import DjangoFilterConnectionField
from location.gql_mutations import (
    CreateHealthFacilityMutation,
    DeleteHealthFacilityMutation,
    UpdateHealthFacilityMutation,
    CreateLocationMutation,
    UpdateLocationMutation,
    DeleteLocationMutation,
    MoveLocationMutation,
    CreateMicroCatchmentMutation,
    UpdateMicroCatchmentMutation,
    DeleteMicroCatchmentMutation,
    CreateZoneMutation,
    UpdateZoneMutation,
    DeleteZoneMutation,
    get_zone_eligible_villages,
    CreateCatchmentMutation,
    UpdateCatchmentMutation,
    DeleteCatchmentMutation,
)
from location.gql_queries import (
    UserDistrictGQLType,
    LocationGQLType,
    HealthFacilityGQLType,
    MicroCatchmentGQLType,
    ZoneGQLType,
    CatchmentGQLType,

)
from location.models import (
    HealthFacility,
    Location,
    LocationManager,
    UserDistrict,
    LocationMutation,
    HealthFacilityMutation,
    MicroCatchment,
    Zone,
    Cluster,
    Catchment,
)
from location.services import LocationService, HealthFacilityService
from location.apps import LocationConfig
import graphene
from django.db.models import Q
from core import models as core_models
from django.conf import settings


from location.clusters import ClusterQuery, SaveClusterMutation, DeleteClusterMutation


class Query(ClusterQuery, graphene.ObjectType):
    health_facilities = OrderedDjangoFilterConnectionField(
        HealthFacilityGQLType,
        showHistory=graphene.Boolean(),
        orderBy=graphene.List(of_type=graphene.String),
    )
    zones = OrderedDjangoFilterConnectionField(
        ZoneGQLType,
        search=graphene.String(),
        cluster_uuid=graphene.String(),
        orderBy=graphene.List(of_type=graphene.String),
    )
    locations = OrderedDjangoFilterConnectionField(
        LocationGQLType,
        orderBy=graphene.List(of_type=graphene.String),
    )
    locations_all = OrderedDjangoFilterConnectionField(
        LocationGQLType, orderBy=graphene.List(of_type=graphene.String)
    )
    locations_str = OrderedDjangoFilterConnectionField(
        LocationGQLType,
        str=graphene.String(),
        orderBy=graphene.List(of_type=graphene.String),
    )
    user_districts = graphene.List(UserDistrictGQLType)
    officer_locations = graphene.List(
        LocationGQLType,
        officer_code=graphene.String(required=True),
        location_type=graphene.String(required=False),
        description="Returns list of locations assigned to a given enrolment officer.",
    )
    health_facilities_str = DjangoFilterConnectionField(
        HealthFacilityGQLType,
        str=graphene.String(),
        region_uuid=graphene.String(),
        district_uuid=graphene.String(),
        districts_uuids=graphene.List(of_type=graphene.String),
        ignore_location=graphene.Boolean(),
    )
    validate_location_code = graphene.Field(
        graphene.Boolean,
        location_code=graphene.String(required=True),
        description="Checks that the specified location code is unique.",
    )
    validate_health_facility_code = graphene.Field(
        graphene.Boolean,
        health_facility_code=graphene.String(required=True),
        description="Checks that the specified health facility code is unique.",
    )
    micro_catchments = OrderedDjangoFilterConnectionField(
        MicroCatchmentGQLType,
        showHistory=graphene.Boolean(),
        orderBy=graphene.List(of_type=graphene.String),
    )
    zone_eligible_villages = graphene.List(
        LocationGQLType,
        cluster_uuid=graphene.String(required=True),
        zone_uuid=graphene.String(required=False),
        description="Villages selectable for a zone in the given cluster.",
    )
    catchments = OrderedDjangoFilterConnectionField(
        CatchmentGQLType,
        search=graphene.String(),
        district_uuid=graphene.String(),
        showHistory=graphene.Boolean(),
        orderBy=graphene.List(of_type=graphene.String),
    )

    def resolve_zone_eligible_villages(self, info, cluster_uuid, zone_uuid=None, **kwargs):
        if info.context.user.is_anonymous:
            raise PermissionDenied(_("unauthorized"))
        try:
            cluster = Cluster.get_queryset(None, info.context.user).get(
                uuid=cluster_uuid, validity_to__isnull=True
            )
        except Cluster.DoesNotExist:
            return []
        zone = None
        if zone_uuid:
            zone = Zone.get_queryset(None, info.context.user).filter(
                uuid=zone_uuid, validity_to__isnull=True
            ).first()
        return get_zone_eligible_villages(cluster, zone).order_by("name")

    def resolve_zones(self, info, **kwargs):
        if info.context.user.is_anonymous:
            raise PermissionDenied(_("unauthorized"))
        query = Zone.get_queryset(None, info.context.user)
        search = kwargs.get("search")
        if search:
            query = query.filter(Q(code__icontains=search) | Q(name__icontains=search))
        cluster_uuid = kwargs.get("cluster_uuid")
        if cluster_uuid:
            query = query.filter(cluster__uuid=cluster_uuid)
        return gql_optimizer.query(query.all(), info)

    def resolve_health_facilities(self, info, **kwargs):
        show_history = kwargs.get("showHistory", False) and info.context.user.has_perms(
            LocationConfig.gql_query_health_facilities_perms
        )
        # OMT-281 allow anyone to query, limited by the get_queryset
        # if not info.context.user.has_perms(LocationConfig.gql_query_health_facilities_perms):
        if info.context.user.is_anonymous:
            raise PermissionDenied(_("unauthorized"))
        query = HealthFacility.get_queryset(None, info.context.user, **kwargs)
        if not show_history:
            query = HealthFacility.filter_queryset(query)

        query = LocationManager().build_user_location_filter_query(
            info.context.user._u, queryset=query
        )

        return gql_optimizer.query(query.all(), info)

    def resolve_validate_location_code(self, info, **kwargs):
        if not info.context.user.has_perms(LocationConfig.gql_query_locations_perms):
            raise PermissionDenied(_("unauthorized"))
        errors = LocationService.check_unique_code(code=kwargs["location_code"])
        return False if errors else True

    def resolve_validate_health_facility_code(self, info, **kwargs):
        if not info.context.user.has_perms(
            LocationConfig.gql_query_health_facilities_perms
        ):
            raise PermissionDenied(_("unauthorized"))
        errors = HealthFacilityService.check_unique_code(
            code=kwargs["health_facility_code"]
        )
        return False if errors else True

    def resolve_locations(self, info, **kwargs):
        # OMT-281 allow querying to anyone, with limitations in the get_queryset
        # if not info.context.user.has_perms(LocationConfig.gql_query_locations_perms):
        if info.context.user.is_anonymous:
            raise PermissionDenied(_("unauthorized"))

    def resolve_locations_all(self, info, **kwargs):
        if info.context.user.is_anonymous:
            raise PermissionDenied(_("unauthorized"))
        return Location.get_queryset(None, info.context.user).filter(
            *Location.filter_validity()
        )

    def resolve_locations_str(self, info, **kwargs):
        if info.context.user.is_anonymous:
            raise PermissionDenied(_("unauthorized"))

        queryset = Location.get_queryset(None, info.context.user)
        filters = [*Location.filter_validity(**kwargs)]

        str = kwargs.get("str")
        if str is not None:
            filters += [Q(code__icontains=str) | Q(name__icontains=str)]

        return queryset.filter(*filters)

    def resolve_health_facilities_str(self, info, **kwargs):
        if not info.context.user.is_authenticated:
            raise PermissionDenied(_("unauthorized"))
        filters = [*HealthFacility.filter_validity(**kwargs)]
        search = kwargs.get("str")
        district_uuid = kwargs.get("district_uuid")
        district_uuids = kwargs.get("districts_uuids")
        region_uuid = kwargs.get("region_uuid")
        if search is not None:
            filters += [Q(code__icontains=search) | Q(name__icontains=search)]
        if district_uuid is not None:
            filters += [Q(location__uuid=district_uuid)]
        if district_uuids is not None:
            if None not in district_uuids:
                filters += [Q(location__uuid__in=district_uuids)]
        if region_uuid is not None:
            filters += [Q(location__parent__uuid=region_uuid)]

        if kwargs.get("ignore_location", False) is False:
            if settings.ROW_SECURITY and not info.context.user._u.is_superuser:
                filters += [
                    LocationManager().build_user_location_filter_query(
                        info.context.user._u, loc_types=["D"]
                    )
                ]
        return HealthFacility.objects.filter(*filters)

    def resolve_user_districts(self, info, **kwargs):
        if info.context.user.is_anonymous:
            raise PermissionDenied(_("unauthorized"))
        if not isinstance(info.context.user._u, core_models.InteractiveUser):
            raise NotImplementedError(
                "Only Interactive Users are registered for districts"
            )
        return [
            UserDistrictGQLType(d)
            for d in UserDistrict.get_user_districts(info.context.user._u)
        ]

    def resolve_officer_locations(self, info, **kwargs):
        if not info.context.user.has_perms(
            LocationConfig.gql_query_locations_perms
        ):
            raise PermissionDenied(_("unauthorized"))

        current_officer = Officer.objects.get(
            code=kwargs["officer_code"],
            validity_to__isnull=True,
        )
        if "location_type" in kwargs:
            return current_officer.officer_allowed_locations.filter(
                type=kwargs["location_type"]
            ).order_by("name")
        return current_officer.officer_allowed_locations.order_by("name")

    def resolve_micro_catchments(self, info, **kwargs):
        show_history = kwargs.get("showHistory", False)
        if info.context.user.is_anonymous:
            raise PermissionDenied(_("unauthorized"))

        query = MicroCatchment.get_queryset(None, info.context.user)
        if not show_history:
            query = query.filter(validity_to__isnull=True)

        return gql_optimizer.query(query.all(), info)

    def resolve_catchments(self, info, **kwargs):
        if not info.context.user.has_perms(LocationConfig.gql_query_catchments_perms):
            raise PermissionDenied(_("unauthorized"))

        show_history = kwargs.get("showHistory", False)
        search = kwargs.get("search")
        district_uuid = kwargs.get("district_uuid")

        query = Catchment.get_queryset(None, info.context.user)
        if not show_history:
            query = query.filter(validity_to__isnull=True)
        if search:
            query = query.filter(Q(code__icontains=search) | Q(name__icontains=search))
        if district_uuid:
            query = query.filter(
                district_links__location__uuid=district_uuid,
                district_links__validity_to__isnull=True,
            )
        return gql_optimizer.query(query.distinct(), info)


class Mutation(graphene.ObjectType):
    save_cluster = SaveClusterMutation.Field()
    delete_cluster = DeleteClusterMutation.Field()
    create_location = CreateLocationMutation.Field()
    update_location = UpdateLocationMutation.Field()
    delete_location = DeleteLocationMutation.Field()
    move_location = MoveLocationMutation.Field()
    create_health_facility = CreateHealthFacilityMutation.Field()
    update_health_facility = UpdateHealthFacilityMutation.Field()
    delete_health_facility = DeleteHealthFacilityMutation.Field()
    create_micro_catchment = CreateMicroCatchmentMutation.Field()
    update_micro_catchment = UpdateMicroCatchmentMutation.Field()
    delete_micro_catchment = DeleteMicroCatchmentMutation.Field()
    create_zone = CreateZoneMutation.Field()
    update_zone = UpdateZoneMutation.Field()
    delete_zone = DeleteZoneMutation.Field()
    create_catchment = CreateCatchmentMutation.Field()
    update_catchment = UpdateCatchmentMutation.Field()
    delete_catchment = DeleteCatchmentMutation.Field()


def on_location_mutation(sender, **kwargs):
    uuid = kwargs["data"].get("uuid", None)
    if not uuid:
        return []
    if "Location" in str(sender._mutation_class):
        impacted_location = Location.objects.get(uuid=uuid)
        LocationMutation.objects.create(
            location=impacted_location, mutation_id=kwargs["mutation_log_id"]
        )
    if "HealthFacility" in str(sender._mutation_class):
        impacted_health_facility = HealthFacility.objects.get(uuid=uuid)
        HealthFacilityMutation.objects.create(
            health_facility=impacted_health_facility,
            mutation_id=kwargs["mutation_log_id"],
        )
    return []


def bind_signals():
    signal_mutation_module_validate["location"].connect(on_location_mutation)

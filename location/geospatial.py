"""Explicitly scoped dashboard schema; no unrestricted Django model exposure."""
import graphene
from graphene.types.generic import GenericScalar
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Exists, OuterRef

from location.apps import LocationConfig
from location.models import MsrLocationReference, allowed_micro_catchment_district_ids


def permitted_references(user):
    if user.is_anonymous or not user.has_perms(LocationConfig.gql_query_locations_perms):
        raise PermissionDenied("Location access is required")
    qs = MsrLocationReference.objects.all()
    districts = allowed_micro_catchment_district_ids(user)
    if districts is not None:
        permitted_district = MsrLocationReference.objects.filter(
            source_instance=OuterRef("source_instance"), msr_type="districts",
            msr_id=OuterRef("district_msr_id"), location_id__in=districts,
            location__validity_to__isnull=True,
        )
        qs = qs.annotate(_permitted=Exists(permitted_district)).filter(_permitted=True)
    return qs


class GeoReferenceType(graphene.ObjectType):
    id = graphene.ID()
    source_instance = graphene.String()
    msr_type = graphene.String()
    msr_id = graphene.String()
    district_msr_id = graphene.String()
    code = graphene.String()
    name = graphene.String()
    is_micro = graphene.Boolean()
    geometry_relation = graphene.String()
    geometry_sha256 = graphene.String()
    geometry_source = graphene.String()
    revision = graphene.String()
    boundary_status = graphene.String()
    synced_at = graphene.DateTime()
    micro_catchment_uuid = graphene.String()
    matched = graphene.Boolean()

    def resolve_micro_catchment_uuid(self, info):
        return self.micro_catchment.uuid if self.micro_catchment_id else None

    def resolve_matched(self, info):
        return bool(self.location_id or self.micro_catchment_id)


class GeoReferencePage(graphene.ObjectType):
    items = graphene.List(GeoReferenceType)
    total_count = graphene.Int()


class GeoGeometryType(graphene.ObjectType):
    status = graphene.String()
    revision = graphene.String()
    relation = graphene.String()
    source = graphene.String()
    geojson = GenericScalar()


class GeospatialQuery(graphene.ObjectType):
    msr_geo_references = graphene.Field(
        GeoReferencePage, source_instance=graphene.String(), msr_type=graphene.String(),
        district_msr_id=graphene.String(), micro_catchment_uuid=graphene.String(),
        is_micro=graphene.Boolean(),
        offset=graphene.Int(default_value=0), limit=graphene.Int(default_value=100),
    )
    msr_geo_geometry = graphene.Field(GeoGeometryType, reference_id=graphene.ID(required=True))

    def resolve_msr_geo_references(self, info, offset=0, limit=100, **filters):
        qs = permitted_references(info.context.user)
        if offset < 0 or not 1 <= limit <= 200:
            raise ValidationError("Use a nonnegative offset and a limit from 1 to 200")
        for key in ("source_instance", "msr_type", "district_msr_id", "is_micro"):
            if filters.get(key) is not None:
                qs = qs.filter(**{key: filters[key]})
        if filters.get("micro_catchment_uuid"):
            qs = qs.filter(micro_catchment__uuid=filters["micro_catchment_uuid"],
                           micro_catchment__validity_to__isnull=True)
        return GeoReferencePage(
            total_count=qs.count(),
            items=list(qs.select_related("micro_catchment").order_by("source_instance", "msr_type", "msr_id")[offset:offset + limit]),
        )

    def resolve_msr_geo_geometry(self, info, reference_id):
        reference = permitted_references(info.context.user).filter(pk=reference_id).first()
        if reference is None:
            raise PermissionDenied("Reference is unavailable")
        from location.geography import legacy_geometry
        return GeoGeometryType(**legacy_geometry(reference))

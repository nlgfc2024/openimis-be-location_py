"""Cluster API: district is a selection filter, not a stored cluster field."""

import graphene
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from graphene_django import DjangoObjectType

from core import ExtendedConnection
from core.schema import OrderedDjangoFilterConnectionField
from .apps import LocationConfig
from .models import Cluster, Location, allowed_micro_catchment_district_ids


class ClusterGQLType(DjangoObjectType):
    class Meta:
        model = Cluster
        fields = ("id", "uuid", "code", "name", "traditional_authority")
        interfaces = (graphene.relay.Node,)
        connection_class = ExtendedConnection
        filter_fields = {"uuid": ["exact"]}

    @classmethod
    def get_queryset(cls, queryset, info):
        require_permission(info.context.user, LocationConfig.gql_query_clusters_perms)
        return Cluster.get_queryset(queryset, info.context.user).filter(validity_to__isnull=True)


def require_permission(user, permissions):
    if getattr(user, "is_anonymous", True) or not user.has_perms(permissions):
        raise PermissionDenied("unauthorized")


class ClusterQuery(graphene.ObjectType):
    clusters = OrderedDjangoFilterConnectionField(
        ClusterGQLType,
        search=graphene.String(),
        district_uuid=graphene.String(),
        traditional_authority_uuid=graphene.String(),
        orderBy=graphene.List(graphene.String),
    )

    def resolve_clusters(self, info, search=None, district_uuid=None,
                         traditional_authority_uuid=None, **kwargs):
        require_permission(info.context.user, LocationConfig.gql_query_clusters_perms)
        queryset = Cluster.get_queryset(None, info.context.user).filter(
            validity_to__isnull=True
        ).select_related("traditional_authority__parent")
        if search:
            queryset = queryset.filter(Q(code__icontains=search) | Q(name__icontains=search))
        if district_uuid:
            queryset = queryset.filter(traditional_authority__parent__uuid=district_uuid)
        if traditional_authority_uuid:
            queryset = queryset.filter(traditional_authority__uuid=traditional_authority_uuid)
        return queryset.order_by("name", "id")


@transaction.atomic
def save_cluster(user, *, name, traditional_authority_uuid, district_uuid, uuid=None, code=None):
    require_permission(user, LocationConfig.gql_mutation_edit_clusters_perms if uuid
                       else LocationConfig.gql_mutation_create_clusters_perms)
    authorities = Location.objects.filter(
        uuid=traditional_authority_uuid, type="D", validity_to__isnull=True,
        parent__uuid=district_uuid, parent__type="R", parent__validity_to__isnull=True,
    )
    district_ids = allowed_micro_catchment_district_ids(user)
    if district_ids is not None:
        authorities = authorities.filter(parent_id__in=district_ids)
    authority = authorities.first()
    if authority is None:
        raise ValidationError("Select an available traditional authority in the selected district.")
    name = name.strip()
    if not name:
        raise ValidationError("Cluster name is required.")
    if uuid:
        cluster = Cluster.get_queryset(None, user).select_for_update().filter(
            uuid=uuid, validity_to__isnull=True
        ).first()
        if cluster is None:
            raise ValidationError("Cluster not found or access denied.")
        cluster.save_history()
    else:
        cluster = Cluster()
        authority = Location.objects.select_for_update().get(pk=authority.pk)
        prefix = authority.code
        if not prefix:
            raise ValidationError("The Traditional Authority must have a code")
        next_number = 1
        for existing_code in Cluster.objects.filter(code__startswith=prefix).values_list("code", flat=True):
            suffix = existing_code[len(prefix):]
            if suffix.isdigit():
                next_number = max(next_number, int(suffix) + 1)
        code = f"{prefix}{next_number:02d}"
    if not uuid:
        cluster.code = code
    cluster.name = name
    cluster.traditional_authority = authority
    cluster.audit_user_id = user.id_for_audit
    cluster.full_clean()
    cluster.save()
    return cluster


class SaveClusterMutation(graphene.Mutation):
    class Arguments:
        uuid = graphene.String()
        code = graphene.String(required=False)
        name = graphene.String(required=True)
        traditional_authority_uuid = graphene.String(required=True)
        district_uuid = graphene.String(required=True)

    cluster = graphene.Field(ClusterGQLType)

    @classmethod
    def mutate(cls, root, info, **data):
        return cls(cluster=save_cluster(info.context.user, **data))


@transaction.atomic
def delete_cluster(user, uuid):
    require_permission(user, LocationConfig.gql_mutation_delete_clusters_perms)
    cluster = Cluster.get_queryset(None, user).select_for_update().filter(
        uuid=uuid, validity_to__isnull=True
    ).first()
    if cluster is None:
        raise ValidationError("Cluster not found or access denied.")
    # Keep the previous version and audit the actor performing the deletion.
    cluster.save_history()
    from core.utils import TimeUtils
    cluster.validity_to = TimeUtils.now()
    cluster.audit_user_id = user.id_for_audit
    cluster.save()
    return str(cluster.uuid)


class DeleteClusterMutation(graphene.Mutation):
    class Arguments:
        uuid = graphene.String(required=True)

    uuid = graphene.String(required=True)

    @classmethod
    def mutate(cls, root, info, uuid):
        return cls(uuid=delete_cluster(info.context.user, uuid))

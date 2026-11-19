"""Transactional v3 publication persistence, independent of legacy import writers."""
import math
import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils.dateparse import parse_datetime

from location.models import Location, MicroCatchment, MsrLocationReference, MsrCatchmentVillage


PARENT_TYPES = {
    "districts": None, "traditional_authorities": "districts",
    "group_village_heads": "traditional_authorities", "villages": "group_village_heads",
    "constituencies": "districts", "wards": "constituencies",
    "epas": "traditional_authorities", "sections": "epas",
    "clusters": "traditional_authorities", "zones": "clusters",
    "catchments": "traditional_authorities",
}
LOCATION_TYPES = {"districts": "R", "traditional_authorities": "D", "group_village_heads": "W", "villages": "V"}
OPTIONAL_FIELDS = {
    "district_id": "district_msr_id", "parents": "parents", "latitude": "latitude",
    "longitude": "longitude", "point_status": "point_status", "is_micro": "is_micro",
    "geometry_relation": "geometry_relation", "geometry_sha256": "geometry_sha256",
    "source": "geometry_source", "geojson_updated_at": "geojson_updated_at",
    "boundary_status": "boundary_status",
}


def _positive_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValidationError("MSR identities must be positive integer IDs, not location codes.")
    return value


def _validate(row):
    if not isinstance(row, dict) or row.get("type") not in PARENT_TYPES:
        raise ValidationError("Unknown MSR location type.")
    _positive_id(row.get("id"))
    for key, limit in (("code", 100), ("name", 255)):
        if not isinstance(row.get(key), str) or not row[key].strip() or len(row[key]) > limit:
            raise ValidationError(f"MSR {key} must be a nonempty string of at most {limit} characters.")
    revision = row.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise ValidationError("MSR publication revision is required and must be nonnegative.")
    if "district_id" in row:
        _positive_id(row["district_id"])
    if "parents" in row:
        parents = row["parents"]
        if not isinstance(parents, list):
            raise ValidationError("MSR parents must be an array.")
        expected = PARENT_TYPES[row["type"]]
        for parent in parents:
            if expected is None or not isinstance(parent, dict) or parent.get("type") != expected:
                raise ValidationError("MSR parent chain does not match its explicit location types.")
            _positive_id(parent.get("id"))
            expected = PARENT_TYPES[expected]
        if expected is not None:
            raise ValidationError("MSR parent chain must include all administrative ancestors.")
        district = row["id"] if row["type"] == "districts" else parents[-1]["id"]
        if "district_id" in row and row["district_id"] != district:
            raise ValidationError("MSR district ID disagrees with its parent chain.")
    for key, maximum in (("latitude", 90), ("longitude", 180)):
        value = row.get(key)
        if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                  or not math.isfinite(value) or abs(value) > maximum):
            raise ValidationError(f"Invalid MSR {key}.")
    if "is_micro" in row and row["is_micro"] is not None and not isinstance(row["is_micro"], bool):
        raise ValidationError("MSR is_micro must be a boolean or null.")
    if row.get("boundary_status") not in (None, "available", "unavailable", "delivery_unavailable"):
        raise ValidationError("Unknown MSR boundary status.")


class MsrReferenceWriter:
    def __init__(self, source_instance):
        if not isinstance(source_instance, str) or not source_instance.strip() or len(source_instance) > 100:
            raise ValidationError("A stable MSR source instance key is required.")
        self.source_instance = source_instance

    @transaction.atomic
    def push(self, rows):
        """Import a complete batch parent-first, or roll back the entire batch.

        A source instance identifies the MSR installation, not a temporary URL.
        References do not create/reparent CoreMIS locations or infer membership.
        """
        pending = list(rows)
        for row in pending:
            _validate(row)
        written = []
        while pending:
            remaining = []
            for row in pending:
                parents = row.get("parents", [])
                if any(not MsrLocationReference.objects.filter(
                    source_instance=self.source_instance, msr_type=p["type"], msr_id=p["id"],
                ).exists() for p in parents):
                    remaining.append(row)
                    continue
                written.append(self._write(row))
            if len(remaining) == len(pending):
                raise ValidationError("Import MSR administrative parents before their children.")
            pending = remaining
        return written

    @transaction.atomic
    def replace_memberships(self, snapshots):
        """Replace only complete successful endpoint responses for named catchments."""
        catchment_ids, village_ids, pairs = [], set(), []
        for snapshot in snapshots:
            revision = snapshot.get("revision")
            if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
                raise ValidationError("Membership snapshots require a nonnegative publication revision.")
            catchment_id = _positive_id(snapshot.get("catchment_id"))
            catchment = MsrLocationReference.objects.select_for_update().get(
                source_instance=self.source_instance, msr_type="catchments", msr_id=catchment_id, is_micro=True,
            )
            if revision < catchment.revision:
                continue  # An old publication retry cannot change its membership snapshot.
            if catchment.pk in catchment_ids:
                raise ValidationError("Duplicate MSR catchment membership snapshot.")
            catchment_ids.append(catchment.pk)
            if not isinstance(snapshot.get("village_ids"), list):
                raise ValidationError("MSR membership snapshot requires a village ID array.")
            for village_id in set(_positive_id(value) for value in snapshot["village_ids"]):
                village = MsrLocationReference.objects.get(
                    source_instance=self.source_instance, msr_type="villages", msr_id=village_id,
                    district_msr_id=catchment.district_msr_id,
                )
                if village.pk in village_ids:
                    raise ValidationError("MSR village belongs to multiple catchments in one snapshot.")
                village_ids.add(village.pk)
                pairs.append(MsrCatchmentVillage(catchment=catchment, village=village))
        # Replacement and moves are atomic, including an authoritative empty response.
        MsrCatchmentVillage.objects.filter(
            Q(catchment_id__in=catchment_ids) | Q(village_id__in=village_ids),
        ).delete()
        MsrCatchmentVillage.objects.bulk_create(pairs)

    def _write(self, row):
        ref, created = MsrLocationReference.objects.select_for_update().get_or_create(
            source_instance=self.source_instance, msr_type=row["type"], msr_id=row["id"],
            defaults={"code": row["code"], "name": row["name"]},
        )
        if not created and row["revision"] < ref.revision:
            return ref  # A retried older publication cannot restore a removed boundary.
        if created and ("parents" not in row or "district_id" not in row):
            raise ValidationError("New references require district_id and a complete parents array.")
        ref.code, ref.name, ref.revision = row["code"], row["name"], row["revision"]
        for source, target in OPTIONAL_FIELDS.items():
            if source in row:
                value = row[source]
                if source == "geojson_updated_at" and value is not None:
                    if not isinstance(value, str):
                        raise ValidationError("MSR publication timestamp must be an ISO datetime.")
                    try:
                        value = parse_datetime(value)
                    except ValueError:
                        value = None
                    if value is None:
                        raise ValidationError("Invalid MSR publication timestamp.")
                setattr(ref, target, value)
        if (ref.latitude is None) != (ref.longitude is None):
            raise ValidationError("MSR coordinates require a complete pair or explicit nulls.")
        _validate({"id": ref.msr_id, "type": ref.msr_type, "code": ref.code, "name": ref.name,
                   "revision": ref.revision, "district_id": ref.district_msr_id, "parents": ref.parents})
        self._match(ref)
        ref.full_clean()
        ref.save()
        return ref

    def _match(self, ref):
        """Only attach an unambiguous active code within its verified parent scope."""
        existing_micro = ref.micro_catchment if ref.micro_catchment_id else None
        ref.location = None
        ref.micro_catchment = None
        if ref.msr_type in LOCATION_TYPES:
            candidates = Location.objects.filter(
                code=ref.code, type=LOCATION_TYPES[ref.msr_type], validity_to__isnull=True,
            )
            if ref.msr_type == "districts":
                candidates = candidates.filter(parent__isnull=True)
            else:
                parent = ref.parents[0]
                parent_ref = MsrLocationReference.objects.get(
                    source_instance=self.source_instance, msr_type=parent["type"], msr_id=parent["id"],
                )
                if not parent_ref.location_id:
                    return
                candidates = candidates.filter(parent_id=parent_ref.location_id)
            matches = list(candidates[:2])
            if len(matches) > 1:
                raise ValidationError("Ambiguous active CoreMIS location code; resolve duplicates first.")
            ref.location = matches[0] if matches else None
        elif ref.msr_type == "catchments" and ref.is_micro is True:
            district = MsrLocationReference.objects.get(
                source_instance=self.source_instance, msr_type="districts", msr_id=ref.district_msr_id,
            )
            if existing_micro:
                if existing_micro.validity_to is not None or existing_micro.district_id != district.location_id:
                    raise ValidationError("The existing MSR micro-catchment link requires review after its district or target changed.")
                ref.micro_catchment = existing_micro
                return
            if district.location_id:
                matches = list(MicroCatchment.objects.filter(
                    code=ref.code, district_id=district.location_id, validity_to__isnull=True,
                )[:2])
                if len(matches) > 1:
                    raise ValidationError("Ambiguous active CoreMIS micro-catchment code.")
                ref.micro_catchment = matches[0] if matches else None


@transaction.atomic
def bind_msr_micro_catchment(reference_id, target_uuid, user):
    """Explicitly review a link when MSR and CoreMIS use different code systems."""
    from location.apps import LocationConfig
    from django.core.exceptions import PermissionDenied
    if (user.is_anonymous or not user.has_perms(LocationConfig.gql_mutation_edit_micro_catchments_perms)
            or not user.has_perms(LocationConfig.gql_query_locations_perms)):
        raise PermissionDenied("Micro-catchment edit and location-view permissions are required")
    target = MicroCatchment.get_queryset(None, user).get(uuid=target_uuid, validity_to__isnull=True)
    ref = MsrLocationReference.objects.select_for_update().get(pk=reference_id, msr_type="catchments", is_micro=True)
    district = MsrLocationReference.objects.get(source_instance=ref.source_instance,
                                               msr_type="districts", msr_id=ref.district_msr_id)
    if district.location_id != target.district_id:
        raise ValidationError("Reviewed target must belong to the matched MSR district")
    if ref.micro_catchment_id and ref.micro_catchment_id != target.pk:
        raise ValidationError("An existing target must be reviewed separately before reassignment")
    if MsrLocationReference.objects.filter(source_instance=ref.source_instance, micro_catchment=target).exclude(pk=ref.pk).exists():
        raise ValidationError("This CoreMIS micro-catchment is already linked in the MSR instance")
    ref.micro_catchment = target
    ref.full_clean()
    ref.save()
    logging.getLogger(__name__).info("Reviewed MSR link: actor=%s reference=%s target=%s", user.pk, ref.pk, target.uuid)
    return ref

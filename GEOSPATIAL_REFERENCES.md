# MSR geospatial references (chunk 2)

`location.MsrLocationReference` stores stable MSR identities and publication
metadata separately from the existing CoreMIS hierarchy. Migration
`0033_msr_location_reference` creates only the new reference table and its unique
identity / single-target constraints. No existing tables are repurposed.

`location.msr_reference.MsrReferenceWriter(source_instance).push(rows)` accepts
MSR v3 location objects. The instance key must consistently identify the MSR
installation across source configurations and URL changes. All writes are atomic
per batch. Missing ancestors fail the batch; rows within a batch are reordered
parent-first. Parents contain the original explicit MSR types and IDs.

Repeated imports update references, and lower publication revisions are ignored.
Same-revision metadata is refreshed because geometry delivery availability can
change without a new publication revision. Omitted fields retain their values;
explicit nulls clear nullable metadata. Temporary signed URLs are never stored.
Absence from a listing does not delete anything. Delivery failure and boundary
unavailability remain distinct publication statuses.

Matching uses active code/type and matched administrative parent. Districts map
to R, TAs to D, GVHs to W and villages to V. Only `catchments` with `is_micro=true`
can match MicroCatchment, scoped by the matched district. Ambiguous candidates
fail rather than selecting an arbitrary row. Other MSR types, including wards,
remain typed references. Unmatched records remain unlinked for later review;
this writer does not create/reparent CoreMIS locations or infer village membership.

Tests cover idempotency, source isolation, parent ordering, micro-catchment
matching, rollback, stale revisions, removal, field omission, delivery failure,
signed URL exclusion, ward handling, coordinate/hierarchy validation and database
constraints. Run with the backend's configured Django test environment:

```bash
cd ../openimis-be_py/openIMIS
../.venv/bin/python manage.py test location.tests.test_msr_reference --noinput
```

Development verification also exercises the actual migration in a temporary
PostgreSQL schema within a rolled-back transaction. Application migrations have
not been applied by this chunk. Use `manage.py migrate --plan` to review the
pending location migrations before applying them.

Chunk 3 adds `MsrCatchmentVillage` and migration `0034_msrcatchmentvillage`.
`MsrReferenceWriter.replace_memberships(snapshots)` accepts complete verified
endpoint responses (`catchment_id`, `revision`, `village_ids`). It validates the
source instance, catchment classification and village district, rejects conflicting
assignments, and atomically replaces memberships or moves villages between
catchments. Empty successful responses clear memberships; failures and stale
publication retries preserve previous assignments. These are MSR reference links,
separate from existing CoreMIS TA/GVH associations.

The MSR ETL module now connects the v3 source, dedicated adapter/writer, background
staging and source-specific UI. See its `GEOSPATIAL_IMPLEMENTATION.md` for activation
steps. GraphQL/map exposure and live publication lifecycle verification follow in
subsequent chunks.

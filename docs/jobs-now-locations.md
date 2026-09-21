# Jobs-Now Clusters and Zones

Jobs Now uses Micro Catchments alongside Clusters. Existing Hotspots remain
children of Micro Catchments; Zones are children of Clusters. These concepts
coexist and must not be implemented by renaming each other's tables or records.

## Schema and branch base

This change is based on the current Malawi location/catchment code-generation
fixes. `0031_cluster` and `0032_zone` only create `tblClusters`, `tblZones`, and
`tblZoneVillages`. Both migrations reverse normally. Existing Hotspot models,
tables, village assignments, and external foreign keys are unchanged. New Zone
tables start empty, even if the database already contains Hotspots.

Keep `jobs-now/develop` current with `mw/develop` before adding migrations.
Future parallel migration branches still need their dependency graph reconciled;
numeric prefixes alone neither prevent nor resolve divergent migration leaves.

## Permissions and menu configuration

Each entity has its own View/Add/Edit/Delete rights:

| Entity | View | Add | Edit | Delete |
| --- | --- | --- | --- | --- |
| Clusters | 121921 | 121922 | 121923 | 121924 |
| Hotspots | 121925 | 121926 | 121927 | 121928 |
| Zones | 121931 | 121932 | 121933 | 121934 |

Dedicated Hotspot permission checks are intentionally retained at the user's
request. They are the deliberate difference from upstream Hotspot behavior;
there is no Hotspot schema or data migration.

Rights are exposed through location module configuration. Grant them to roles
through Roles Management or the explicit setup command below. No migration
assigns roles or rewrites frontend configuration.

The frontend registers `location.clusters` and `admin.zones`. If a deployment
uses an explicit Administration menu whitelist, preview its update with:

```sh
python manage.py configure_jobs_now_locations
python manage.py configure_jobs_now_locations --role-id ROLE_ID
```

After reviewing the output, repeat the selected command with `--apply`.
The optional role receives all twelve rights above. Existing menu items,
including `admin.hotspots`, and their positions are preserved. Repeated runs
are idempotent. A deployment using the default menus needs no whitelist change.
Sign in again after changing role permissions.

## Databases that used the superseded development migrations

The earlier, unmerged branch renamed Hotspots into Zones and later copied them
back. Those migrations have been removed from this PR, not extended with another
repair migration. Databases that never ran that branch need only normal migration.

Do not attempt to roll the superseded chain back or blindly fake the new migration.
For a disposable development database, rebuild from the current base and reapply
the revised migrations. Export any genuine Cluster/Zone work before rebuilding.

For a development database whose records must be retained, first archive the
Cluster, Zone, Zone-village, Hotspot, Hotspot-village and migration-history rows.
Reconcile it explicitly: remove only unassigned Zone copies whose UUID already
exists as a Hotspot, preserve genuine Cluster-based Zones and their links,
remove the obsolete Zone Micro Catchment column, and verify the Cluster foreign
key and final schema against `0032_zone`. Only then replace the superseded
location migration-history entries with the verified new state. Leave Hotspot
records and external references unchanged. This is a one-time development
transition, not part of the application's migration chain.

## Future enhancement

Define shared administrative location types and program-specific groupings with
documented relationships, including overlapping groupings where a strict tree
is insufficient. Each program could select the levels it requires and reuse
selection, filtering and validation rather than repurposing existing entities.
This broader location-model work is outside this change.

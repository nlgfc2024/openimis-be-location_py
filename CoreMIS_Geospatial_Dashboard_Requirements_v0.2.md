# CoreMIS Geospatial Dashboard — Requirements Specification

**Version:** 0.2 — draft for stakeholder review

**Date:** 16 November 2026

**System:** CoreMIS

**Delivery branch:** `feature/geospatial-dashboard`

This document defines the required CoreMIS behavior. It is not a statement that all requirements
have already been delivered or accepted. The implementation baseline below is based on the
repository and recorded development checks; production readiness requires the acceptance evidence in
this specification.

## 1. Purpose and intended outcome

CoreMIS shall provide an authorized user with a geospatial view of programme projects, their linked
micro-catchments, verified village coverage and enrolled beneficiaries with usable coordinates. It
shall consume published location information from MSR while retaining CoreMIS ownership of projects,
programme enrolments, user permissions and operational workflows.

The first demonstrable outcome is **one district and one explicitly matched micro-catchment
synchronized from MSR and displayed in CoreMIS**, including an associated project where a valid
CoreMIS link exists. Beneficiary markers are accepted separately when their authorized coordinate
source is confirmed.

## 2. Scope and system responsibilities

| Area                 | CoreMIS responsibility                                                                             |
| -------------------- | -------------------------------------------------------------------------------------------------- |
| Location integration | Retrieve MSR publications and verified memberships; preserve stable identities and metadata.       |
| Project association  | Use the project's existing `micro_catchment` relationship and an explicitly matched MSR reference. |
| Dashboard            | Render permitted geographic layers, projects, counts, status information and beneficiary markers.  |
| Security             | Enforce programme, district, project and beneficiary access on the backend.                        |
| Operations           | Schedule synchronization, report progress/failures and support retry without duplicate imports.    |
| Source provenance    | Show the origin, geometry relation, revision, availability and last synchronization time.          |

MSR remains responsible for geometry publication, replacement, removal, restoration, classification,
source relationships and signed-file delivery.

CoreMIS shall not become an alternative geometry editing or publication system.

## 3. Users and access

These are capability profiles to map onto existing CoreMIS roles, not new roles that may be assumed
to exist.

| Capability profile          | Required access                                                                                                                                  |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| Programme/dashboard viewer  | View permitted projects and geographic summaries within assigned programme and location scope.                                                   |
| District/project officer    | View assigned projects and authorized enrolment details; precise markers require the applicable beneficiary access.                              |
| Synchronization operator    | Start permitted imports and inspect synchronization progress/errors. This capability does not automatically grant beneficiary-coordinate access. |
| Configuration administrator | Configure the backend source and credentials and resolve matching configuration.                                                                 |

**SEC-01.** Every dashboard query, count, detail lookup and geometry-access request shall apply
backend authorization. Hiding controls in React is insufficient.

**SEC-02.** Effective access shall be the intersection of the user's applicable programme,
geographic and record-level permissions. Filters shall never widen it.

Restricted records shall not leak through counts, labels, pagination totals, error messages or
signed links.

**SEC-03.** MSR Bearer credentials shall remain backend-held and shall not appear in browser
requests, frontend configuration, GraphQL source options or logs.

Authorized temporary file links may be delivered to the browser and shall be treated as sensitive,
short-lived capabilities rather than permanent identifiers.

**SEC-04.** Precise beneficiary coordinates and identifying popups shall require the agreed
beneficiary access capability. An administrative map-view capability alone shall not grant this
access. Exact permission codes and coordinate precision remain decisions in Section 21.

## 4. Location identity and data requirements

**DAT-01.** A location reference shall be uniquely identified by source instance, original MSR type
and original MSR ID. The source instance identifies an MSR installation and shall remain stable
across host or port changes.

**DAT-02.** MSR primary keys, MSR codes and CoreMIS primary keys shall remain distinct. For example,
MSR district ID `13` and code `213` shall not be used interchangeably. Codes shall retain string
formatting, including leading zeros.

**DAT-03.** The CoreMIS hierarchy shall be preserved:

| MSR entity            | CoreMIS representation                                         |
| --------------------- | -------------------------------------------------------------- |
| District              | `Location`, type `R`                                           |
| Traditional authority | `Location`, type `D`                                           |
| Group village head    | `Location`, type `W`                                           |
| Village               | `Location`, type `V`                                           |
| Micro-catchment       | Separate `MicroCatchment`, linked through an MSR reference     |
| Other MSR types       | Explicitly typed references until a separate mapping is agreed |

An MSR ward shall never become a GVH merely because CoreMIS uses `W` for GVHs.

**DAT-04.** References shall preserve code/name, administrative parent references, district
identity, coordinates and point status, micro-catchment classification, geometry relation,
publication hash/source/revision/timestamp, availability and last successful synchronization time.
Signed download URLs shall not be stored as permanent reference data.

**DAT-05.** Automatic matching shall require an unambiguous active code/type match within the
applicable parent or district. Unmatched references shall remain unlinked and identifiable for
review. Ambiguous matches shall fail explicitly.

No silent creation, reparenting or arbitrary selection of CoreMIS records is permitted in the
initial release.

**DAT-06.** Catchment–village coverage shall come from the verified MSR membership endpoint.
Geometry containment, shared GVH membership or proximity shall not be used to infer it. Membership
is distinct from administrative ownership.

## 5. Synchronization requirements

| ID     | Requirement                                                                                                                                                                                   |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SYN-01 | Provide a separately configured, location-only v3 source. Preserve the existing household source, endpoints and import behavior.                                                              |
| SYN-02 | Retrieve districts and district-scoped TAs, GVHs, villages and catchments using the MSR v3 location API. Follow every page.                                                                   |
| SYN-03 | Retrieve every page of the verified MSR micro-catchment village endpoint for each selected micro-catchment.                                                                                   |
| SYN-04 | Run synchronization as a background job. The browser shall receive a job handle without waiting for the district download to finish.                                                          |
| SYN-05 | Stage a complete district snapshot; import references parent-first and persist references/memberships transactionally per snapshot.                                                           |
| SYN-06 | Repeated imports shall update existing identities without duplicates. Older publication revisions shall not overwrite newer publication metadata.                                             |
| SYN-07 | A failed or incomplete download shall not be interpreted as an authoritative empty membership list. Failed writes shall roll back before retry status is recorded.                            |
| SYN-08 | A successful complete empty membership response shall remove only the corresponding membership assignments. Verified moves shall update the affected relationships atomically.                |
| SYN-09 | Retries of staged writes shall reuse the staged payload. Staged data shall remain bound to its original source instance.                                                                      |
| SYN-10 | Report queued/running/terminal state, downloaded/imported/failed counts, timestamps, unit identity and sanitized errors through existing job and sync-log facilities.                         |
| SYN-11 | Omitted publication fields shall retain stored values; explicit nulls shall clear nullable values according to the source contract. Absence from a listing alone shall not delete a location. |
| SYN-12 | Use bounded network timeouts/retries and reject credential forwarding through redirects or pagination outside the configured endpoint.                                                        |
| SYN-13 | Preserve appropriate actor/job audit context for synchronization and any later manual reference-link changes. Never log credentials, signed query strings or beneficiary coordinates.         |

The initial release requires operator-triggered imports. The existing background recovery mechanism
shall support interrupted jobs. A recurring business refresh schedule and freshness threshold must
be agreed before production rollout; background execution does not itself mean periodic source
synchronization.

## 6. Dashboard and map requirements

| ID     | Requirement                                                                                                                                                                                                           |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| MAP-01 | Provide a dashboard reachable through authorized CoreMIS navigation and reuse its map component in the project context.                                                                                               |
| MAP-02 | Support district, micro-catchment, programme and project filters within the user's permitted scope. A district change shall clear incompatible dependent selections.                                                  |
| MAP-03 | Show district and micro-catchment geometry where published and available. Offer independent layer visibility, a legend, zoom/pan and fit-to-selection.                                                                |
| MAP-04 | Project context shall use the selected project's existing micro-catchment link. A missing or unmatched link shall show an explicit empty state rather than a guessed boundary.                                        |
| MAP-05 | Identify geometry as an actual boundary or source-area association using the MSR `geometry_relation`. An association shall not be presented as an exact surveyed project boundary.                                    |
| MAP-06 | Selection details shall show permitted name/code, source, relation, revision, availability, synchronization time and matching state. Geometry availability and coordinate availability shall be displayed separately. |
| MAP-07 | Load GeoJSON through authorized temporary access. On link expiry, request fresh access from CoreMIS and retry within a bounded limit. Do not expose the MSR service token.                                            |
| MAP-08 | Replacement shall invalidate the old layer/version. Confirmed removal shall clear the layer; restoration shall load the restored publication revision.                                                                |
| MAP-09 | Distinguish no published geometry, expired access, delivery failure, loading, authorization failure and no matching records. None shall be represented as a successful empty map without explanation.                 |
| MAP-10 | Invalid/unrenderable GeoJSON shall produce a layer-specific error without crashing other dashboard content. Reject unsupported coordinates/geometry types using the agreed contract.                                  |
| MAP-11 | Clear pending responses and cached sensitive layers when selection, user or access scope changes. A delayed response shall not restore a layer from a previous selection.                                             |
| MAP-12 | Provide a text/list alternative with the same authorized selection and status information. Keyboard users shall be able to operate filters and inspect record details.                                                |

A delivery failure shall not delete the stored reference or be described as source removal. If a
previous layer is retained, it shall be clearly labeled as stale; it shall not silently remain the
apparent current boundary.

## 7. Projects and beneficiary markers

**BEN-01.** Project relationships shall come from CoreMIS programme/project records, not from MSR
location names or polygon containment. The current project model already has programme, location and
optional micro-catchment relationships.

**BEN-02.** Beneficiary markers shall originate from authorized CoreMIS programme and project
enrolment records. MSR boundary publication does not supply beneficiary coordinates. The actual GPS
field, ownership and provenance must be confirmed before implementing markers.

**BEN-03.** A usable coordinate pair shall be numeric, finite, in valid latitude/ longitude ranges
and acceptable under the agreed geographic quality policy.

Null, partial, placeholder or unverified coordinates shall not be plotted as valid beneficiary
locations. Coordinates shall not be invented, geocoded or replaced by polygon centroids in this
release.

**BEN-04.** Shared household coordinates shall retain household provenance and shall not be
presented as independently measured individual locations. Group enrolments shall not be expanded
into individual markers without an agreed membership and coordinate rule.

**BEN-05.** The dashboard shall identify enrolled records excluded from mapping because of
missing/invalid GPS. Marker clustering may be used for rendering; cluster counts shall represent the
documented record unit, not imply physical occupancy at the displayed point.

**BEN-06.** Marker selection may link to an existing authorized detail page.

Only the minimum agreed identity fields shall appear in popups. No map interaction shall change
enrolment, payroll, project completion or benefit eligibility.

## 8. Summary measures and counting rules

The following measures define the proposed minimum dashboard summary. Their underlying business
population must be confirmed before implementation.

| Measure                    | Required definition                                                                                                                                                                |
| -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Projects                   | Distinct permitted, non-deleted projects within selected filters. Any project-status restriction shall be visible.                                                                 |
| Linked micro-catchments    | Distinct CoreMIS micro-catchments linked to the selected projects; show separately those without an MSR match.                                                                     |
| Boundary availability      | Distinct selected matched micro-catchments by current publication/delivery status. Source-area associations shall remain separately identifiable.                                  |
| Individual beneficiaries   | Distinct authorized individual beneficiary identities in the agreed current enrolment population. Multiple project enrolments shall not double-count a person in an overall total. |
| Group/household enrolments | Separate count in its documented unit; never add it to the individual count as though the units were equivalent.                                                                   |
| Mappable beneficiaries     | Distinct eligible individual identities with usable, authorized coordinates under the agreed GPS rule.                                                                             |
| GPS coverage               | Mappable individuals ÷ eligible individual population × 100; show numerator/denominator and “not applicable” for a zero denominator.                                               |
| Synchronization freshness  | Last successful district snapshot time and latest job result. A failed run shall not replace the last-success timestamp.                                                           |

Counts and map/list results shall use the same permissions, filters and effective population. The
interface shall distinguish live CoreMIS programme data from MSR metadata last synchronized at a
recorded time. Current eligibility/status, enrolment history and the identity used to deduplicate
people are unresolved business decisions, not assumptions that every enrollment FK is an individual.

## 9. Backend and integration interfaces

**API-01.** Expose paginated, filtered, permission-scoped GraphQL access to references, matching
state, verified memberships and project associations. Do not return unrestricted raw source
payloads.

**API-02.** Provide an authorized operation to refresh geometry access for a stable reference.
Revalidate access at refresh time and return publication revision, availability and expiration
metadata with any temporary URL.

**API-03.** Provide authorized aggregates and beneficiary points using documented identity,
population and coordinate rules. Bound result sizes and support map viewport/pagination or
clustering suitable for the agreed data volume.

**API-04.** Document input/output contracts, error states and filter semantics.

The UI shall not use MSR type/ID, location code and CoreMIS database ID interchangeably or allow
browser-provided identifiers to bypass authorization.

**API-05.** GeoJSON coordinates shall use the agreed WGS84 longitude/latitude order.

Confirm supported Feature/FeatureCollection and geometry types against real published files before
declaring interoperability complete.

## 10. Operational and quality requirements

| ID     | Requirement                                                                                                                                                                           |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NFR-01 | Map/network failure shall leave existing project and programme workflows usable.                                                                                                      |
| NFR-02 | Requests and rendering shall be bounded; cancel obsolete requests and avoid downloading every beneficiary or geometry on initial page load.                                           |
| NFR-03 | Define representative district geometry sizes, concurrent users and point volumes before agreeing measurable response/rendering targets. No performance SLA is assumed by this draft. |
| NFR-04 | Show meaningful errors and recovery actions, including retry, refresh access and view sync log where permitted.                                                                       |
| NFR-05 | Record job-level diagnostics and source/reference revision context sufficient to investigate failures without sensitive payload logging.                                              |
| NFR-06 | Retain staging/audit records according to configured policy. Temporary geometry access caching shall respect expiration and user scope.                                               |
| NFR-07 | Reuse the shared frontend map in location/project modules and maintain module changes in source repositories. Preserve existing payroll/project links.                                |
| NFR-08 | Validate compatibility in supported CoreMIS browsers, dependency versions and deployment configuration. Configure any basemap provider, attribution and network access explicitly.    |

Local integration addresses are CoreMIS frontend `http://localhost:3000/front`, CoreMIS backend
`http://localhost:8000` and MSR `http://localhost:8080`.

If the browser downloads signed files directly, their returned host must be browser-reachable and
MSR must allow the CoreMIS origin. Production addresses, TLS, origin policy and file-delivery
approach require deployment configuration.

## 11. Acceptance tests

| ID    | Scenario and pass condition                                                                                                                                                                                    |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AC-01 | Pilot: synchronize a verified district and matched micro-catchment; show the correct geometry, source label, relation and project link in CoreMIS. Record the actual MSR/CoreMIS identities and revision/hash. |
| AC-02 | Repeat the same import; reference and membership counts remain stable and existing links remain correct.                                                                                                       |
| AC-03 | Import out-of-order parent/child records; parents resolve first. Unresolved/ambiguous matching produces an explicit error or unlinked state according to DAT-05.                                               |
| AC-04 | Follow paginated location and membership responses; final counts equal the complete authorized source response.                                                                                                |
| AC-05 | Simulate a membership download/write failure; previous assignments remain intact, job status is accurate and a staged-write retry does not refetch.                                                            |
| AC-06 | Publish a replacement in MSR, synchronize, refresh the dashboard; the new revision/hash replaces the previous layer. An older retry cannot restore old publication metadata.                                   |
| AC-07 | Remove geometry in MSR; after synchronization/current-state refresh the layer disappears, while the location/project remains. Restore it and display the restored revision.                                    |
| AC-08 | Expire a signed URL; CoreMIS obtains new authorized access without revealing service credentials or requiring permanent URL storage.                                                                           |
| AC-09 | Make geometry delivery fail; show delivery failure rather than source removal. The location and verified memberships remain.                                                                                   |
| AC-10 | Compare permitted and restricted users across list, aggregate, detail, direct-ID and geometry-refresh requests; no out-of-scope records or coordinates are disclosed.                                          |
| AC-11 | Use a project with valid, missing, partial and invalid beneficiary coordinates; only eligible usable points display and coverage counts reconcile with the agreed population.                                  |
| AC-12 | Verify individual/group units and multiple-project deduplication; map/list/count results reconcile under the same filters.                                                                                     |
| AC-13 | Switch district/project while an old request is pending; no stale layer, marker or count appears in the new selection.                                                                                         |
| AC-14 | Verify ward handling, leading-zero codes, source-instance isolation and separate MSR/CoreMIS IDs.                                                                                                              |
| AC-15 | Run existing household import, project and payroll regression checks; their links and operational behavior remain intact.                                                                                      |
| AC-16 | Meet the agreed performance, browser, accessibility and deployment criteria using representative data.                                                                                                         |

Acceptance evidence shall include environment/version, test actor/scope, source IDs,
expected/observed results, job IDs, publication revisions/hashes and failure recovery results. Use
synthetic or appropriately protected beneficiary examples.

## 12. Implementation baseline and delivery phases

| Phase                                           | Recorded status                                                                                                         | Acceptance still required                                                         |
| ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| 1. Local setup and v3 transport                 | Implemented on feature branches; editable backend installs, local frontend builds, authenticated client and pagination. | Live endpoint/credential validation.                                              |
| 2. Reference persistence                        | Implemented model/migration, hierarchy-preserving matching and transactional metadata updates.                          | Application migration deployment and pilot matching confirmation.                 |
| 3. Background synchronization and UI            | Implemented dedicated source/adapter/writer dispatch, staged retries, verified memberships and district input.          | Enable configured source and demonstrate authenticated live synchronization.      |
| 4. Authorized queries and shared map            | Pending.                                                                                                                | API/SEC/MAP acceptance; location and project integration.                         |
| 5. Beneficiary layer and lifecycle verification | Pending.                                                                                                                | Agreed GPS/counting rules, BEN requirements and complete live lifecycle evidence. |

The recorded development checks include 95 backend tests, frontend tests/module build and
Django/migration consistency checks. New location migrations were tested forward/backward in an
isolated PostgreSQL schema. This is development evidence, not a live acceptance result. Application
migrations/source activation and a live synchronization/map demonstration have not been established
by this baseline. No payroll module changes are required for boundary integration.

## 13. Geospatial data dictionary

A geospatial data dictionary shall define the meaning, format, source, ownership and validation
rules for every field exchanged between MSR and CoreMIS or used by the dashboard. The dictionary
shall be maintained as part of the integration documentation and updated when an approved API or
data model changes.

The initial dictionary shall cover, at minimum, the following entities:

| Entity                             | Required fields / attributes                                                                                                                                                     | Description and handling                                                                                                                                      |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| District                           | MSR source instance, MSR entity type, MSR ID, district code, name, CoreMIS reference, publication status, synchronization timestamp                                              | Top-level administrative reference. MSR identifiers and codes shall remain distinct from CoreMIS primary keys.                                                |
| Traditional authority (TA)         | MSR ID, code, name, parent district reference, CoreMIS location reference, status                                                                                                | Administrative child of a district. Parent relationship shall be preserved during synchronization.                                                            |
| Group village head (GVH)           | MSR ID, code, name, parent TA reference, district reference, CoreMIS location reference, status                                                                                  | Administrative child of a TA. It shall not be confused with an MSR ward.                                                                                      |
| Village                            | MSR ID, code, name, parent GVH reference, TA/district references, CoreMIS location reference, coordinate values where published, coordinate status                               | Village identity and administrative hierarchy shall be retained. A village point shall not be treated as a village boundary polygon.                          |
| Micro-catchment                    | MSR ID, code, name, classification, district reference, geometry reference, geometry relation, publication revision/hash, availability                                           | A separately identified geographic/source-area entity, linked to CoreMIS through an explicit MSR reference.                                                   |
| Micro-catchment–village membership | Micro-catchment source reference, village source reference, membership status, source revision, verification/provenance metadata                                                 | Represents the verified relationship between a micro-catchment and villages. It shall not be inferred from proximity or polygon containment.                  |
| Geometry publication               | Stable publication/reference ID, source instance, entity reference, geometry type, CRS, revision, content hash, object/file reference, publication status and timestamps         | Describes the published spatial file or geometry. Temporary signed URLs shall not be treated as stable identifiers.                                           |
| Project association                | CoreMIS project ID, programme ID, location reference, micro-catchment reference, association type/status                                                                         | Uses existing CoreMIS project relationships. It shall not be derived from names or spatial overlap.                                                           |
| Beneficiary/enrolment location     | Authorized CoreMIS record identity, enrolment/project context, coordinate pair, coordinate source, coordinate owner, precision/quality status, capture timestamp where available | Used only where a confirmed, authorized GPS source and applicable access permission exist. Household and individual coordinates shall remain distinguishable. |

For each field, the detailed dictionary shall record: field name; business definition; data type and
format; whether it is mandatory, nullable or conditionally required; source system and owning team;
allowed values; identifier namespace; transformation/mapping rule; validation rule; sensitivity
classification; and example value. The exact API field names and any fields not yet confirmed shall
be finalized against the live MSR API contract and CoreMIS models before implementation.

Unknown, unmapped or unavailable fields shall be documented as unresolved rather than silently
assigned a meaning. Changes to field definitions, code lists or identifier rules shall be versioned
and agreed by the responsible MSR and CoreMIS data owners.

## 14. Coordinate reference system and geometry standards

All spatial data exchanged and rendered by the dashboard shall use an explicitly declared coordinate
reference system (CRS). The source CRS shall be recorded for every geometry or coordinate dataset.
The integration shall not assume that a file is WGS84 solely because its coordinate values appear
plausible.

The preferred interchange standard for web mapping is WGS84, longitude/latitude, commonly identified
as EPSG:4326, subject to confirmation that this matches the authoritative MSR publication contract.
Where MSR publishes data in another CRS, the transformation method, target CRS and validation
process shall be documented and tested. Original source values and CRS provenance shall be retained
where required for audit and reproducibility.

The following geometry rules shall apply:

- GeoJSON coordinate arrays shall follow the longitude, latitude order required by the GeoJSON/WGS84
  contract. Latitude/longitude reversal shall be detected where possible and rejected or quarantined
  rather than silently corrected.

- Supported geometry types shall be explicitly agreed and tested against real MSR files. The initial
  contract shall identify whether Point, MultiPoint, LineString, MultiLineString, Polygon and
  MultiPolygon are supported; unsupported types shall return a clear validation error.

- Point coordinates, including village or beneficiary points, shall remain distinct from polygon or
  multipolygon boundaries. The existence of a village coordinate does not establish the existence of
  a village boundary.

- Polygon and multipolygon geometries shall be checked for valid structure, closed rings where
  required, finite coordinate values, valid ranges and geometry validity before publication or
  rendering.

- Geometry shall retain its source entity, source revision, geometry relation, CRS, publication
  status and content hash.

- A geometry representing an associated source area shall be labelled as an association and shall
  not be displayed or described as a surveyed administrative or project boundary.

- Reprojection, simplification or other geometry processing shall be traceable and shall not
  overwrite the authoritative source publication.

The authoritative MSR data owner and CoreMIS technical team shall agree the CRS, supported geometry
types, precision, geometry validity rules and any simplification requirements before production
acceptance.

## 15. Object storage architecture

Geospatial files such as GeoJSON publications and other approved spatial artefacts shall be stored
using a dedicated object-storage approach rather than being embedded as large binary payloads in
ordinary CoreMIS relational records. PostgreSQL/CoreMIS shall retain the stable metadata and
references required to identify, authorize and track each publication. Object storage shall retain
the actual file content.

The architecture shall provide the following capabilities:

- A dedicated object-storage service or approved storage platform shall be provisioned for
  geospatial publications, with separate development, test and production configuration where
  applicable.

- Each stored object shall have a stable internal object key or identifier. The database shall
  retain the source instance, MSR entity/publication reference, revision, content hash, file format,
  CRS, size, storage state, creation/receipt time and applicable retention metadata.

- Object keys shall not expose sensitive beneficiary or household identifiers. File names and
  metadata shall follow an agreed naming convention that supports source, entity type, entity
  reference and revision without relying on a temporary signed URL.

- Upload and replacement operations shall verify file integrity using a content hash or equivalent
  checksum. Incomplete uploads shall not become the active publication.

- Access shall be mediated by the CoreMIS backend or an explicitly approved secure delivery
  mechanism. Private objects shall not be publicly readable by default. Temporary access links shall
  be short-lived, scope-checked and excluded from permanent database identity fields and logs.

- Replacement shall preserve the ability to identify the active revision and, where retention policy
  permits, previous revisions. Removal and restoration shall update publication state without
  confusing storage or delivery failure with source removal.

- Storage availability, capacity, backup, recovery, lifecycle/retention and deletion policies shall
  be defined by the responsible infrastructure and data owners.

- The design shall specify whether the browser receives files through the CoreMIS backend, a
  controlled reverse proxy or short-lived signed object links. The selected approach shall satisfy
  authorization, CORS, TLS, network reachability and audit requirements.

The object-storage provider, hosting location, capacity, backup policy, retention period, service
credentials and operational owner remain deployment decisions. These shall be agreed and documented
before production rollout. The relational database shall not store permanent signed URLs as object
identities.

## 16. Synchronization frequency and freshness

The initial release shall support operator-triggered synchronization as stated in Section 5. A
recurring synchronization schedule shall be agreed before production rollout so that the dashboard
does not present outdated MSR location information as current.

The synchronization configuration shall support an approved schedule and/or event-triggered refresh
where the MSR API and operational arrangements permit it. The schedule shall be configurable by
environment and source, rather than hard-coded into the frontend. The responsible data owners shall
determine the required frequency based on how often MSR location records, geometry publications and
verified micro-catchment memberships are expected to change.

The synchronization policy shall define:

- The normal refresh interval for location references, geometry publication metadata and verified
  micro-catchment–village memberships.

- Whether urgent publication changes, removals or restorations require an on-demand refresh or
  notification mechanism.

- The maximum acceptable age of a successful district snapshot (freshness threshold) and how that
  threshold is displayed to users.

- Whether a failed scheduled run triggers bounded retries, an operator alert or escalation, and when
  manual intervention is required.

- The treatment of weekends, maintenance windows, API unavailability and planned MSR downtime.

- The responsible operator/team, monitoring arrangement and audit record for scheduled and manual
  runs.

The dashboard shall display the last successful synchronization time and latest job status. A failed
or incomplete run shall not advance the last-success timestamp or cause previously valid references
and memberships to be treated as deleted. The actual schedule and freshness threshold shall be
recorded as an approved operational configuration; any suggested interval during design discussions
shall remain a proposal until formally agreed.

## 17. Data quality and validation

Data quality checks shall be applied to incoming MSR location data, geometry publications, verified
membership records and any CoreMIS coordinates used for mapping. Validation shall take place before
records are committed or made active for dashboard use. Validation failures shall be recorded with
sufficient non-sensitive detail to support correction and retry.

At minimum, validation shall cover:

- **Identity and uniqueness:** required source instance, entity type and source ID; duplicate source
  identities; duplicate or conflicting codes within the applicable administrative parent;
  preservation of leading zeros; and separation of MSR IDs, MSR codes and CoreMIS IDs.

- **Administrative hierarchy:** valid parent references; correct district/TA/GVH/village
  relationships; missing or circular parent links; and prevention of unintended reparenting.

- **Coordinate quality:** numeric and finite values; valid longitude/latitude ranges; declared CRS;
  detection of missing, partial, placeholder or unverified coordinates; and checks for likely
  coordinate-order reversal.

- **Geometry quality:** supported GeoJSON structure and geometry types; valid coordinate nesting;
  valid rings and geometry topology where applicable; non-empty geometry where required; declared
  CRS; and consistency between geometry metadata and file content.

- **Membership quality:** valid micro-catchment and village references; duplicate membership rows;
  complete pagination; source verification/provenance; and atomic handling of membership additions,
  removals and moves.

- **Publication quality:** revision ordering, content hash/checksum, file format, publication
  status, replacement/removal/restoration state and availability of the referenced object.

- **CoreMIS association quality:** unambiguous matching, valid project/micro-catchment relationships
  and prevention of inferred links based only on similar names or spatial proximity.

Records that fail mandatory validation shall be rejected, quarantined or left explicitly unmatched
according to a documented error policy. The system shall not silently repair source identifiers,
invent coordinates, substitute centroids or infer unverified membership. Non-blocking warnings may
be retained where the record can safely be used, but the warning and its effect shall be visible to
authorized operators.

A data-quality report shall summarize records received, accepted, rejected, quarantined, unmatched
and updated, with counts by entity type and reason. It shall identify the source snapshot/revision
and synchronization job. The report shall avoid exposing beneficiary coordinates or other sensitive
data. Data owners shall agree thresholds for acceptable completeness and error rates and define the
process for correcting source data.

## 18. Spatial analysis and reporting

The initial dashboard shall prioritize reliable visualization, filtering and summary measures
defined in Sections 6 and 8. Spatial analysis and extended reporting may be delivered incrementally
after the source data, geometry standards, permissions and data quality have been validated.

Subject to approved data availability and business rules, future or separately approved capabilities
may include:

- Mapping the distribution of projects, enrolled beneficiaries and programme interventions by
  district, TA, GVH, village and micro-catchment.

- Summarizing project and beneficiary counts by an agreed administrative or programme geography,
  using the same permission and deduplication rules as the dashboard.

- Identifying geographic areas with limited or no programme coverage, where the eligible population
  and coverage denominator are available and approved.

- Comparing programme coverage or project implementation across districts and micro-catchments using
  clearly defined measures and reporting periods.

- Showing project status, implementation progress or other approved indicators geographically, while
  retaining the authoritative status in the relevant CoreMIS workflow.

- Exporting authorized map summaries or tabular reports with source, reporting date, filters and
  definitions attached.

Spatial calculations shall use an approved geometry and CRS and shall document whether a result is
based on administrative boundaries, micro-catchment boundaries, source-area associations, verified
membership or point coordinates. The system shall not infer beneficiary eligibility, project
ownership, catchment membership or programme coverage solely from point-in-polygon or proximity
calculations unless a separate business rule is approved.

Any spatial analysis that requires population denominators, historical boundaries, time-series
snapshots or additional source datasets shall identify those dependencies before implementation.
Such capabilities shall not be treated as part of the first demonstrable outcome unless explicitly
prioritized and accepted.

## 19. Data privacy and public dashboard separation

The geospatial dashboard shall distinguish internal operational information from information
approved for public disclosure. Internal CoreMIS access and any public-facing dashboard shall use
separate authorization and data-release rules. A record being visible to an authenticated CoreMIS
user shall not automatically make it suitable for public display.

The following requirements shall apply:

- Precise beneficiary or household coordinates, names, contact details, household identifiers and
  other identifying attributes shall not be exposed on a public dashboard.

- Public outputs shall use approved aggregate or suitably generalized geographic information. The
  responsible data owner shall assess disclosure and re-identification risks before releasing
  small-area counts or combinations of attributes.

- Internal beneficiary markers and identifying popups shall remain subject to the specific backend
  permission requirements in SEC-04 and the agreed coordinate precision policy.

- Public map layers shall be generated from an explicitly approved publication dataset or API
  response, not by exposing internal GraphQL endpoints, database records, object-storage buckets or
  temporary internal file links.

- Public and internal endpoints, caches, exports and access credentials shall be separated. Public
  access shall not provide a route to retrieve restricted internal records by changing identifiers,
  filters or URLs.

- Data minimization shall apply to map popups, tooltips, downloads, logs and analytics. Only fields
  necessary for the approved purpose shall be displayed.

- Any coordinate masking, aggregation, geographic generalization or suppression of small counts
  shall follow a documented policy approved by the relevant data protection and programme
  authorities.

- Access, exports and administrative changes affecting sensitive geographic data shall be auditable
  under the applicable CoreMIS and organizational policies.

Before any public release, stakeholders shall approve the public data fields, geographic resolution,
aggregation and suppression thresholds, refresh frequency, responsible publishing authority, privacy
review and incident-response process. Until that approval is recorded, beneficiary-level coordinates
and identifying details shall remain internal and shall not be included in public dashboard
responses.

## 20. Monitoring and technical alerts

The integration shall provide operational monitoring for synchronization, API communication, data
validation, geometry delivery, object storage and dashboard service health. Monitoring shall allow
support teams to identify a failure, determine its scope and take an appropriate recovery action
without requiring access to sensitive payloads.

At minimum, monitoring shall capture:

- Synchronization job ID, source instance, selected district or unit, start/end time, duration,
  trigger type, status and retry count.

- Counts of records and memberships discovered, downloaded, staged, created, updated, unchanged,
  rejected, unmatched and failed, grouped by entity type.

- MSR API response outcomes, pagination failures, timeout/rate-limit events and
  authentication/authorization failures, with credentials and sensitive query parameters excluded.

- Geometry/object-storage upload, retrieval, checksum, availability and expiry failures, including
  the affected non-sensitive publication/reference ID and revision.

- Data-quality validation failures and recurring unmatched or ambiguous references.

- Background worker, queue and scheduled-job health, including jobs that remain queued or running
  beyond an agreed threshold.

- Dashboard/API availability, response errors and performance indicators against targets agreed
  under NFR-03.

Technical alerts shall be configurable by severity and routed to the responsible operational team
through an agreed channel. Alert conditions shall include repeated synchronization failure, a job
exceeding its expected duration, authentication failure, incomplete pagination, a rise in rejected
or unmatched records, object-storage unavailability, checksum mismatch and geometry-delivery
failure. Thresholds, recipients, escalation paths and support hours shall be agreed before
production operation.

Logs and alerts shall not contain MSR bearer tokens, passwords, signed URL query strings,
beneficiary coordinates, household identifiers or unnecessary personal information. Monitoring shall
use stable internal job/reference identifiers and sanitized error messages. Operational dashboards
shall distinguish a source publication removal from an API outage, an expired temporary link, an
object-storage failure or a CoreMIS processing error.

## 21. Outstanding decisions and stakeholder agreements

The following decisions remain necessary to complete the requirements and establish production
acceptance. They shall be recorded with an agreed decision, responsible owner, date and any
resulting change to the API contract, data model, security configuration or deployment plan.

| Decision area                   | Required agreement                                                                                                                                             | Suggested responsible stakeholders                           |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| MSR API contract                | Confirm production endpoints, authentication, pagination, field definitions, versioning, error responses and verified micro-catchment membership endpoint.     | MSR technical/API team and CoreMIS integration team          |
| Location identity and hierarchy | Confirm source-instance identity, entity types, code uniqueness and administrative parent relationships.                                                       | MSR data owners and CoreMIS data team                        |
| Spatial source availability     | Confirm which entities have point coordinates, polygon boundaries or no geometry; specifically distinguish village coordinates from village boundary polygons. | MSR, NSO where applicable, and geospatial/data teams         |
| CRS and geometry                | Approve CRS, GeoJSON profile, supported geometry types, coordinate precision and validation rules.                                                             | Geospatial and technical teams                               |
| Beneficiary GPS                 | Identify the authoritative CoreMIS GPS field, capture process, ownership, precision, provenance and quality rules.                                             | Programme/data owners and CoreMIS team                       |
| Access and privacy              | Approve role/capability mapping, geographic and programme scope, beneficiary-coordinate access, public data fields and aggregation/suppression rules.          | CoreMIS security, programme and data protection stakeholders |
| Object storage                  | Select the storage platform, hosting location, delivery pattern, capacity, backup, retention, access control and operational owner.                            | Infrastructure, security and CoreMIS teams                   |
| Synchronization operations      | Approve refresh frequency, freshness threshold, trigger/notification approach, retry policy, monitoring owner and escalation path.                             | MSR and CoreMIS operations/data teams                        |
| Data quality                    | Approve mandatory validation rules, warning/rejection thresholds, discrepancy resolution and source-correction workflow.                                       | MSR and CoreMIS data owners                                  |
| Dashboard measures              | Confirm eligible beneficiary population, current enrolment/status rules, identity deduplication, group/household counting and project-status definitions.      | Programme and data owners                                    |
| Spatial reporting scope         | Prioritize any coverage-gap, geographic aggregation, comparison or export requirements beyond the initial map.                                                 | Programme stakeholders and dashboard product owner           |
| Scale and performance           | Provide representative geometry sizes, beneficiary point volumes, expected concurrent users and measurable response/rendering targets.                         | Infrastructure and application teams                         |
| Deployment                      | Confirm production URLs, TLS, CORS/origin policy, browser reachability, basemap provider/attribution and object-file delivery route.                           | Infrastructure, security and application teams               |

Until these decisions are approved, the corresponding requirements shall remain explicitly
unresolved and shall not be treated as completed implementation assumptions. The first pilot shall
validate the highest-priority data, identity, geometry, access and storage decisions using an agreed
district and representative source records.

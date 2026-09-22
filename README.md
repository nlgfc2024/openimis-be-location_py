# openIMIS Backend Location reference module
This repository holds the files of the openIMIS Backend Location reference module.
It is dedicated to be deployed as a module of [openimis-be_py](https://github.com/openimis/openimis-be_py).

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)

## Code climat (develop branch)

[![Maintainability](https://img.shields.io/codeclimate/maintainability/openimis/openimis-be-location_py.svg)](https://codeclimate.com/github/openimis/openimis-be-location_py/maintainability)
[![Test Coverage](https://img.shields.io/codeclimate/coverage/openimis/openimis-be-location_py.svg)](https://codeclimate.com/github/openimis/openimis-be-location_py)

## ORM mapping:
* tblLocations > Location
* tblHF > HealthFacility (partial mapping)
* tblUsersDistricts > UserDistrict

## Listened Django Signals
None

## Services
None

## Reports (template can be overloaded via report.ReportDefinition)
None

## GraphQL Queries
* health_facilities
* health_facilities_str (full text search on code + name)
* locations
* user_districts

## GraphQL Mutations - each mutation emits default signals and return standard error lists (cfr. openimis-be-core_py)
None

## Configuration options (can be changed via core.ModuleConfiguration)
* gql_query_locations_perms: necessary rights to call locations (default:) )[],
* gql_query_health_facilities_perms: necessary rights to call health_facilities and health_facilities_str (default:) [])
* no_location_check : if implementation is at a national scale without any Location check for all Users (default: False)

## Clusters and Zones

Clusters group villages within a Traditional Authority. Zones are children of a
Cluster and can contain villages from that Cluster's Traditional Authority.
They are independent of Micro Catchments and Hotspots: Hotspots remain children
of Micro Catchments. Clusters and Zones provide geographic groupings that can
be used to organize and filter households according to ther villages for operational workflows.

## Cluster, Hotspot and Zone rights

Each entity has separate View, Add, Edit and Delete rights. Configure the
rights for roles through Roles Management or with the setup command below.

| Entity | View | Add | Edit | Delete |
| --- | --- | --- | --- | --- |
| Clusters | 121921 | 121922 | 121923 | 121924 |
| Hotspots | 121925 | 121926 | 121927 | 121928 |
| Zones | 121931 | 121932 | 121933 | 121934 |

## Configure Jobs-Now locations

`configure_jobs_now_locations` previews the required Cluster and Zone menu
entries. Review the preview first, then rerun with `--apply` to save it:

```sh
python manage.py configure_jobs_now_locations
python manage.py configure_jobs_now_locations --apply
```

Use `--role-id` to grant all twelve Cluster, Hotspot and Zone rights to an
active role. It can be combined with `--apply`; sign in again after applying
role changes.

```sh
python manage.py configure_jobs_now_locations --role-id ROLE_ID
python manage.py configure_jobs_now_locations --role-id ROLE_ID --apply
```

## openIMIS Modules Dependencies
* core.models.InteractiveUser

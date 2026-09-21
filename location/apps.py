from django.apps import AppConfig

MODULE_NAME = "location"

DEFAULT_CFG = {
    "gql_query_hotspots_perms": ["121925"],
    "gql_mutation_create_hotspots_perms": ["121926"],
    "gql_mutation_edit_hotspots_perms": ["121927"],
    "gql_mutation_delete_hotspots_perms": ["121928"],
    "gql_query_clusters_perms": ["121921"],
    "gql_mutation_create_clusters_perms": ["121922"],
    "gql_mutation_edit_clusters_perms": ["121923"],
    "gql_mutation_delete_clusters_perms": ["121924"],
    "gql_query_zones_perms": ["121931"],
    "gql_mutation_create_zones_perms": ["121932"],
    "gql_mutation_edit_zones_perms": ["121933"],
    "gql_mutation_delete_zones_perms": ["121934"],
    "location_types": ["R", "D", "W", "V"],
    "gql_query_locations_perms": ["121901"],
    "gql_query_health_facilities_perms": ["121101"],
    "gql_mutation_create_locations_perms": ["121902"],
    "gql_mutation_edit_locations_perms": ["121903"],
    "gql_mutation_delete_locations_perms": ["121904"],
    "gql_mutation_move_location_perms": ["121905"],
    "gql_mutation_create_region_locations_perms": ["121906"],
    "gql_mutation_create_health_facilities_perms": ["121102"],
    "gql_mutation_edit_health_facilities_perms": ["121103"],
    "gql_mutation_delete_health_facilities_perms": ["121104"],
    "gql_mutation_delete_micro_catchments_perms": ["159003"],
    "import_micro_catchments_perms": ["159004"],
    "export_micro_catchments_perms": ["159005"],
    "gql_query_catchments_perms": ["121911"],
    "gql_mutation_create_catchments_perms": ["121912"],
    "gql_mutation_edit_catchments_perms": ["121913"],
    "gql_mutation_delete_catchments_perms": ["121914"],
    "no_location_check": False,

    "health_facility_level": [
        {
            "code": "D",
            "display": "Dispensary",
        },
        {
            "code": "C",
            "display": "Health Centre",
        },
        {
            "code": "H",
            "display": "Hospital",
        },
    ],
    "health_facility_contract_dates_mandatory": False,
}


class LocationConfig(AppConfig):
    gql_query_hotspots_perms = ["121925"]
    gql_mutation_create_hotspots_perms = ["121926"]
    gql_mutation_edit_hotspots_perms = ["121927"]
    gql_mutation_delete_hotspots_perms = ["121928"]
    gql_query_clusters_perms = ["121921"]
    gql_mutation_create_clusters_perms = ["121922"]
    gql_mutation_edit_clusters_perms = ["121923"]
    gql_mutation_delete_clusters_perms = ["121924"]
    gql_query_zones_perms = ["121931"]
    gql_mutation_create_zones_perms = ["121932"]
    gql_mutation_edit_zones_perms = ["121933"]
    gql_mutation_delete_zones_perms = ["121934"]
    name = MODULE_NAME

    location_types = []
    gql_query_locations_perms = []
    gql_query_health_facilities_perms = []
    gql_mutation_create_locations_perms = []
    gql_mutation_create_region_locations_perms = []
    gql_mutation_edit_locations_perms = []
    gql_mutation_delete_locations_perms = []
    gql_mutation_move_location_perms = []
    gql_mutation_create_health_facilities_perms = []
    gql_mutation_edit_health_facilities_perms = []
    gql_mutation_delete_health_facilities_perms = []
    gql_mutation_delete_micro_catchments_perms = ["159003"]
    import_micro_catchments_perms = ["159004"]
    export_micro_catchments_perms = ["159005"]
    gql_query_catchments_perms = ["121911"]
    gql_mutation_create_catchments_perms = ["121912"]
    gql_mutation_edit_catchments_perms = ["121913"]
    gql_mutation_delete_catchments_perms = ["121914"]
    no_location_check = None
    health_facility_level = []
    health_facility_contract_dates_mandatory = None

    def __load_config(self, cfg):
        print("Load cfg", cfg)
        for field in cfg:
            if hasattr(LocationConfig, field):
                setattr(LocationConfig, field, cfg[field])

    def ready(self):
        from core.models import ModuleConfiguration

        cfg = ModuleConfiguration.get_or_default(MODULE_NAME, DEFAULT_CFG)
        self.__load_config(cfg)

    def set_dataloaders(self, dataloaders):
        from .dataloaders import LocationLoader, HealthFacilityLoader

        dataloaders["location_loader"] = LocationLoader()
        dataloaders["health_facility_loader"] = HealthFacilityLoader()

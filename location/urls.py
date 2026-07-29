from django.urls import path

from . import views


urlpatterns = [
    path("micro-catchments/export/", views.export_micro_catchments),
    path("micro-catchments/template/", views.download_micro_catchment_template),
    path("micro-catchments/import/", views.import_micro_catchments),
]

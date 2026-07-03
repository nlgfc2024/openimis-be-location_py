from django.urls import path

from . import views


urlpatterns = [
    path("micro-catchments/export/", views.export_micro_catchments),
    path("micro-catchments/import/", views.import_micro_catchments),
]

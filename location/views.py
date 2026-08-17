import logging

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.views import check_user_rights

from .apps import LocationConfig
from .micro_catchment_workbook import build_template_workbook, build_workbook, import_csv, import_excel
from .models import Location, UserDistrict


logger = logging.getLogger(__name__)


def _district_for_user(request):
    district_uuid = request.query_params.get("district_uuid") or request.data.get("district_uuid")
    if not district_uuid:
        raise ValidationError("district_uuid is required.")
    district = Location.objects.filter(
        uuid=district_uuid, type="R", validity_to__isnull=True
    ).first()
    if not district:
        raise ValidationError("District not found.")

    # UserDistrict assignments still point to level-D locations (Traditional
    # Authorities in the Malawi hierarchy). Export/import operates on the
    # top-level R location stored by MicroCatchment.district, so authorize the
    # selected District through the assigned location's parent.
    allowed_ids = set()
    for user_district in UserDistrict.get_user_districts(request.user):
        assigned_location = user_district.location
        if assigned_location.type == "R":
            allowed_ids.add(assigned_location.id)
        elif assigned_location.parent_id:
            allowed_ids.add(assigned_location.parent_id)

    if district.id not in allowed_ids:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied("You are not assigned to this district.")
    return district


@api_view(["GET"])
@permission_classes([check_user_rights(LocationConfig.export_micro_catchments_perms)])
def export_micro_catchments(request):
    try:
        district = _district_for_user(request)
        content = build_workbook(district)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="micro_catchments_{district.code}.xlsx"'
        )
        return response
    except ValidationError as exc:
        return Response({"success": False, "errors": exc.messages}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
@permission_classes([check_user_rights(LocationConfig.import_micro_catchments_perms)])
def download_micro_catchment_template(request):
    try:
        district = _district_for_user(request)
        content = build_template_workbook(district)
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="micro_catchment_template_{district.code}.xlsx"'
        )
        return response
    except ValidationError as exc:
        return Response({"success": False, "errors": exc.messages}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([check_user_rights(LocationConfig.import_micro_catchments_perms)])
def import_micro_catchments(request):
    try:
        district = _district_for_user(request)
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            raise ValidationError("An .xlsx or .csv file is required.")
        filename = uploaded_file.name.lower()
        if filename.endswith(".xlsx"):
            result = import_excel(uploaded_file, district, request.user.id_for_audit)
        elif filename.endswith(".csv"):
            result = import_csv(uploaded_file, district, request.user.id_for_audit)
        else:
            raise ValidationError("Only .xlsx and .csv files are supported.")
        return Response({"success": True, **result})
    except ValidationError as exc:
        return Response({"success": False, "errors": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.exception("Unexpected micro-catchment import failure")
        return Response(
            {"success": False, "errors": [str(exc)]},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

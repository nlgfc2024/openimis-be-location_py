import logging

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.views import check_user_rights

from .apps import LocationConfig
from .micro_catchment_workbook import build_workbook, import_workbook
from .models import Location, UserDistrict


logger = logging.getLogger(__name__)


def _district_for_user(request):
    district_uuid = request.query_params.get("district_uuid") or request.data.get("district_uuid")
    if not district_uuid:
        raise ValidationError("district_uuid is required.")
    district = Location.objects.filter(
        uuid=district_uuid, type="D", validity_to__isnull=True
    ).first()
    if not district:
        raise ValidationError("District not found.")
    allowed_ids = {
        user_district.location_id
        for user_district in UserDistrict.get_user_districts(request.user)
    }
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


@api_view(["POST"])
@permission_classes([check_user_rights(LocationConfig.import_micro_catchments_perms)])
def import_micro_catchments(request):
    try:
        district = _district_for_user(request)
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            raise ValidationError("An .xlsx file is required.")
        if not uploaded_file.name.lower().endswith(".xlsx"):
            raise ValidationError("Only .xlsx files are supported.")
        result = import_workbook(uploaded_file, district, request.user.id_for_audit)
        return Response({"success": True, **result})
    except ValidationError as exc:
        return Response({"success": False, "errors": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        logger.exception("Unexpected micro-catchment import failure")
        return Response(
            {"success": False, "errors": [str(exc)]},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

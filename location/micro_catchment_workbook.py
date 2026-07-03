from datetime import date, datetime
from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from core.utils import TimeUtils

from .models import Location, MicroCatchment, MicroCatchmentGVH, MicroCatchmentTA


HEADERS = (
    "code",
    "name",
    "type",
    "district_code",
    "ta_codes",
    "gvh_codes",
    "date_from",
    "date_to",
)


def _cell_text(value):
    if value is None:
        return ""
    return str(value).strip()


def _codes(value):
    return [code.strip() for code in _cell_text(value).split(",") if code.strip()]


def _date(value, field, row_number):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(_cell_text(value), "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValidationError(
            f"Row {row_number}: {field} must use YYYY-MM-DD format."
        ) from exc


def _format_sheet(sheet):
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="00677F")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        width = max(len(_cell_text(cell.value)) for cell in column) + 2
        sheet.column_dimensions[get_column_letter(column[0].column)].width = min(max(width, 12), 45)


def build_workbook(district):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "MicroCatchments"
    sheet.append(HEADERS)

    catchments = (
        MicroCatchment.objects.filter(district=district, validity_to__isnull=True)
        .prefetch_related("traditional_authorities__location", "gvhs__location")
        .order_by("code")
    )
    for catchment in catchments:
        ta_codes = catchment.traditional_authorities.filter(
            validity_to__isnull=True
        ).values_list("location__code", flat=True)
        gvh_codes = catchment.gvhs.filter(validity_to__isnull=True).values_list(
            "location__code", flat=True
        )
        sheet.append(
            (
                catchment.code,
                catchment.name,
                catchment.type or "",
                district.code,
                ",".join(ta_codes),
                ",".join(gvh_codes),
                catchment.date_from,
                catchment.date_to,
            )
        )

    # Keep an immediately usable blank row when a district has no catchments yet.
    if sheet.max_row == 1:
        sheet.append(("", "", "", district.code, "", "", "", ""))

    reference = workbook.create_sheet("DistrictLocations")
    reference.append(("type", "code", "name", "parent_code"))
    locations = Location.objects.filter(
        validity_to__isnull=True,
        type__in=("W", "V"),
    ).filter(
        models_for_district(district)
    ).select_related("parent").order_by("type", "code")
    for location in locations:
        reference.append(
            (
                "TA" if location.type == "W" else "GVH",
                location.code,
                location.name,
                location.parent.code if location.parent else "",
            )
        )

    _format_sheet(sheet)
    _format_sheet(reference)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def models_for_district(district):
    from django.db.models import Q

    return Q(type="W", parent=district) | Q(type="V", parent__parent=district)


def parse_workbook(uploaded_file, district):
    try:
        workbook = load_workbook(uploaded_file, data_only=True, read_only=True)
    except Exception as exc:
        raise ValidationError("The uploaded file is not a valid .xlsx workbook.") from exc

    if "MicroCatchments" not in workbook.sheetnames:
        raise ValidationError("The workbook must contain a 'MicroCatchments' sheet.")

    sheet = workbook["MicroCatchments"]
    rows = sheet.iter_rows(values_only=True)
    try:
        supplied_headers = tuple(_cell_text(value).lower() for value in next(rows))
    except StopIteration as exc:
        raise ValidationError("The MicroCatchments sheet is empty.") from exc

    missing = [header for header in HEADERS if header not in supplied_headers]
    if missing:
        raise ValidationError("Missing required columns: %s." % ", ".join(missing))
    indexes = {header: supplied_headers.index(header) for header in HEADERS}

    parsed = []
    seen_codes = set()
    errors = []
    for row_number, row in enumerate(rows, start=2):
        values = {header: row[index] if index < len(row) else None for header, index in indexes.items()}
        if not any(_cell_text(value) for value in values.values()):
            continue
        code = _cell_text(values["code"])
        name = _cell_text(values["name"])
        district_code = _cell_text(values["district_code"])
        row_errors = []
        if not code:
            row_errors.append("code is required")
        if not name:
            row_errors.append("name is required")
        if district_code != district.code:
            row_errors.append(f"district_code must be {district.code}")
        if code in seen_codes:
            row_errors.append(f"code {code} appears more than once")
        seen_codes.add(code)

        ta_codes = _codes(values["ta_codes"])
        gvh_codes = _codes(values["gvh_codes"])
        tas = list(
            Location.objects.filter(
                code__in=ta_codes,
                type="W",
                parent=district,
                validity_to__isnull=True,
            )
        )
        gvhs = list(
            Location.objects.filter(
                code__in=gvh_codes,
                type="V",
                parent__in=tas,
                validity_to__isnull=True,
            )
        )
        missing_tas = sorted(set(ta_codes) - {location.code for location in tas})
        missing_gvhs = sorted(set(gvh_codes) - {location.code for location in gvhs})
        if missing_tas:
            row_errors.append("invalid TA code(s): %s" % ", ".join(missing_tas))
        if missing_gvhs:
            row_errors.append("invalid GVH code(s): %s" % ", ".join(missing_gvhs))
        if not ta_codes:
            row_errors.append("at least one TA code is required")
        if not gvh_codes:
            row_errors.append("at least one GVH code is required")

        try:
            date_from = _date(values["date_from"], "date_from", row_number)
            date_to = _date(values["date_to"], "date_to", row_number)
            if date_from and date_to and date_to < date_from:
                row_errors.append("date_to cannot be before date_from")
        except ValidationError as exc:
            row_errors.extend(exc.messages)
            date_from = date_to = None

        if row_errors:
            errors.append("Row %s: %s." % (row_number, "; ".join(row_errors)))
        else:
            parsed.append(
                {
                    "code": code,
                    "name": name,
                    "type": _cell_text(values["type"]) or None,
                    "date_from": date_from,
                    "date_to": date_to,
                    "tas": tas,
                    "gvhs": gvhs,
                }
            )

    if errors:
        raise ValidationError(errors)
    if not parsed:
        raise ValidationError("The workbook contains no completed micro-catchment rows.")
    return parsed


@transaction.atomic
def import_workbook(uploaded_file, district, audit_user_id):
    records = parse_workbook(uploaded_file, district)
    now = TimeUtils.now()
    created = updated = 0

    for record in records:
        tas = record.pop("tas")
        gvhs = record.pop("gvhs")
        catchment = MicroCatchment.objects.filter(
            code=record["code"], validity_to__isnull=True
        ).first()
        if catchment:
            if catchment.district_id != district.id:
                raise ValidationError(
                    f"Code {record['code']} already belongs to another district."
                )
            catchment.save_history()
            for field, value in record.items():
                setattr(catchment, field, value)
            catchment.audit_user_id = audit_user_id
            catchment.validity_from = now
            catchment.save()
            updated += 1
        else:
            catchment = MicroCatchment.objects.create(
                **record,
                district=district,
                audit_user_id=audit_user_id,
                validity_from=now,
            )
            created += 1

        _sync_links(catchment, tas, MicroCatchmentTA, "traditional_authorities", audit_user_id, now)
        _sync_links(catchment, gvhs, MicroCatchmentGVH, "gvhs", audit_user_id, now)

    return {"created": created, "updated": updated, "total": len(records)}


def _sync_links(catchment, locations, model, related_name, audit_user_id, now):
    location_ids = {location.id for location in locations}
    related = getattr(catchment, related_name)
    related.filter(validity_to__isnull=True).exclude(location_id__in=location_ids).update(validity_to=now)
    existing = set(
        related.filter(validity_to__isnull=True).values_list("location_id", flat=True)
    )
    model.objects.bulk_create(
        [
            model(
                micro_catchment=catchment,
                location=location,
                audit_user_id=audit_user_id,
                validity_from=now,
            )
            for location in locations
            if location.id not in existing
        ]
    )

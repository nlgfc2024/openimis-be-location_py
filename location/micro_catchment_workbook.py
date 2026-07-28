import csv
from datetime import date, datetime
from io import BytesIO, StringIO

from django.core.exceptions import ValidationError
from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from core.utils import TimeUtils

from .models import Location, MicroCatchment, MicroCatchmentGVH, MicroCatchmentTA


CSV_HEADERS = (
    "district_code",
    "district_name",
    "ta_code",
    "ta_name",
    "gvh_code",
    "gvh_name",
    "micro_catchment_code",
    "micro_catchment_name",
    "start_date",
    "end_date",
)


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

EXPORT_HEADERS = (
    "code",
    "micro_catchment_name",
    "type",
    "district_code",
    "ta_code",
    "ta_name",
    "gvh_code",
    "gvh_name",
    "date_from",
    "date_to",
)


def build_template_workbook(district):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "MicroCatchments"
    sheet.append(CSV_HEADERS)
    traditional_authorities = Location.objects.filter(
        type="D",
        parent=district,
        validity_to__isnull=True,
    ).order_by("code")
    rows_written = False
    for ta in traditional_authorities:
        gvhs = Location.objects.filter(
            type="W",
            parent=ta,
            validity_to__isnull=True,
        ).order_by("code")
        ta_has_gvhs = False
        for gvh in gvhs:
            sheet.append((district.code, district.name, ta.code, ta.name, gvh.code, gvh.name, "", "", "", ""))
            rows_written = ta_has_gvhs = True
        if not ta_has_gvhs:
            sheet.append((district.code, district.name, ta.code, ta.name, "", "", "", "", "", ""))
            rows_written = True
    if not rows_written:
        sheet.append((district.code, district.name, "", "", "", "", "", "", "", ""))
    _format_sheet(sheet)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


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
    sheet.append(EXPORT_HEADERS)

    catchments = (
        MicroCatchment.objects.filter(district=district, validity_to__isnull=True)
        .prefetch_related("traditional_authorities__location", "gvhs__location")
        .order_by("code")
    )
    for catchment in catchments:
        ta_locations = [
            link.location
            for link in catchment.traditional_authorities.filter(
                validity_to__isnull=True
            ).select_related("location")
        ]
        gvh_locations = [
            link.location
            for link in catchment.gvhs.filter(
                validity_to__isnull=True
            ).select_related("location__parent")
        ]

        rows = [
            (
                gvh.parent.code if gvh.parent else "",
                gvh.parent.name if gvh.parent else "",
                gvh.code,
                gvh.name,
            )
            for gvh in gvh_locations
        ]
        if not rows:
            rows = [(ta.code, ta.name, "", "") for ta in ta_locations] or [("", "", "", "")]

        for ta_code, ta_name, gvh_code, gvh_name in rows:
            sheet.append(
                (
                    catchment.code,
                    catchment.name,
                    catchment.type or "",
                    district.code,
                    ta_code,
                    ta_name,
                    gvh_code,
                    gvh_name,
                    catchment.date_from,
                    catchment.date_to,
                )
            )

    # Keep an immediately usable blank row when a district has no catchments yet.
    if sheet.max_row == 1:
        sheet.append(("", "", "", district.code, "", "", "", ""))

    _format_sheet(sheet)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


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
    return import_records(records, district, audit_user_id)


def import_csv(uploaded_file, district, audit_user_id):
    try:
        content = uploaded_file.read().decode("utf-8-sig")
        reader = csv.DictReader(StringIO(content))
        supplied_headers = tuple((header or "").strip().lower() for header in (reader.fieldnames or ()))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValidationError("The uploaded file is not a valid UTF-8 CSV file.") from exc

    missing = [header for header in CSV_HEADERS if header not in supplied_headers]
    if missing:
        raise ValidationError("Missing required columns: %s." % ", ".join(missing))

    grouped = {}
    errors = []
    for row_number, row in enumerate(reader, start=2):
        values = {(key or "").strip().lower(): _cell_text(value) for key, value in row.items()}
        code = values["micro_catchment_code"]
        name = values["micro_catchment_name"]
        ta_code = values["ta_code"]
        gvh_code = values["gvh_code"]
        if not code and not name:
            continue

        row_errors = []
        if values["district_code"] != district.code:
            row_errors.append(f"district_code must be {district.code}")
        if not code:
            row_errors.append("micro_catchment_code is required")
        if not name:
            row_errors.append("micro_catchment_name is required")
        ta = Location.objects.filter(
            code=ta_code,
            type="D",
            parent=district,
            validity_to__isnull=True,
        ).first()
        if not ta:
            row_errors.append(f"invalid TA code: {ta_code}")
        gvh = None
        if gvh_code and ta:
            gvh = Location.objects.filter(
                code=gvh_code,
                type="W",
                parent=ta,
                validity_to__isnull=True,
            ).first()
            if not gvh:
                row_errors.append(f"invalid GVH code: {gvh_code}")
        try:
            start_date = _date(values["start_date"], "start_date", row_number)
            end_date = _date(values["end_date"], "end_date", row_number)
            if start_date and end_date and end_date < start_date:
                row_errors.append("end_date cannot be before start_date")
        except ValidationError as exc:
            row_errors.extend(exc.messages)
            start_date = end_date = None
        if row_errors:
            errors.append("Row %s: %s." % (row_number, "; ".join(row_errors)))
            continue

        record = grouped.setdefault(
            code,
            {"name": name, "tas": [], "gvhs": [], "start_date": start_date, "end_date": end_date},
        )
        if record["name"] != name:
            errors.append(f"Row {row_number}: micro_catchment_name is inconsistent for code {code}.")
        elif record["start_date"] != start_date or record["end_date"] != end_date:
            errors.append(f"Row {row_number}: start_date or end_date is inconsistent for code {code}.")
        elif ta.id not in {location.id for location in record["tas"]}:
            record["tas"].append(ta)
        if gvh and gvh.id not in {location.id for location in record["gvhs"]}:
            record["gvhs"].append(gvh)

    if errors:
        raise ValidationError(errors)
    if not grouped:
        raise ValidationError("The CSV contains no completed micro-catchment rows.")

    records = [
        {
            "code": code,
            "name": values["name"],
            "type": None,
            "date_from": values["start_date"],
            "date_to": values["end_date"],
            "tas": values["tas"],
            "gvhs": values["gvhs"],
        }
        for code, values in grouped.items()
    ]
    return import_records(records, district, audit_user_id)


def import_excel(uploaded_file, district, audit_user_id):
    try:
        workbook = load_workbook(uploaded_file, data_only=True, read_only=True)
        sheet = workbook["MicroCatchments"]
        first_row = next(sheet.iter_rows(values_only=True))
        headers = tuple(_cell_text(value).lower() for value in first_row)
    except Exception as exc:
        raise ValidationError("The uploaded file is not a valid MicroCatchments workbook.") from exc

    uploaded_file.seek(0)
    if all(header in headers for header in CSV_HEADERS):
        output = StringIO(newline="")
        writer = csv.writer(output)
        for row in sheet.iter_rows(values_only=True):
            writer.writerow(row)
        converted = BytesIO(output.getvalue().encode("utf-8-sig"))
        return import_csv(converted, district, audit_user_id)
    return import_workbook(uploaded_file, district, audit_user_id)


@transaction.atomic
def import_records(records, district, audit_user_id):
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

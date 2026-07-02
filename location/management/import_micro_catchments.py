#!/usr/bin/env python3
"""
import_micro_catchments.py
--------------------------
Import Micro Catchments from an Excel file into the OpenIMIS database.

Expected Excel columns (case-insensitive, order does not matter):
  - code          (required, unique)
  - name          (required)
  - type          (optional)
  - district_code (required – must match an existing Location with type='D')
  - ta_codes      (optional – comma-separated Location codes with type='W')
  - gvh_codes     (optional – comma-separated Location codes with type='V')
  - date_from     (optional – YYYY-MM-DD)
  - date_to       (optional – YYYY-MM-DD)

Usage
-----
  python import_micro_catchments.py <path_to_excel_file> [--dry-run] [--user-id <id>]

The script must be run from the openIMIS Django project root, or with the
DJANGO_SETTINGS_MODULE environment variable set correctly.

Example:
  cd openimis-be_py/openIMIS
  python ../../openimis-be-location_py/location/management/import_micro_catchments.py \\
      /tmp/micro_catchments.xlsx --user-id 1
"""

import argparse
import os
import sys
import django
from datetime import date


def _setup_django():
    """Bootstrap Django when running as a standalone script."""
    # Try to locate settings automatically from the working directory.
    cwd = os.getcwd()
    if cwd not in sys.path:
        sys.path.insert(0, cwd)
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        # Assume the script is run from openIMIS/ or openimis-be_py/openIMIS/
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "openIMIS.settings")
    django.setup()


def _normalise_columns(df):
    """Return a copy of df with all column names lowercased and stripped."""
    df.columns = [c.strip().lower() for c in df.columns]
    return df


def _get_location(code, loc_type, cache):
    from location.models import Location
    key = (code, loc_type)
    if key not in cache:
        try:
            cache[key] = Location.objects.get(code=code, type=loc_type, validity_to__isnull=True)
        except Location.DoesNotExist:
            cache[key] = None
    return cache[key]


def _parse_codes(cell_value):
    """Split a comma-separated string of codes into a list of stripped strings."""
    if not cell_value or str(cell_value).strip() in ("", "nan"):
        return []
    return [c.strip() for c in str(cell_value).split(",") if c.strip()]


def _parse_date(cell_value):
    if not cell_value or str(cell_value).strip() in ("", "nan"):
        return None
    if isinstance(cell_value, date):
        return cell_value
    try:
        from datetime import datetime
        return datetime.strptime(str(cell_value).strip(), "%Y-%m-%d").date()
    except ValueError:
        try:
            import pandas as pd
            return pd.to_datetime(cell_value).date()
        except Exception:
            return None


def run_import(excel_path: str, audit_user_id: int, dry_run: bool = False):
    try:
        import pandas as pd
    except ImportError:
        print("ERROR: pandas and openpyxl are required. Install with: pip install pandas openpyxl")
        sys.exit(1)

    from location.models import Location, MicroCatchment, MicroCatchmentTA, MicroCatchmentGVH
    from core.utils import TimeUtils

    df = pd.read_excel(excel_path)
    df = _normalise_columns(df)

    required_cols = {"code", "name", "district_code"}
    missing = required_cols - set(df.columns)
    if missing:
        print(f"ERROR: Excel file is missing required columns: {missing}")
        sys.exit(1)

    loc_cache = {}
    now = TimeUtils.now()
    created = updated = skipped = errors = 0

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-based with header

        code = str(row.get("code", "")).strip()
        name = str(row.get("name", "")).strip()
        district_code = str(row.get("district_code", "")).strip()

        if not code or not name or not district_code:
            print(f"  Row {row_num}: SKIP – missing required value (code/name/district_code).")
            skipped += 1
            continue

        district = _get_location(district_code, "D", loc_cache)
        if district is None:
            print(f"  Row {row_num}: ERROR – District '{district_code}' not found.")
            errors += 1
            continue

        # Resolve TA locations
        ta_objs = []
        for ta_code in _parse_codes(row.get("ta_codes", "")):
            ta = _get_location(ta_code, "W", loc_cache)
            if ta is None:
                print(f"  Row {row_num}: WARNING – TA '{ta_code}' not found, skipping it.")
            else:
                ta_objs.append(ta)

        # Resolve GVH locations
        gvh_objs = []
        for gvh_code in _parse_codes(row.get("gvh_codes", "")):
            gvh = _get_location(gvh_code, "V", loc_cache)
            if gvh is None:
                print(f"  Row {row_num}: WARNING – GVH '{gvh_code}' not found, skipping it.")
            else:
                gvh_objs.append(gvh)

        mc_type = str(row.get("type", "")).strip() or None
        date_from = _parse_date(row.get("date_from"))
        date_to = _parse_date(row.get("date_to"))

        if dry_run:
            print(
                f"  Row {row_num}: DRY-RUN – code={code}, name={name}, district={district_code}, "
                f"TAs={[t.code for t in ta_objs]}, GVHs={[g.code for g in gvh_objs]}"
            )
            created += 1
            continue

        # Check if already exists
        existing = MicroCatchment.objects.filter(code=code, validity_to__isnull=True).first()

        if existing:
            # Update
            existing.save_history()
            existing.name = name
            existing.type = mc_type
            existing.district = district
            existing.date_from = date_from
            existing.date_to = date_to
            existing.audit_user_id = audit_user_id
            existing.validity_from = now
            existing.save()
            mc = existing
            updated += 1
            print(f"  Row {row_num}: UPDATED – {code}")
        else:
            mc = MicroCatchment.objects.create(
                code=code,
                name=name,
                type=mc_type,
                district=district,
                date_from=date_from,
                date_to=date_to,
                audit_user_id=audit_user_id,
                validity_from=now,
            )
            created += 1
            print(f"  Row {row_num}: CREATED – {code}")

        # Sync TAs
        ta_ids = {t.id for t in ta_objs}
        mc.traditional_authorities.filter(validity_to__isnull=True).exclude(location_id__in=ta_ids).update(
            validity_to=now
        )
        existing_ta_ids = set(
            mc.traditional_authorities.filter(validity_to__isnull=True).values_list("location_id", flat=True)
        )
        for ta in ta_objs:
            if ta.id not in existing_ta_ids:
                MicroCatchmentTA.objects.create(
                    micro_catchment=mc, location=ta, audit_user_id=audit_user_id, validity_from=now
                )

        # Sync GVHs
        gvh_ids = {g.id for g in gvh_objs}
        mc.gvhs.filter(validity_to__isnull=True).exclude(location_id__in=gvh_ids).update(validity_to=now)
        existing_gvh_ids = set(
            mc.gvhs.filter(validity_to__isnull=True).values_list("location_id", flat=True)
        )
        for gvh in gvh_objs:
            if gvh.id not in existing_gvh_ids:
                MicroCatchmentGVH.objects.create(
                    micro_catchment=mc, location=gvh, audit_user_id=audit_user_id, validity_from=now
                )

    print(
        f"\nImport complete: {created} created, {updated} updated, "
        f"{skipped} skipped, {errors} errors."
    )
    if errors:
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Import Micro Catchments from an Excel file.")
    parser.add_argument("excel_file", help="Path to the Excel file (.xlsx)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate the file without writing to the database.",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        help="Audit user ID to associate with created/updated records (default: 1).",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.excel_file):
        print(f"ERROR: File not found: {args.excel_file}")
        sys.exit(1)

    _setup_django()
    print(f"{'DRY-RUN: ' if args.dry_run else ''}Importing from {args.excel_file} ...")
    run_import(args.excel_file, audit_user_id=args.user_id, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

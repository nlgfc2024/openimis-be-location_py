#!/usr/bin/env python3
"""
generate_micro_catchment_template.py
-------------------------------------
Generates a sample Excel template for use with import_micro_catchments.py.

Usage:
  python generate_micro_catchment_template.py [output_path]
"""
import sys

try:
    import openpyxl
except ImportError:
    print("ERROR: openpyxl is required. Install with: pip install openpyxl")
    sys.exit(1)

output = sys.argv[1] if len(sys.argv) > 1 else "micro_catchments_template.xlsx"

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "MicroCatchments"

headers = [
    "code",
    "name",
    "type",
    "district_code",
    "ta_codes",
    "gvh_codes",
]
ws.append(headers)

# Example row
ws.append([
    "MC001",
    "Example Micro Catchment",
    "Standard",
    "D001",
    "W001,W002",
    "V001,V002,V003",
])

# Column widths
for col in ws.columns:
    max_len = max(len(str(cell.value)) if cell.value else 0 for cell in col)
    ws.column_dimensions[col[0].column_letter].width = max(max_len + 4, 14)

wb.save(output)
print(f"Template saved to: {output}")

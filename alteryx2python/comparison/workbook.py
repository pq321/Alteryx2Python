"""Compare Excel sheet structure, cell values and formula text."""

import math

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


def workbook_snapshot(path):
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        return {
            sheet.title: [
                [(cell.data_type, cell.value) if cell.value is not None else (None, None) for cell in row]
                for row in sheet.iter_rows()
            ]
            for sheet in workbook.worksheets
        }
    finally:
        workbook.close()

def trim_workbook_padding(sheets):
    # Excel writers omit different amounts of trailing cell padding in sparse rows.
    for rows in sheets.values():
        for row in rows:
            while row and row[-1] == (None, None):
                row.pop()
    return sheets


def _excel_numeric_roundoff(left, right):
    if left[0] != "n" or right[0] != "n":
        return False
    a, b = left[1], right[1]
    if not isinstance(a, float) and not isinstance(b, float):
        return False
    if not math.isfinite(a) or not math.isfinite(b):
        return False
    # Excel displays 15 significant digits. Limit equivalence to adjacent
    # Double values that agree at that precision.
    return abs(a - b) <= max(math.ulp(a), math.ulp(b)) and format(a, ".15g") == format(b, ".15g")


def first_workbook_difference(expected_path, actual_path, *, allow_excel_roundoff=False):
    expected = trim_workbook_padding(workbook_snapshot(expected_path))
    actual = trim_workbook_padding(workbook_snapshot(actual_path))
    if list(expected) != list(actual):
        return {"dimension": "sheets", "expected": list(expected), "actual": list(actual)}
    for sheet, before in expected.items():
        after = actual[sheet]
        if len(before) != len(after):
            return {"dimension": "sheet_rows", "sheet": sheet, "expected": len(before), "actual": len(after)}
        for row_number, (left, right) in enumerate(zip(before, after), 1):
            if left == right:
                continue
            for index in range(max(len(left), len(right))):
                one = left[index] if index < len(left) else (None, None)
                two = right[index] if index < len(right) else (None, None)
                if one != two and not (allow_excel_roundoff and _excel_numeric_roundoff(one, two)):
                    return {
                        "dimension": "cell", "sheet": sheet,
                        "cell": f"{get_column_letter(index + 1)}{row_number}",
                        "expected": {"type": one[0], "value": repr(one[1])},
                        "actual": {"type": two[0], "value": repr(two[1])},
                    }
    return None

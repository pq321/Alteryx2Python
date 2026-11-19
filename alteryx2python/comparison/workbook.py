"""Compare Excel sheet structure, cell values and formula text."""

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


def first_workbook_difference(expected_path, actual_path):
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
                if one != two:
                    return {
                        "dimension": "cell", "sheet": sheet,
                        "cell": f"{get_column_letter(index + 1)}{row_number}",
                        "expected": {"type": one[0], "value": repr(one[1])},
                        "actual": {"type": two[0], "value": repr(two[1])},
                    }
    return None

"""Compare Excel sheet structure, cell values and formula text."""

from openpyxl import load_workbook


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

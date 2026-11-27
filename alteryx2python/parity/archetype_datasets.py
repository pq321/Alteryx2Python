"""Deterministic input tables for differential parity cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from alteryx2python.runtime.app_config import Question


@dataclass
class ArchetypeBundle:
    dataset_id: str
    directory: Path
    tables: dict[str, pd.DataFrame]
    files: dict[str, Path]


def _relational():
    left = pd.DataFrame({
        "key": pd.Series([None, "", "A ", "us", "US", "0012", "12", "dup", "dup", "left"], dtype="string"),
        "region": ["A"] * 10, "value": range(10),
    })
    right = pd.DataFrame({
        "value": pd.Series([1.25, 2, 3, 4, 5, 6, 7]),
        "key": pd.Series([None, "", "US", "12", "dup", "dup", "right"], dtype="string"),
        "region": ["A", "B", "A", "A", "A", "A", "A"],
    })
    return {"left": left, "right": right}


def _numeric():
    return {"input": pd.DataFrame({
        "group": ["a", "a", "a", "a", "b", "b", "b", "b", "b", None, "null", "null"],
        "value": [1.5, 2.5, -2.5, 2.675, 0.0, -0.0, 8, 8, 8, 1e12, None, None],
        "integer": pd.Series([-(2**63), 2**63 - 1, *range(10)], dtype="Int64"),
        "weight": [1, 0, -1] * 4,
        "constant": [1] * 12,
    })}


def _text():
    return {"input": pd.DataFrame({"text": pd.Series([
        None, "", " abc  def ", "\tA\r\nB", "中日한😀", "é ß", '"a,b",c',
        "a,(b,c)", "a,,b", "a,b,c,d,e", "0012", "2", "10", "1e-8",
        "-128", "127", "128", "32768", "2147483648", "true", "false",
    ], dtype="string")})}


def _temporal():
    return {"input": pd.DataFrame({"date_text": pd.Series([
        "2024-02-29", "2025-02-28", "2025-01-31", "2024-12-31 23:59:59",
        "2025-01-01 00:00:00", "31 January 2025", "Jan 31, 2025", "2025-02-29", "", None,
    ], dtype="string")})}


def _window():
    groups = [f"G{size}" for size in (1, 2, 7, 50) for _ in range(size)]
    return {"input": pd.DataFrame({
        "group": groups, "ordinal": range(len(groups)),
        "pivot": (["with space", "x+y", "中文", None] * 15),
        "class": ["major"] * 54 + ["minor"] * 6,
    })}


def _structured():
    return {"input": pd.DataFrame({
        "json": ['{"a.b":[{"x":null,"y":true},{"x":2e3}]}', '{"inner":{"empty":[],"map":{}}}', '{"broken":', None],
        "xml": ['<root attr="v"><r><x a="1"/><x>é</x></r><r><x/></r></root>', '<root/>', '<root><truncated>', None],
    })}


def _reporting():
    return {"input": pd.DataFrame({
        "group": ["west", "west", "east", None],
        "title": ['<b>special</b> & "quotes"', "second", "中文", ""],
        "value": [3.25, -5, 25, 0],
    })}


def _file_io():
    return {"input": pd.DataFrame({
        "account": pd.Series(["0012", "12", "17", "0012", "NA", "", None, "中"], dtype="string"),
        "label": pd.Series(["daily", '"quoted"', "one,two", "two\r\nlines", None, "", "é", "末"], dtype="string"),
    })}


_BUILDERS = {
    "D01": _relational, "D02": _numeric, "D03": _text, "D04": _temporal,
    "D05": _window, "D06": _structured, "D07": _file_io,
    "D08": _text, "D09": _reporting,
}


def _write_bundle(dataset_id: str, directory: Path, tables: dict[str, pd.DataFrame]) -> ArchetypeBundle:
    directory.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, frame in tables.items():
        file = directory / f"{name}.csv"
        # Quote strings including intentional empty strings; leave missing cells bare.
        with file.open("w", encoding="utf-8", newline="") as stream:
            def cell_text(value):
                if pd.isna(value):
                    return ""
                if isinstance(value, str):
                    return '"' + value.replace('"', '""') + '"'
                return str(value)

            stream.write(",".join(cell_text(value) for value in frame.columns) + "\r\n")
            for row in frame.itertuples(index=False, name=None):
                stream.write(",".join(cell_text(value) for value in row) + "\r\n")
        paths[name] = file
    if dataset_id == "D07":
        from openpyxl import Workbook
        from openpyxl.workbook.defined_name import DefinedName

        workbook = Workbook()
        cover = workbook.active
        cover.title = "Cover"
        cover.append(["Info"])
        cover.append(["Read data from the second sheet"])
        data = workbook.create_sheet("Data")
        table = tables["input"]
        data.append(list(table.columns))
        for row in table.itertuples(index=False, name=None):
            data.append([None if pd.isna(value) else value for value in row])
        workbook.defined_names.add(DefinedName("CurrentSlice", attr_text="'Data'!$A$1:$B$4"))
        workbook_path = directory / "input.xlsx"
        workbook.save(workbook_path)
        paths["input-workbook"] = workbook_path
    return ArchetypeBundle(dataset_id, directory, tables, paths)


def build_archetype(dataset_id: str, dest_dir: Path) -> ArchetypeBundle:
    key = dataset_id.split("_", 1)[0]
    if key not in _BUILDERS:
        raise ValueError(f"Unknown archetype: {dataset_id}")
    bundle = _write_bundle(key, dest_dir, _BUILDERS[key]())
    if key == "D07":
        for encoding, value in {
            "utf-8": "é 中文", "utf-8-sig": "é 中文", "cp1252": "é €",
            "latin-1": "é", "gbk": "中文", "cp932": "日本語",
        }.items():
            path = dest_dir / f"{encoding}.csv"
            path.write_bytes(f',a,,a\r\n001,"",{value},\r\n'.encode(encoding))
            bundle.files[encoding] = path
        path = dest_dir / "payload.bin"
        path.write_bytes(b"\xff\xfe\x00\xff\x00")
        bundle.files["blob"] = path
        for kind, value in (("numeric", 123), ("text", "different type")):
            path = dest_dir / f"{kind}.xlsx"
            with pd.ExcelWriter(path, engine="openpyxl") as workbook:
                pd.DataFrame({"key": [1]}).to_excel(workbook, sheet_name="Cover", index=False)
                pd.DataFrame({"mixed": [value]}).to_excel(workbook, sheet_name="Data", index=False)
            bundle.files[kind] = path
    return bundle


def derive_universal_perturbations(bundle: ArchetypeBundle) -> dict[str, ArchetypeBundle]:
    rules = {
        "P_EMPTY_0ROW": lambda frame: frame.iloc[:0],
        "P_SINGLE_1ROW": lambda frame: frame.iloc[:1],
        "P_ALL_NULL_COL": lambda frame: frame.assign(**{frame.columns[-1]: pd.NA}),
        "P_NEGATIVE_SCHEMA": lambda frame: frame.rename(columns={frame.columns[0]: "__missing_target__"}),
    }
    return {
        name: _write_bundle(bundle.dataset_id, bundle.directory / name, {
            key: transform(table) for key, table in bundle.tables.items()
        })
        for name, transform in rules.items()
    }


def generate_five_state_answers(question_manifest: list[Question]) -> dict[str, dict]:
    states: dict[str, dict] = {name: {} for name in (
        "default", "alternate_boundary", "special_escaping", "empty_deselected", "invalid_expected_error",
    )}
    special = 'a"b\' \\ 中文 [a-z]+'
    for question in question_manifest:
        default = question.default
        alternate, escaped, empty, invalid = special, special, "", None
        if question.kind == "NumericUpDown":
            edges = [float(value) for value in (question.minimum, question.maximum) if value]
            alternate = next((value for value in edges if value != float(default or 0)), default)
            escaped, invalid = default, (max(edges) + 1 if question.maximum else "not numeric")
        elif question.kind == "Date":
            alternate = date(2024, 2, 29).isoformat() if default != "2024-02-29" else "2025-01-01"
            escaped, invalid = alternate, "2025-02-29"
        elif question.kind in {"CheckBoxGroup", "RadioButtonGroup", "BooleanGroup"}:
            alternate = str(default).lower() not in {"true", "1", "yes"}
            escaped, empty, invalid = alternate, False, "invalid boolean"
        elif question.choices:
            choice = next((value for value in question.choices if value != default), question.choices[0])
            alternate = [choice] if question.kind == "ListBox" else choice
            escaped = next((value for value in question.choices if any(ch in value for ch in "\\'\"")),
                           choice)
            if question.kind == "ListBox":
                escaped, empty, invalid = [escaped], [], ["__unknown_choice__"]
            else:
                invalid = "__unknown_choice__"
        for name, value in zip(states, (default, alternate, escaped, empty, invalid), strict=True):
            states[name][question.name] = value
    return states

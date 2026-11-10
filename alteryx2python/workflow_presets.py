"""Preset data-processing workflows for native-vs-python equivalence proof.

Every preset is deterministic (seeded) and self-contained: the source data is
embedded in a Text Input node and the sink is a DbFileOutput CSV node, so the
identical .yxmd can run under the Alteryx engine and the converted Python.
"""
from __future__ import annotations

import random
from pathlib import Path

from alteryx2python.workflow_generator import WorkflowBuilder

REGIONS = ["North", "South", "East", "West"]
PRODUCTS = ["Widget", "Gadget", "Sprocket", "Gear"]


def _sales_rows(rng: random.Random, count: int) -> tuple[list[str], list[list[object]]]:
    fields = ["OrderID", "Region", "Product", "Quantity", "UnitPrice", "OrderDate"]
    rows = []
    for i in range(count):
        rows.append(
            [
                1000 + i,
                rng.choice(REGIONS),
                rng.choice(PRODUCTS),
                rng.randint(1, 9),
                round(rng.uniform(5, 50), 2),
                f"2024-{1 + i % 12:02d}-{1 + i % 28:02d}",
            ]
        )
    return fields, rows


def build_preset(name: str, csv_path: str, seed: int = 42, rows: int = 40) -> WorkflowBuilder:
    builder = WorkflowBuilder()
    rng = random.Random(seed)
    preset = PRESETS[name]
    preset(builder, rng, csv_path, rows)
    return builder


# ---- presets ---------------------------------------------------------------


def _preset_formula_filter_sort(builder, rng, csv_path, rows):
    fields, data = _sales_rows(rng, rows)
    src = builder.add_text_input(fields, data)
    formula = builder.add_formula([("Revenue", "Double", "", "[Quantity] * [UnitPrice]")])
    filt = builder.add_filter("[Quantity] >= 3")
    sort = builder.add_sort([("Revenue", "Descending")])
    out = builder.add_csv_output(csv_path)
    builder.connect(src, formula)
    builder.connect(formula, filt)
    builder.connect(filt, sort, source_anchor="True")
    builder.connect(sort, out)


def _preset_summarize(builder, rng, csv_path, rows):
    fields, data = _sales_rows(rng, rows)
    src = builder.add_text_input(fields, data)
    summary = builder.add_summarize(
        [
            ("Region", "GroupBy", ""),
            ("Product", "GroupBy", ""),
            ("Quantity", "Sum", "Sum_Quantity"),
            ("UnitPrice", "Avg", "Avg_UnitPrice"),
            ("OrderID", "Count", "Count_Orders"),
        ]
    )
    out = builder.add_csv_output(csv_path)
    builder.connect(src, summary)
    builder.connect(summary, out)


def _preset_join_union(builder, rng, csv_path, rows):
    fields, data = _sales_rows(rng, rows)
    src = builder.add_text_input(fields, data)
    regions = builder.add_text_input(
        ["Region", "Manager"],
        [[region, f"Mgr_{region}"] for region in REGIONS],
        position=(54, 320),
    )
    join = builder.add_join("Region", "Region")
    union = builder.add_union()
    out = builder.add_csv_output(csv_path)
    builder.connect(src, join, target_anchor="Left")
    builder.connect(regions, join, target_anchor="Right")
    builder.connect(join, union, target_anchor="1", source_anchor="Join")
    builder.connect(regions, union, target_anchor="2")
    builder.connect(union, out)


def _preset_select_recordid_sample(builder, rng, csv_path, rows):
    fields, data = _sales_rows(rng, rows)
    src = builder.add_text_input(fields, data)
    select = builder.add_select(
        [("OrderID", "True"), ("Region", "True"), ("Product", "True"), ("Quantity", "True")],
        include_unknown=False,
    )
    record = builder.add_record_id()
    sample = builder.add_sample("First", "10")
    out = builder.add_csv_output(csv_path)
    builder.connect(src, select)
    builder.connect(select, record)
    builder.connect(record, sample)
    builder.connect(sample, out)


def _preset_unique_multirow(builder, rng, csv_path, rows):
    fields, data = _sales_rows(rng, rows)
    src = builder.add_text_input(fields, data)
    unique = builder.add_unique("Region")
    multi = builder.add_multi_row_formula("[Quantity] - [Row-1:Quantity]", "QtyDelta")
    out = builder.add_csv_output(csv_path)
    builder.connect(src, unique)
    builder.connect(unique, multi, source_anchor="Unique")
    builder.connect(multi, out)


def _preset_crosstab(builder, rng, csv_path, rows):
    fields, data = _sales_rows(rng, rows)
    src = builder.add_text_input(fields, data)
    crosstab = builder.add_crosstab("Region", "Product", "Quantity", "First")
    out = builder.add_csv_output(csv_path)
    builder.connect(src, crosstab)
    builder.connect(crosstab, out)


def _preset_transpose(builder, rng, csv_path, rows):
    fields, data = _sales_rows(rng, rows)
    src = builder.add_text_input(fields, data)
    transpose = builder.add_transpose(["OrderID", "Region"], ["Quantity", "UnitPrice"])
    out = builder.add_csv_output(csv_path)
    builder.connect(src, transpose)
    builder.connect(transpose, out)


def _preset_regex_parse(builder, rng, csv_path, rows):
    fields = ["Code", "Amount"]
    data = []
    for i in range(rows):
        data.append([f"AB-{1000 + i}-XY", round(rng.uniform(1, 100), 2)])
    src = builder.add_text_input(fields, data)
    regex = builder.add_regex("Code", r"AB-(\d+)-XY", [("ParsedID", "V_String", 16)])
    out = builder.add_csv_output(csv_path)
    builder.connect(src, regex)
    builder.connect(regex, out)


def _preset_datetime(builder, rng, csv_path, rows):
    fields, data = _sales_rows(rng, rows)
    src = builder.add_text_input(fields, data)
    parsed = builder.add_datetime("OrderDate", "ParsedDate", "yyyy-MM-dd")
    out = builder.add_csv_output(csv_path)
    builder.connect(src, parsed)
    builder.connect(parsed, out)


def _preset_rank_running_total(builder, rng, csv_path, rows):
    fields, data = _sales_rows(rng, rows)
    src = builder.add_text_input(fields, data)
    rank = builder.add_rank("Quantity", order="Descending")
    total = builder.add_running_total("Quantity")
    out = builder.add_csv_output(csv_path)
    builder.connect(src, rank)
    builder.connect(rank, total)
    builder.connect(total, out)


PRESETS = {
    "formula-filter-sort": _preset_formula_filter_sort,
    "summarize": _preset_summarize,
    "join-union": _preset_join_union,
    "select-recordid-sample": _preset_select_recordid_sample,
    "unique-multirow": _preset_unique_multirow,
    "crosstab": _preset_crosstab,
    "transpose": _preset_transpose,
    "regex-parse": _preset_regex_parse,
    "datetime-shift": _preset_datetime,
    "rank-running-total": _preset_rank_running_total,
}


def preset_names() -> list[str]:
    return sorted(PRESETS)


def render_preset(name: str, csv_path: str, seed: int = 42, rows: int = 40) -> str:
    return build_preset(name, csv_path, seed, rows).render()


def write_preset(name: str, yxmd_path: Path, csv_path: Path, seed: int = 42, rows: int = 40) -> str:
    xml = render_preset(name, str(csv_path), seed, rows)
    yxmd_path.write_text(xml, encoding="utf-8")
    return xml

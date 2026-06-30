from __future__ import annotations

import re
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


_COORD_PAIR_RE = re.compile(r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)")
BBox = tuple[float, float, float, float]


def _frame(inputs: dict[str, pd.DataFrame], anchor: str) -> pd.DataFrame:
    if anchor not in inputs:
        raise KeyError(f"SpatialMatch tool requires a {anchor} anchor")
    frame = inputs[anchor]
    if not isinstance(frame, pd.DataFrame):
        raise TypeError(f"{anchor} anchor must contain a pandas DataFrame")
    return frame


def _wkt_points(value: Any) -> list[tuple[float, float]]:
    if not isinstance(value, str):
        return []
    return [(float(match.group(1)), float(match.group(2))) for match in _COORD_PAIR_RE.finditer(value)]


def _bbox(value: Any) -> BBox | None:
    points = _wkt_points(value)
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _contains(outer: BBox, inner: BBox) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def _intersects(left: BBox, right: BBox) -> bool:
    return left[0] <= right[2] and left[2] >= right[0] and left[1] <= right[3] and left[3] >= right[1]


def _matches(target_bbox: BBox | None, universe_bbox: BBox | None, method: str) -> bool:
    if target_bbox is None or universe_bbox is None:
        return False
    normalized = method.lower()
    if normalized == "contains":
        return _contains(target_bbox, universe_bbox)
    if normalized == "within":
        return _contains(universe_bbox, target_bbox)
    return _intersects(target_bbox, universe_bbox)


def _intersection_polygon(left: BBox | None, right: BBox | None) -> str | None:
    if left is None or right is None or not _intersects(left, right):
        return None
    min_x = max(left[0], right[0])
    min_y = max(left[1], right[1])
    max_x = min(left[2], right[2])
    max_y = min(left[3], right[3])
    return (
        f"POLYGON (({min_x:g} {max_y:g}, {max_x:g} {max_y:g}, "
        f"{max_x:g} {min_y:g}, {min_x:g} {min_y:g}, {min_x:g} {max_y:g}))"
    )


def _prefixed_row(row: pd.Series, prefix: str) -> dict[str, Any]:
    return {f"{prefix}_{column}": row[column] for column in row.index}


def _selected_output(joined: pd.DataFrame, select_fields: list[dict[str, Any]]) -> pd.DataFrame:
    if not select_fields:
        return joined
    explicit_sources = {str(field.get("source", "")) for field in select_fields if field.get("source") != "*Unknown"}
    output_columns: dict[str, pd.Series] = {}
    for field in select_fields:
        if not field.get("selected", True):
            continue
        source = str(field.get("source", ""))
        if source == "*Unknown":
            for column in joined.columns:
                if column not in explicit_sources and column not in output_columns:
                    output_columns[column] = joined[column].copy()
            continue
        if source not in joined.columns:
            continue
        rename = str(field.get("rename", source))
        output_columns[rename] = joined[source].copy()
    return pd.DataFrame(output_columns, index=joined.index)


def spatialmatch_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    targets = _frame(inputs, "Targets")
    universe = _frame(inputs, "Universe")
    target_spatial_field = str(config.get("target_spatial_field", ""))
    universe_spatial_field = str(config.get("universe_spatial_field", ""))
    ensure_fields_exist(targets, [target_spatial_field])
    ensure_fields_exist(universe, [universe_spatial_field])

    target_bboxes = [_bbox(value) for value in targets[target_spatial_field]]
    universe_bboxes = [_bbox(value) for value in universe[universe_spatial_field]]
    method = str(config.get("method", "Intersects") or "Intersects")

    rows: list[dict[str, Any]] = []
    for target_position, target_row in enumerate(targets.itertuples(index=False, name=None)):
        target_series = pd.Series(target_row, index=targets.columns)
        target_bbox = target_bboxes[target_position]
        for universe_position, universe_row in enumerate(universe.itertuples(index=False, name=None)):
            universe_series = pd.Series(universe_row, index=universe.columns)
            universe_bbox = universe_bboxes[universe_position]
            if not _matches(target_bbox, universe_bbox, method):
                continue
            row = {
                **_prefixed_row(target_series, "Target"),
                **_prefixed_row(universe_series, "Universe"),
            }
            if bool(config.get("intersect_poly", False)):
                row["IntersectPoly"] = _intersection_polygon(target_bbox, universe_bbox)
            rows.append(row)

    joined = pd.DataFrame(rows)
    select_fields = [field for field in config.get("select_fields", []) if isinstance(field, dict)]
    output = _selected_output(joined, select_fields).reset_index(drop=True)
    outputs = {"Matched": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="SpatialMatch",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Targets": targets, "Universe": universe},
        outputs=outputs,
        status="success",
        config={
            "target_spatial_field": target_spatial_field,
            "universe_spatial_field": universe_spatial_field,
            "method": method,
            "intersect_poly": bool(config.get("intersect_poly", False)),
            "input_schema": {"Targets": snapshot_schema(targets), "Universe": snapshot_schema(universe)},
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class SpatialMatchTool(BaseTool):
    tool_type = "SpatialMatch"
    input_anchors = ("Targets", "Universe")
    output_anchors = ("Matched",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return spatialmatch_tool(inputs, config, context)

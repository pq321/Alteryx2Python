"""Compare a baseline and a single-axis variant at a tool's observable boundary."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .snapshot import compare_snapshots, frame_snapshot


class NonDiscriminatingDatasetError(ValueError):
    """The fixture did not exercise the configuration change."""


@dataclass(frozen=True)
class SensitivityResult:
    changed_anchors: tuple[str, ...]
    outcome_changed: bool
    changed_artifacts: tuple[str, ...]


def verify_config_sensitivity(
    tool_type: str, base_case: dict, variant_case: dict, dataset: str,
) -> SensitivityResult:
    statuses = (base_case["status"], variant_case["status"])
    if any(status not in {"success", "failed"} for status in statuses):
        raise ValueError(f"{tool_type} requires two completed sensitivity runs, got {statuses}")
    if statuses == ("failed", "failed"):
        raise NonDiscriminatingDatasetError(f"{tool_type} failed for both configurations on {dataset}")

    def snapshot(value):
        return frame_snapshot(value) if isinstance(value, pd.DataFrame) else value

    left, right = (case.get("outputs", {}) for case in (base_case, variant_case))
    changed_anchors = tuple(
        anchor for anchor in sorted(left.keys() | right.keys())
        if anchor not in left or anchor not in right
        or compare_snapshots(snapshot(left[anchor]), snapshot(right[anchor]))["status"] == "mismatch"
    )
    left_files, right_files = (case.get("artifacts", {}) for case in (base_case, variant_case))
    changed_artifacts = tuple(
        name for name in sorted(left_files.keys() | right_files.keys())
        if left_files.get(name) != right_files.get(name)
    )
    outcome_changed = statuses[0] != statuses[1]
    if not (changed_anchors or outcome_changed or changed_artifacts):
        raise NonDiscriminatingDatasetError(f"{tool_type} configuration flip produced no observable change on {dataset}")
    return SensitivityResult(changed_anchors, outcome_changed, changed_artifacts)

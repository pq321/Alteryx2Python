"""Native-vs-Python equivalence harness.

Runs the SAME workflow through the native Alteryx backends and the converted
Python runtime, then compares outputs at the value level.

On hosts whose license includes the automation feature ("API or FlowChartMode")
the native side runs automatically (engine-cmd, or the Designer command-line
run channel). On hosts without it the native attempt is recorded in the report
with its exact license detail and the comparison falls back to any explicit
oracle file, so the evidence trail stays complete.
"""

from __future__ import annotations

import json
import hashlib
import time
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from alteryx2python.native_runner import run_native
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.workflow_presets import preset_names, render_preset


@dataclass
class FrameComparison:
    matches: bool
    row_counts: tuple[int, int]
    column_diff: dict[str, Any] = field(default_factory=dict)
    cell_diffs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "matches": self.matches,
            "row_counts": list(self.row_counts),
            "column_diff": self.column_diff,
            "cell_diffs": self.cell_diffs[:25],
            "cell_diff_count": len(self.cell_diffs),
        }


def read_alteryx_csv(path: Path) -> pd.DataFrame:
    """Read a CSV written by Alteryx DbFileOutput (ISO-8859-1 + BOM + CRLF)."""
    raw = path.read_bytes()
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "iso-8859-1"
    try:
        return pd.read_csv(
            path,
            dtype=object,
            keep_default_na=False,
            encoding=encoding,
            engine="python",
        )
    except UnicodeDecodeError:
        return pd.read_csv(
            path,
            dtype=object,
            keep_default_na=False,
            encoding="iso-8859-1",
            engine="python",
        )


def _is_null(value: object) -> bool:
    if value is None:
        return True
    try:
        import pandas as pd

        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _cell_equal(native: object, python: object) -> bool:
    native_null, python_null = _is_null(native), _is_null(python)
    if native_null or python_null:
        return native_null and python_null
    a = str(native)
    b = str(python)
    if a == b:
        return True
    if any(
        isinstance(value, str)
        and (value != value.strip() or re.match(r"^[+-]?0\d", value))
        for value in (native, python)
    ):
        return False
    try:
        fa, fb = float(a), float(b)
    except ValueError:
        return False
    if fa == fb:
        return True
    scale = max(abs(fa), abs(fb), 1.0)
    return abs(fa - fb) / scale < 1e-9


def compare_frames(native: pd.DataFrame, python: pd.DataFrame) -> FrameComparison:
    column_diff: dict[str, Any] = {}
    native_cols = list(native.columns)
    python_cols = list(python.columns)
    if native_cols != python_cols:
        column_diff = {
            "native": native_cols,
            "python": python_cols,
            "missing_in_python": [c for c in native_cols if c not in python_cols],
            "extra_in_python": [c for c in python_cols if c not in native_cols],
        }
        return FrameComparison(
            False, (len(native), len(python)), column_diff=column_diff
        )
    cell_diffs: list[dict[str, Any]] = []
    for row_index in range(max(len(native), len(python))):
        native_row = native.iloc[row_index] if row_index < len(native) else None
        python_row = python.iloc[row_index] if row_index < len(python) else None
        for column in native_cols:
            a = native_row[column] if native_row is not None else None
            b = python_row[column] if python_row is not None else None
            if not _cell_equal(a, b):
                cell_diffs.append(
                    {
                        "row": row_index,
                        "column": column,
                        "native": None if a is None else str(a),
                        "python": None if b is None else str(b),
                    }
                )
    matches = len(native) == len(python) and not cell_diffs
    return FrameComparison(matches, (len(native), len(python)), cell_diffs=cell_diffs)


def read_python_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=object, keep_default_na=False, engine="python")
    frame.columns = [str(col).lstrip("\ufeff").strip() for col in frame.columns]
    return frame


def run_python_workflow(
    yxmd_path: Path, output_node_id: str, python_csv: Path | None = None
) -> pd.DataFrame:
    """Parse a workflow, execute it through the canonical Python runtime, and
    return the frame written by its DbFileOutput node.

    The output node writes an actual CSV (mirroring the native DbFileOutput),
    so both engines are compared through the same file-based sink.
    """
    workflow = XmlWorkflowParser().parse(yxmd_path)
    context = WorkflowContext()
    nodes_by_id = {node.node_id: node for node in workflow.nodes}
    node = nodes_by_id.get(output_node_id)
    if node is None:
        raise RuntimeError(f"unknown output node: {output_node_id}")
    if node.tool_type != "DbFileOutput":
        raise ValueError("CSV comparison requires a DbFileOutput target")
    python_csv = python_csv or yxmd_path.with_name(yxmd_path.stem + "_python.csv")
    normalized = (
        node.config.get("normalized") if isinstance(node.config, dict) else None
    )
    if not isinstance(normalized, dict):
        normalized = {}
    node.config["normalized"] = {**normalized, "file": str(python_csv)}
    for sink in workflow.nodes:
        if sink.tool_type == "DbFileOutput" and sink.node_id != output_node_id:
            sink.config["normalized"] = {
                **sink.config.get("normalized", {}),
                "file": str(
                    python_csv.with_name(f"{python_csv.stem}-node-{sink.node_id}.csv")
                ),
            }
    run_workflow_graph(workflow, context, target_node_ids={output_node_id})
    if not python_csv.exists():
        raise RuntimeError(
            f"python run did not write the expected output: {python_csv}"
        )
    return read_python_csv(python_csv)


def find_output_node(yxmd_path: Path) -> str:
    """Return the tool id of the single DbFileOutput node."""
    workflow = XmlWorkflowParser().parse(yxmd_path)
    output_nodes = [n for n in workflow.nodes if n.tool_type == "DbFileOutput"]
    if len(output_nodes) != 1:
        raise ValueError(
            f"expected exactly one DbFileOutput node, found {len(output_nodes)}"
        )
    return output_nodes[0].node_id


def run_equivalence(
    yxmd_path: Path,
    native_csv: Path | None = None,
    oracle_csv: Path | None = None,
    runner: str = "auto",
    timeout: int = 240,
) -> dict[str, Any]:
    """Execute both engines for one workflow and produce an equivalence report."""
    output_node = find_output_node(yxmd_path)
    report: dict[str, Any] = {
        "workflow": str(yxmd_path),
        "output_node": output_node,
        "runner": runner,
        "proven_scope": "final-csv-only",
        "limitations": [
            "CSV cannot establish original NULL versus empty-string values or intermediate node equivalence"
        ],
    }
    yxmd_path = yxmd_path.resolve()
    if native_csv is None:
        from alteryx2python.tools.dbfileoutput import _resolve_path

        sink = next(
            node
            for node in XmlWorkflowParser().parse(yxmd_path).nodes
            if node.node_id == output_node
        )
        config = sink.config.get("normalized", {})
        native_csv = _resolve_path(
            str(config.get("file", "")).split("|||", 1)[0], config.get("base_dir")
        )
    native_csv = native_csv.resolve()
    native_started = time.time()
    native_preexisting = native_csv.exists()
    native_result = run_native(yxmd_path, native_csv, runner=runner, timeout=timeout)
    explicit_oracle = (
        Path(oracle_csv).read_bytes()
        if oracle_csv is not None and Path(oracle_csv).is_file()
        else None
    )
    artifacts = Path(
        tempfile.mkdtemp(prefix=f"{yxmd_path.stem}-equivalence-", dir=yxmd_path.parent)
    )
    report["native"] = {
        "runner": native_result.runner,
        "ok": native_result.ok,
        "detail": native_result.detail,
        "status": native_result.status,
        "stdout": native_result.stdout,
        "stderr": native_result.stderr,
        "returncode": native_result.returncode,
        "fresh": bool(
            native_result.ok
            and native_csv.exists()
            and native_csv.stat().st_mtime >= native_started
        ),
        "preexisting_before_run": native_preexisting,
    }
    oracle_path = native_csv if report["native"]["fresh"] else oracle_csv
    oracle_snapshot = None
    if oracle_path is not None and Path(oracle_path).is_file():
        oracle_snapshot = artifacts / "oracle.csv"
        oracle_snapshot.write_bytes(Path(oracle_path).read_bytes())
    python_csv = artifacts / "python.csv"
    try:
        python_frame = run_python_workflow(yxmd_path, output_node, python_csv)
        report["python"] = {
            "ok": True,
            "rows": int(len(python_frame.index)),
            "columns": [str(c) for c in python_frame.columns],
            "output": str(python_csv),
        }
    except Exception as exc:  # noqa: BLE001
        report["python"] = {
            "ok": False,
            "error": str(exc),
            "blocked": isinstance(exc, (ImportError, NotImplementedError))
            or isinstance(exc.__cause__, ImportError),
        }
        python_frame = None
    native_fresh = report["native"]["fresh"]
    oracle_path = native_csv if native_result.ok and native_fresh else oracle_csv
    if oracle_path is not None and Path(oracle_path).exists():
        try:
            native_frame = read_alteryx_csv(oracle_snapshot)
        except Exception as exc:  # noqa: BLE001
            report["compare"] = {"status": "oracle-unreadable", "error": str(exc)}
            report["equivalent"] = False
            return report
        if python_frame is None:
            report["compare"] = {"status": "python-failed"}
            report["equivalent"] = False
            return report
        comparison = compare_frames(native_frame, python_frame)
        report["compare"] = {
            "status": "match" if comparison.matches else "mismatch",
            "oracle": str(oracle_path),
            "oracle_snapshot": str(oracle_snapshot),
            "oracle_source": "native-run"
            if native_result.ok and native_fresh
            else "explicit",
            "oracle_provenance": {
                "sha256": hashlib.sha256(oracle_snapshot.read_bytes()).hexdigest(),
                "fresh_native_run": native_fresh,
            },
            **comparison.to_dict(),
        }
        report["equivalent"] = comparison.matches
    else:
        report["compare"] = {
            "status": "no-oracle",
            "reason": "native backend unavailable and no explicit oracle provided",
        }
    if native_result.ok and not native_fresh:
        report["compare"]["status"] = "stale-oracle"
    detail = native_result.detail.lower()
    failed = native_result.status == "failed" and native_result.returncode not in (
        None,
        0,
        1,
    )
    if report.get("equivalent") is None:
        report["equivalent"] = (
            True
            if (
                failed
                and not report["python"]["ok"]
                and not report["python"].get("blocked")
            )
            else None
        )
        if report["equivalent"] is True:
            report["proven_scope"] = "workflow-failure-only"
            report["compare"]["status"] = "both-failed"
    if (
        oracle_csv is not None
        and explicit_oracle is not None
        and Path(oracle_csv).read_bytes() != explicit_oracle
    ):
        report.update(equivalent=None, proven_scope="none")
        report["compare"] = {"status": "oracle-changed-during-python-run"}
    return report


def run_equivalence_suite(
    out_dir: Path,
    presets: list[str] | None = None,
    seed: int = 42,
    rows: int = 40,
    runner: str = "auto",
) -> dict[str, Any]:
    """Generate, run, and compare every requested preset workflow."""
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=False)
    presets = presets or preset_names()
    results: list[dict[str, Any]] = []
    for name in presets:
        yxmd = out_dir / f"{name}.yxmd"
        native_csv = out_dir / f"{name}_native.csv"
        yxmd.write_text(
            render_preset(name, str(native_csv), seed=seed, rows=rows), encoding="utf-8"
        )
        entry = run_equivalence(yxmd, native_csv=native_csv, runner=runner)
        entry["preset"] = name
        results.append(entry)
    equivalent = [r for r in results if r.get("equivalent") is True]
    mismatched = [r for r in results if r.get("equivalent") is False]
    blocked = [r for r in results if r.get("equivalent") is None]
    return {
        "presets": presets,
        "seed": seed,
        "rows": rows,
        "summary": {
            "equivalent": len(equivalent),
            "mismatched": len(mismatched),
            "native_blocked": len(blocked),
        },
        "results": results,
    }


def run_node_equivalence(
    yxmd_path: Path, output_dir: Path, engine: Path | None = None, timeout: int = 240
) -> dict[str, Any]:
    from alteryx2python.parity.runner import write_json

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    report = _run_node_equivalence(yxmd_path, output_dir, engine, timeout)
    write_json(output_dir / "report.json", report)
    return report


def _run_node_equivalence(
    yxmd_path: Path,
    output_dir: Path,
    engine: Path | None = None,
    timeout: int = 240,
) -> dict[str, Any]:
    """Capture and compare every node/anchor using parity instrumentation.

    This is deliberately separate from the legacy final CSV comparison: a
    blocked native run never falls back to a stale CSV and is never reported as
    node equivalence.
    """
    from alteryx2python.parity.runner import (
        capture_python,
        collect_native,
        compare_runs,
        execute_native,
        prepare,
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle = output_dir / "node-evidence"
    try:
        manifest = prepare(Path(yxmd_path), bundle)
    except Exception as exc:  # noqa: BLE001
        return {"status": "blocked", "proven_scope": "none", "reason": str(exc)}
    python = capture_python(Path(yxmd_path))
    from alteryx2python.native_runner import DEFAULT_ENGINE_CMD

    selected_engine = Path(engine) if engine is not None else Path(DEFAULT_ENGINE_CMD)
    if not selected_engine.exists():
        return {
            "status": "blocked",
            "proven_scope": "none",
            "reason": "native engine unavailable",
            "python": python,
            "manifest": manifest,
        }
    native_run = execute_native(bundle, selected_engine, timeout=timeout)
    native = collect_native(bundle)
    if native.get("status") == "blocked":
        return {
            "status": "blocked",
            "proven_scope": "none",
            "native": native,
            "python": python,
            "native_run": native_run,
        }
    comparison = compare_runs(native, python, profile="behavioral")
    from alteryx2python.parity.runner import write_json

    write_json(bundle / "native.json", native)
    write_json(bundle / "comparison.json", comparison)
    report = {
        "status": comparison.get("status", "incomplete"),
        "proven_scope": "node-outputs" if comparison["status"] == "match" else "none",
        "native": native,
        "python": python,
        "comparison": comparison,
        "native_run": native_run,
    }
    write_json(output_dir / "report.json", report)
    return report

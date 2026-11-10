"""Background EngineCmd execution with process-bound diagnostics and freshness.

The undocumented GUI channel is retained only as an explicitly blocked selector.
No Designer window, Task Scheduler entry or user profile is modified.
"""

from __future__ import annotations

import subprocess
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ENGINE_CMD = r"D:\Alteryx\bin\AlteryxEngineCmd.exe"
DEFAULT_GUI_EXE = r"D:\Alteryx\bin\AlteryxGui.exe"
DEFAULT_ENGINE_LOG_DIR = r"D:\Alteryx\bin\log"


@dataclass
class NativeRunResult:
    runner: str
    ok: bool
    detail: str
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    status: str | None = None

    def __post_init__(self):
        if self.status is None:
            self.status = "success" if self.ok else "blocked"


def _latest_engine_error(
    workflow: Path,
    log_dir: str = DEFAULT_ENGINE_LOG_DIR,
    *,
    since: float | None = None,
) -> str | None:
    """Return the newest engine error text that mentions this workflow."""
    log_path = Path(log_dir)
    if not log_path.is_dir():
        return None
    marker = str(workflow)
    try:
        logs = sorted(
            log_path.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True
        )
    except OSError:
        return None
    if since is not None:
        fresh_logs = []
        for log in logs:
            try:
                if log.stat().st_mtime >= since:
                    fresh_logs.append(log)
            except OSError:
                continue
        logs = fresh_logs
    logs = logs[:5]
    for log in logs:
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if marker.lower() not in text.lower():
            continue
        for line in text.splitlines():
            if line.startswith("ErrorText:"):
                return line.split(":", 1)[1].strip()
    return None


class EngineCmdRunner:
    name = "engine-cmd"

    def __init__(self, engine_cmd: str = DEFAULT_ENGINE_CMD) -> None:
        self.engine_cmd = engine_cmd

    def available(self) -> bool:
        return Path(self.engine_cmd).exists()

    def run(
        self, workflow: Path, watch_file: Path, timeout: int = 600
    ) -> NativeRunResult:
        if not self.available():
            return NativeRunResult(
                self.name,
                False,
                f"engine not found: {self.engine_cmd}",
                status="blocked",
            )
        before = None
        if watch_file.exists():
            try:
                stat = watch_file.stat()
                before = (stat.st_mtime_ns, stat.st_size)
            except OSError:
                before = None
        started = time.time()
        try:
            completed = subprocess.run(
                [self.engine_cmd, str(workflow)],
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            return NativeRunResult(
                self.name, False, "engine timed out", status="blocked"
            )
        output = (completed.stdout or "") + (completed.stderr or "")
        # EngineCmd stdout/stderr are bound to this process. Shared Designer log
        # files may contain older runs even when their mtime was just updated.
        engine_error = None
        license_text = (output + " " + (engine_error or "")).lower()
        if any(
            token in license_text
            for token in (
                "is not licensed",
                "license feature",
                "not licensed",
                "license unavailable",
            )
        ):
            detail = engine_error or next(
                (line for line in output.splitlines() if "licens" in line.lower()),
                "engine-cmd is not licensed (API or FlowChartMode)",
            )
            return NativeRunResult(
                self.name,
                False,
                detail,
                stdout=completed.stdout or "",
                stderr=completed.stderr or "",
                returncode=completed.returncode,
                status="blocked",
            )
        errors = [
            line
            for line in output.splitlines()
            if re.match(r"\s*Error(?:\b|:)", line, re.I)
        ]
        fresh_output = False
        if watch_file.exists():
            try:
                after = watch_file.stat()
                fresh_output = after.st_mtime >= started and after.st_size > 0
                if before is not None and (after.st_mtime_ns, after.st_size) == before:
                    fresh_output = False
            except OSError:
                fresh_output = False
        ok = completed.returncode in (0, 1) and not errors and fresh_output
        detail = "completed" if ok else ("; ".join(errors[:3]) or "no output produced")
        status = (
            "success"
            if ok
            else "failed"
            if completed.returncode not in (0, 1) or errors
            else "blocked"
        )
        return NativeRunResult(
            self.name,
            ok,
            detail,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            returncode=completed.returncode,
            status=status,
        )


class DesignerCliRunner:
    """Compatibility selector which cannot start a GUI process."""

    name = "designer-cli"

    def __init__(self, gui_exe: str = DEFAULT_GUI_EXE) -> None:
        self.gui_exe = gui_exe

    def available(self) -> bool:
        return Path(self.gui_exe).exists()

    def run(
        self, workflow: Path, watch_file: Path, timeout: int = 240
    ) -> NativeRunResult:
        # AlteryxGui.exe's file argument is not a documented headless execution
        # interface.  Starting it through a scheduled task can attach to or
        # mutate an existing Designer session, so never claim this is safe.
        return NativeRunResult(
            self.name,
            False,
            "designer-cli is unsupported for guaranteed background execution; use AlteryxEngineCmd.exe",
            status="blocked",
        )


def run_native(
    workflow: Path,
    watch_file: Path,
    runner: str = "auto",
    timeout: int = 240,
) -> NativeRunResult:
    """Use EngineCmd for auto; never fall back to an existing Designer session."""
    if runner not in ("auto", "engine-cmd", "designer-cli"):
        raise ValueError(f"unknown runner: {runner}")
    candidates: list[EngineCmdRunner | DesignerCliRunner] = []
    if runner in ("auto", "engine-cmd"):
        candidates.append(EngineCmdRunner())
    if runner == "designer-cli":
        candidates.append(DesignerCliRunner())
    last = NativeRunResult(runner, False, "no runner attempted")
    for candidate in candidates:
        if not candidate.available():
            last = NativeRunResult(
                candidate.name, False, "backend executable missing", status="blocked"
            )
            continue
        result = candidate.run(workflow, watch_file, timeout=timeout)
        if result.ok:
            return result
        last = result
        if "license" in result.detail.lower():
            return result
    return last

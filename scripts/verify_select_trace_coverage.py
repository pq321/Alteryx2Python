from __future__ import annotations

import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
TARGET_MODULES = [
    ROOT / "alteryx2python" / "tools" / "select.py",
    ROOT / "alteryx2python" / "runtime" / "context.py",
    ROOT / "alteryx2python" / "comparison" / "schema_diff.py",
]


def _cover_name(source_path: Path) -> str:
    relative_path = source_path.relative_to(ROOT).with_suffix("")
    return ".".join(relative_path.parts) + ".cover"


def _assert_no_missing_lines(cover_dir: Path) -> None:
    missing_by_file: list[str] = []
    for source_path in TARGET_MODULES:
        cover_path = cover_dir / _cover_name(source_path)
        if not cover_path.exists():
            missing_by_file.append(f"{source_path.relative_to(ROOT)}: no trace output")
            continue

        missing_lines: list[str] = []
        for line in cover_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if re.match(r"^\s*>>>>>>", line):
                missing_lines.append(line)

        if missing_lines:
            missing_by_file.append(
                f"{source_path.relative_to(ROOT)}: {len(missing_lines)} missing executable lines"
            )

    if missing_by_file:
        details = "\n".join(missing_by_file)
        raise SystemExit(f"Trace coverage check failed:\n{details}")


def main() -> int:
    with TemporaryDirectory(prefix="select-trace-coverage-") as temp_dir:
        cover_dir = Path(temp_dir)
        command = [
            sys.executable,
            "-m",
            "trace",
            "-c",
            "--coverdir",
            str(cover_dir),
            "-m",
            "--module",
            "pytest",
            "-o",
            "addopts=",
            "-q",
        ]
        completed = subprocess.run(command, cwd=str(ROOT), check=False)
        if completed.returncode != 0:
            return int(completed.returncode)

        _assert_no_missing_lines(cover_dir)

    print("Trace coverage verified for Select slice.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
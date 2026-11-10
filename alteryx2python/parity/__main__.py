from __future__ import annotations

import argparse
import json
from pathlib import Path

from .coverage import coverage_report, refresh_inventory
from .runner import (
    capture_python,
    collect_native,
    compare_runs,
    execute_native,
    prepare,
    verify_manifest,
    write_json,
)
from .samples import generate_samples


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local Alteryx/Python per-node differential evidence"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument(
        "--output", type=Path, default=Path("docs/tools/official_inventory.json")
    )
    coverage = commands.add_parser("coverage")
    coverage.add_argument(
        "--inventory", type=Path, default=Path("docs/tools/official_inventory.json")
    )
    coverage.add_argument("--output", type=Path, required=True)
    coverage.add_argument(
        "--require-mapped",
        action="store_true",
        help="Fail if any official identifier is unmapped",
    )
    samples = commands.add_parser("samples")
    samples.add_argument("--output-dir", type=Path, required=True)
    for command in ("prepare", "run"):
        item = commands.add_parser(command)
        item.add_argument("workflow", type=Path)
        item.add_argument("--output-dir", type=Path, required=True)
        if command == "run":
            item.add_argument("--engine", type=Path, required=True)
            item.add_argument("--timeout", type=float, default=120)
    collect = commands.add_parser("collect")
    collect.add_argument("directory", type=Path)
    collect.add_argument("--manual", action="store_true")
    collect.add_argument(
        "--refresh-python",
        action="store_true",
        help="Capture the current runtime against the unchanged source",
    )
    collect.add_argument(
        "--profile", choices=["behavioral", "strict"], default="behavioral"
    )
    attest = commands.add_parser(
        "attest", help="Record the native Designer outcome you observed"
    )
    attest.add_argument("directory", type=Path)
    attest.add_argument("--status", choices=["success", "failed"], required=True)
    attest.add_argument("--failed-node", action="append", default=[])
    attest.add_argument("--reviewer", default="manual")
    attest.add_argument("--note", default="")
    review = commands.add_parser(
        "review-bundle",
        help="Generate corresponding Python and a manual checkpoint checklist",
    )
    review.add_argument("workflow", type=Path)
    review.add_argument("--output-dir", type=Path, required=True)
    review_check = commands.add_parser(
        "review-check",
        help="Validate filled review.json against captured Python results",
    )
    review_check.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command in {"attest", "review-bundle", "review-check"}:
            from .manual import attest_native, create_review_bundle, check_review_bundle

            if args.command == "attest":
                result = attest_native(
                    args.directory,
                    args.status,
                    failed_nodes=args.failed_node,
                    reviewer=args.reviewer,
                    note=args.note,
                )
            elif args.command == "review-bundle":
                result = create_review_bundle(args.workflow, args.output_dir)
            else:
                result = check_review_bundle(args.directory)
            print(json.dumps(result, ensure_ascii=False))
            return (
                1
                if args.command == "review-check" and result["status"] != "match"
                else 0
            )
        if args.command == "inventory":
            result = refresh_inventory(args.output)
            print(
                json.dumps({"tools": len(result["tools"]), "output": str(args.output)})
            )
            return 0
        if args.command == "coverage":
            report = coverage_report(
                json.loads(args.inventory.read_text(encoding="utf-8"))
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_json(args.output, report)
            print(
                json.dumps(
                    {key: value for key, value in report.items() if key != "tools"}
                )
            )
            return 1 if args.require_mapped and report["missing_rows"] else 0
        if args.command == "samples":
            print(json.dumps([str(path) for path in generate_samples(args.output_dir)]))
            return 0
        if args.command in {"prepare", "run"}:
            prepare(args.workflow, args.output_dir)
            if args.command == "prepare":
                print(
                    json.dumps(
                        {
                            "status": "prepared",
                            "workflow": str(args.output_dir / "instrumented.yxmd"),
                        }
                    )
                )
                return 0
            execute_native(args.output_dir, args.engine, args.timeout)
            directory = args.output_dir
        else:
            directory = args.directory
            if args.refresh_python:
                manifest = verify_manifest(directory)
                write_json(
                    directory / "python.json", capture_python(Path(manifest["source"]))
                )
        native = collect_native(directory, manual=getattr(args, "manual", False))
        write_json(directory / "native.json", native)
        python = json.loads((directory / "python.json").read_text(encoding="utf-8"))
        report = compare_runs(
            native, python, profile=getattr(args, "profile", "behavioral")
        )
        write_json(directory / "comparison.json", report)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "issues": report["issues"],
                    "report": str(directory / "comparison.json"),
                }
            )
        )
        return 0 if report["status"] == "match" else 1
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

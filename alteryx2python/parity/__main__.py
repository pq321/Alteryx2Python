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
    instrumented_path,
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
    sample_kind = samples.add_mutually_exclusive_group()
    sample_kind.add_argument("--container-macro", action="store_true", help="Generate enabled and disabled nested-macro cases")
    sample_kind.add_argument("--control-log", action="store_true", help="Generate a Control Container log and trigger case")
    sample_kind.add_argument("--variable-events", action="store_true", help="Generate a case for variable binding and command events")
    sample_kind.add_argument("--fuzzy-keys", action="store_true", help="Generate Fuzzy Match key and pair cases")
    for command in ("prepare", "run"):
        item = commands.add_parser(command)
        item.add_argument("workflow", type=Path)
        item.add_argument("--output-dir", type=Path, required=True)
        item.add_argument("--answers", type=Path, help="JSON object of analytic-app answers")
        item.add_argument("--allow-event-command", action="append", default=[])
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
    attest.add_argument("--skipped-node", action="append", default=[])
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
    replay = commands.add_parser("replay-macro", help="Replay a macro with attested native boundary inputs")
    replay.add_argument("directory", type=Path)
    replay.add_argument("caller_id")
    replay.add_argument("--output-dir", type=Path, required=True)
    delivery = commands.add_parser("verify-delivery", help="Verify generated Python against a prepared native workflow")
    delivery.add_argument("directory", type=Path)
    delivery.add_argument("--output-dir", type=Path, required=True)
    demo = commands.add_parser("prepare-record-id-demo", help="Prepare the installed Record ID sample and its CSV delivery")
    demo.add_argument("sample", type=Path)
    demo.add_argument("--output-dir", type=Path, required=True)
    amp_export = commands.add_parser("prepare-amp-export", help="Prepare a Designer workflow to export AMP probes as classic YXDB")
    amp_export.add_argument("directories", nargs="+", type=Path)
    scope = commands.add_parser("phase-one-scope", help="Report the selected palette and runtime profiles")
    scope.add_argument("--output", type=Path, required=True)
    scope.add_argument("--samples", type=Path, help="Scan an installed Designer sample directory for configured fixtures")
    matrix = commands.add_parser("phase-one-plan", help="Prepare installed Designer examples for the selected palette")
    matrix.add_argument("--samples", type=Path, required=True)
    matrix.add_argument("--output-dir", type=Path, required=True)
    matrix.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare-record-id-demo":
            from .delivery import prepare_record_id_demo

            print(json.dumps(prepare_record_id_demo(args.sample, args.output_dir), ensure_ascii=False))
            return 0
        if args.command == "verify-delivery":
            from .delivery import verify_delivery

            result = verify_delivery(args.directory, args.output_dir)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["status"] == "match" else 1
        if args.command == "prepare-amp-export":
            from .amp_export import prepare_amp_export

            print(json.dumps([prepare_amp_export(directory) for directory in args.directories], ensure_ascii=False))
            return 0
        if args.command == "phase-one-plan":
            from .matrix import prepare_sample_matrix

            if args.limit is not None and args.limit < 1:
                raise ValueError("Sample limit must be positive")
            summary = prepare_sample_matrix(args.samples, args.output_dir.resolve(), limit=args.limit)
            print(json.dumps(summary, ensure_ascii=False))
            return 0 if summary["ready"] else 1
        if args.command == "phase-one-scope":
            from .scope import phase_one_scope

            report = phase_one_scope(args.samples)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_json(args.output, report)
            print(json.dumps({"tool_count": report["tool_count"], "output": str(args.output)}))
            return 0
        if args.command == "replay-macro":
            from .macro_replay import prepare_macro_replay

            result = prepare_macro_replay(args.directory, args.caller_id, args.output_dir)
            print(json.dumps(result, ensure_ascii=False))
            return 0 if result["status"] == "match" else 1
        if args.command in {"attest", "review-bundle", "review-check"}:
            from .manual import attest_native, create_review_bundle, check_review_bundle

            if args.command == "attest":
                result = attest_native(
                    args.directory,
                    args.status,
                    failed_nodes=args.failed_node,
                    skipped_nodes=args.skipped_node,
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
            generator = generate_samples
            if args.control_log:
                from .samples import generate_control_log_sample

                generator = generate_control_log_sample
            elif args.container_macro:
                from .samples import generate_container_macro_samples

                generator = generate_container_macro_samples
            elif args.variable_events:
                from .samples import generate_variable_event_sample

                generator = generate_variable_event_sample
            elif args.fuzzy_keys:
                from .samples import generate_fuzzy_key_samples

                generator = generate_fuzzy_key_samples
            print(json.dumps([str(path) for path in generator(args.output_dir)]))
            return 0
        if args.command in {"prepare", "run"}:
            answers = json.loads(args.answers.read_text(encoding="utf-8-sig")) if args.answers else None
            if args.answers and not isinstance(answers, dict):
                raise ValueError("App answers must be a JSON object")
            manifest = prepare(
                args.workflow, args.output_dir, answers=answers, event_commands=tuple(args.allow_event_command)
            )
            if args.command == "prepare":
                print(
                    json.dumps(
                        {
                            "status": "prepared",
                            "workflow": str(instrumented_path(args.output_dir, manifest)),
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
                    directory / "python.json",
                    capture_python(
                        Path(manifest["source"]), answers=manifest.get("answers"),
                        event_commands=tuple(manifest.get("event_commands_sha256", {})),
                        log_event_ids=manifest.get("log_event_ids", ()),
                    ),
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

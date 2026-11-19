"""Trace filesystem failures to a workflow tool when a tool owns the path."""

import json
import sys


def format_path_issue(issue):
    labels = []
    for consumer in issue.get("consumers", ()):
        label = consumer["tool"]
        if consumer.get("node_id"):
            label += f' (Tool ID {consumer["node_id"]})'
        if consumer.get("field"):
            label += f' [field {consumer["field"]}]'
        if consumer.get("question"):
            label += f' [{consumer["question"]}]'
        labels.append(label)
    owner = f' for {", ".join(labels)}' if labels else ""
    message = f'{issue["operation"]}{owner}: {issue["path"]} ({issue["reason"]})'
    if issue.get("source") and issue["source"] != issue["path"]:
        message += f'; original input: {issue["source"]}'
    return message


class PathAccessError(OSError):
    def __init__(self, operation, path, reason, *, consumers=(), source=None):
        self.issue = {
            "severity": "error", "operation": operation, "path": str(path),
            "reason": str(reason), "consumers": list(consumers),
        }
        if source is not None:
            self.issue["source"] = str(source)
        super().__init__(format_path_issue(self.issue))


def record_path_issue(directory, issue):
    report = directory / "path-issues.json"
    try:
        issues = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else []
        if issue not in issues:
            report.write_text(json.dumps([*issues, issue], ensure_ascii=False, indent=2), encoding="utf-8")
    except (OSError, ValueError) as error:
        print(f"{format_path_issue(issue)}\nCould not write path diagnostics: {report} ({error})", file=sys.stderr)

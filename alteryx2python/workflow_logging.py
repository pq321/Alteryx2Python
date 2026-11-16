"""Structured records for explicitly migrated workflow logging events."""

from datetime import datetime, timezone
import csv
import io
import json
import logging
import os
import socket
from uuid import uuid4


def configure_workflow_logging(path, columns_path=None):
    """Configure the CLI logger. A CSV projection appends rows without a header."""
    if columns_path is not None and path is None:
        raise ValueError("--workflow-log-columns requires --workflow-log")
    columns = json.loads(columns_path.read_text(encoding="utf-8-sig")) if columns_path else None
    fields = {
        "run_id", "workflow", "event_id", "started_at", "finished_at", "status", "server",
        "user", "computer_name", "working_dir", "warning_count", "error_count",
        "conversion_error_count", "error_type", "error",
    }
    if columns_path and (
        not isinstance(columns, list) or not columns
        or any(not isinstance(key, str) or key not in fields for key in columns)
        or len(columns) != len(set(columns))
    ):
        raise ValueError("Workflow log columns must be a nonempty JSON array of distinct record field names")

    class CsvFormatter(logging.Formatter):
        def format(self, record):
            payload = json.loads(record.getMessage())
            stream = io.StringIO(newline="")
            csv.writer(stream).writerow(payload[key] for key in columns)
            return stream.getvalue().removesuffix("\r\n")

    logger = logging.getLogger("alteryx.workflow")
    handler = logging.FileHandler(path, encoding="utf-8") if path else logging.StreamHandler()
    handler.setFormatter(CsvFormatter() if columns is not None else logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def start_workflow_log():
    return str(uuid4()), datetime.now(timezone.utc).isoformat()


def emit_workflow_log(run, workflow, event_id, working_dir, warning_count, error_count, error=None):
    run_id, started_at = run
    payload = {
        "run_id": run_id,
        "workflow": workflow,
        "event_id": event_id,
        "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": "failed" if error is not None else "success",
        "server": os.environ.get("ALTERYX_LOG_SERVER"),
        "user": os.environ.get("USERNAME") or os.environ.get("USER"),
        "computer_name": socket.gethostname(),
        "working_dir": str(working_dir),
        "warning_count": warning_count,
        "error_count": error_count,
        "conversion_error_count": None,
        "error_type": type(error).__name__ if error is not None else None,
        "error": str(error) if error is not None else None,
    }
    logger = logging.getLogger("alteryx.workflow")
    logger.log(logging.ERROR if error is not None else logging.INFO, json.dumps(payload, ensure_ascii=False))

"""Structured records for explicitly migrated workflow logging events."""

from datetime import datetime, timezone
import json
import logging
import os
import socket
from uuid import uuid4


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

from __future__ import annotations

from alteryx2python.ir.models import WorkflowIR


def validate_workflow_ir_shape(workflow: WorkflowIR) -> list[str]:
    errors: list[str] = []
    if not workflow.workflow_id:
        errors.append("workflow_id is required")
    if not workflow.workflow_name:
        errors.append("workflow_name is required")
    if not workflow.source_file:
        errors.append("source_file is required")
    if not workflow.parser_version:
        errors.append("parser_version is required")
    if not workflow.migration_spec_version:
        errors.append("migration_spec_version is required")
    return errors
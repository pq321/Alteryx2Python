"""Backward-compatible schema helpers."""

from alteryx2python.comparison.schema_diff import SchemaSnapshot, ensure_fields_exist, snapshot_schema

__all__ = ["SchemaSnapshot", "ensure_fields_exist", "snapshot_schema"]
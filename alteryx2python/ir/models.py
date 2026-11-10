from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class AnchorIR:
    name: str
    direction: str


@dataclass(slots=True)
class NodeIR:
    node_id: str
    source_tool_id: str
    tool_type: str
    tool_name: str
    config: dict[str, Any]
    input_anchors: list[AnchorIR] = field(default_factory=list)
    output_anchors: list[AnchorIR] = field(default_factory=list)
    incoming_edges: list[str] = field(default_factory=list)
    outgoing_edges: list[str] = field(default_factory=list)
    expected_input_schema: dict[str, Any] = field(default_factory=dict)
    expected_output_schema: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_semantics_version: str = "0.1.0"
    supported_status: str = "L1_PARSED_ONLY"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class EdgeIR:
    edge_id: str
    source_node_id: str
    source_anchor: str
    target_node_id: str
    target_anchor: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowIR:
    workflow_id: str
    workflow_name: str
    source_file: str
    source_hash: str
    parser_version: str
    migration_spec_version: str
    nodes: list[NodeIR] = field(default_factory=list)
    edges: list[EdgeIR] = field(default_factory=list)
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    macros: list[str] = field(default_factory=list)
    external_dependencies: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    classification: str = "CLASS_D_PARTIAL_MIGRATION_ONLY"
    source_xml: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

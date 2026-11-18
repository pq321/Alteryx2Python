"""Explicit file bindings for migrated Input Data nodes."""

from pathlib import PureWindowsPath


STAGEABLE_INPUT_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx", ".yxdb"}


def parse_input_bindings(values):
    bindings = {}
    for value in values:
        node_id, marker, path = value.partition("=")
        if not marker or not node_id.isdigit() or not path or node_id in bindings:
            raise ValueError("--bind-input requires a distinct NODE_ID=PATH for each input")
        bindings[node_id] = path
    return bindings


def apply_input_bindings(workflow, bindings):
    nodes = {node.node_id: node for node in workflow.nodes}
    for node_id, replacement in bindings.items():
        node = nodes.get(node_id)
        if node is None or node.tool_type != "DbFileInput":
            raise ValueError(f"Input binding target {node_id} is not an Input Data node")
        settings = node.config.get("normalized", node.config)
        old_path, marker, old_selector = str(settings.get("file", "")).partition("|||")
        new_path, separator, _ = replacement.partition("|||")
        suffix = PureWindowsPath(new_path).suffix.lower()
        if not suffix or suffix != PureWindowsPath(old_path).suffix.lower():
            raise ValueError(f"Input binding at node {node_id} changes the configured file format")
        settings["file"] = replacement if separator else new_path + marker + old_selector
        settings["explicit_input_binding"] = True

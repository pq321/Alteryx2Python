from __future__ import annotations

from collections import defaultdict, deque

from alteryx2python.ir.models import WorkflowIR


def validate_unique_node_ids(workflow: WorkflowIR) -> list[str]:
    seen: set[str] = set()
    errors: list[str] = []
    for node in workflow.nodes:
        if node.node_id in seen:
            errors.append(f"Duplicate node_id: {node.node_id}")
        seen.add(node.node_id)
    return errors


def validate_edge_references(workflow: WorkflowIR) -> list[str]:
    node_ids = {node.node_id for node in workflow.nodes}
    errors: list[str] = []
    for edge in workflow.edges:
        if edge.source_node_id not in node_ids:
            errors.append(f"Unknown source node: {edge.source_node_id}")
        if edge.target_node_id not in node_ids:
            errors.append(f"Unknown target node: {edge.target_node_id}")
    return errors


def validate_anchor_references(workflow: WorkflowIR) -> list[str]:
    anchors_by_node = {
        node.node_id: {
            "inputs": {anchor.name for anchor in node.input_anchors},
            "outputs": {anchor.name for anchor in node.output_anchors},
        }
        for node in workflow.nodes
    }
    errors: list[str] = []
    for edge in workflow.edges:
        source = anchors_by_node.get(edge.source_node_id)
        target = anchors_by_node.get(edge.target_node_id)
        if source and edge.source_anchor not in source["outputs"]:
            errors.append(f"Unknown source anchor {edge.source_anchor} on node {edge.source_node_id}")
        if target and edge.target_anchor not in target["inputs"]:
            errors.append(f"Unknown target anchor {edge.target_anchor} on node {edge.target_node_id}")
    return errors


def validate_acyclic_graph(workflow: WorkflowIR) -> list[str]:
    indegree: dict[str, int] = {node.node_id: 0 for node in workflow.nodes}
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in workflow.edges:
        adjacency[edge.source_node_id].append(edge.target_node_id)
        indegree[edge.target_node_id] = indegree.get(edge.target_node_id, 0) + 1

    queue = deque(node_id for node_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        node_id = queue.popleft()
        visited += 1
        for target_id in adjacency.get(node_id, []):
            indegree[target_id] -= 1
            if indegree[target_id] == 0:
                queue.append(target_id)

    if visited != len(indegree):
        return ["Workflow graph contains a cycle or unresolved dependency"]
    return []


def validate_workflow_ir(workflow: WorkflowIR) -> list[str]:
    return [
        *validate_unique_node_ids(workflow),
        *validate_edge_references(workflow),
        *validate_anchor_references(workflow),
        *validate_acyclic_graph(workflow),
    ]
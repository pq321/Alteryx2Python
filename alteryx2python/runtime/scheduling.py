"""Ordering constraints for buffered branches and nested control containers."""
from __future__ import annotations


def scheduling_dependencies(nodes, edges):
    by_id = {node.node_id: node for node in nodes}
    pairs = {(edge.source_node_id, edge.target_node_id) for edge in edges}
    outgoing = {}
    for edge in edges:
        outgoing.setdefault(edge.source_node_id, []).append(edge)

    for node in nodes:
        if node.tool_type != 'ControlContainer':
            continue
        children = set(node.config.get('child_node_ids', [])) & by_id.keys()
        pending = list(children)
        while pending:
            member = by_id[pending.pop()]
            nested = (set(member.config.get('child_node_ids', [])) & by_id.keys()) - children
            children |= nested
            pending.extend(nested)
        triggers = [edge.source_node_id for edge in edges if edge.target_node_id == node.node_id and edge.target_anchor == 'Control']
        pairs.update((trigger, child) for trigger in triggers for child in children)
        pairs.update((child, node.node_id) for child in children)
    dependency_targets = {}
    for source, target in pairs:
        dependency_targets.setdefault(source, []).append(target)

    def descendants(start):
        found, pending = set(), [start]
        while pending:
            current = pending.pop()
            if current in found:
                continue
            found.add(current)
            pending.extend(dependency_targets.get(current, []))
        return found

    for node in nodes:
        parallel = node.metadata.get('ordered_macro_outputs')
        if node.tool_type == 'BlockUntilDone' or parallel:
            anchors = list(parallel) if parallel else ['Output', 'Output2', 'Output3']
            branches = []
            for anchor in anchors:
                branch = set()
                for edge in outgoing.get(node.node_id, []):
                    if edge.source_anchor == anchor:
                        branch |= descendants(edge.target_node_id)
                branches.append(branch)
            for index, branch in enumerate(branches):
                others = set().union(*(branches[:index] + branches[index + 1:]))
                exclusive = branch - others
                for next_branch in branches[index + 1:]:
                    later = next_branch - set().union(*branches[:index + 1])
                    pairs.update((before, after) for before in exclusive for after in later if before != after)
    return pairs


def container_guards(node, by_id, edges):
    guards = []
    parent = node.config.get('container_id')
    seen = set()
    while parent:
        if parent in seen or parent not in by_id:
            raise ValueError('Invalid container hierarchy')
        seen.add(parent)
        container = by_id[parent]
        config = container.config.get('normalized', container.config)
        if config.get('disabled'):
            guards.append(None)
        if container.tool_type == 'ControlContainer':
            guards.extend((edge.source_node_id, edge.source_anchor) for edge in edges
                          if edge.target_node_id == parent and edge.target_anchor == 'Control')
        parent = container.config.get('container_id')
    return guards

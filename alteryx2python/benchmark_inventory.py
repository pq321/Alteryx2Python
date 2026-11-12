"""Independent official-tool inventory and non-executing template probes."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from alteryx2python.generator.readable import ReadablePythonGenerator
from alteryx2python.ir.models import AnchorIR, EdgeIR, NodeIR, WorkflowIR
from alteryx2python.parity.coverage import coverage_report
from alteryx2python.parser.tool_catalog import CATALOG
from alteryx2python.parser.xml_parser import XmlWorkflowParser


def _probe_workflow(original, node):
    """Probe source linking only; synthetic inputs never count as execution proof."""
    target = deepcopy(node)
    target.config.pop('container_id', None)
    target.config.pop('child_node_ids', None)
    nodes, edges = [target], []
    incoming = [edge for edge in original.edges if edge.target_node_id == node.node_id]
    for index, anchor in enumerate(dict.fromkeys(edge.target_anchor for edge in incoming)):
        source_id = 'probe_' + str(index)
        nodes.append(NodeIR(source_id, source_id, 'TextInput', 'probe_input',
            {'fields': ['__compile_probe__'], 'rows': []}, output_anchors=[AnchorIR('Output', 'output')]))
        edges.append(EdgeIR('probe_edge_' + str(index), source_id, 'Output', target.node_id, anchor))
    # Outer questions/actions do not describe this isolated configuration.
    return WorkflowIR(original.workflow_id, original.workflow_name, original.source_file,
        original.source_hash, original.parser_version, original.migration_spec_version,
        nodes=nodes, edges=edges, metadata=deepcopy(original.metadata))


def build_inventory(destination, samples_root, acceptance_source=None):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    inventory_path = Path(__file__).resolve().parent.parent / 'docs/tools/official_inventory.json'
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    report = coverage_report(inventory)
    parser, cases, parse_errors = XmlWorkflowParser(), {}, []
    roots = [samples_root] if isinstance(samples_root, (str, Path)) else list(samples_root)
    roots = [Path(root).resolve() for root in roots]
    paths = sorted({path.resolve() for root in roots
                    for path in ([root] if root.is_file() else root.rglob('*'))
                    if path.is_file() and path.suffix.lower() in {'.yxmd', '.yxwz', '.yxmc'}})
    for path in paths:
        try:
            workflow = parser.parse(path)
        except Exception as exc:
            parse_errors.append({'path': str(path), 'reason': str(exc)})
            continue
        for node in workflow.nodes:
            cases.setdefault(node.tool_type, []).append((workflow, node))
    accepted = {}
    if acceptance_source:
        proof = json.loads(Path(acceptance_source).read_text(encoding='utf-8'))
        if proof.get('status') != 'python_match':
            raise ValueError('Acceptance report does not record a successful differential run')
        accepted = {item['tool_type']: item for item in proof['nodes'] if item['status'] == 'match'}
    fixtures = destination / 'cases'
    fixtures.mkdir()
    probes = {}
    for row in report['tools']:
        kind = row['tool_type']
        candidates = cases.get(kind, [])
        row['sample_present'] = bool(candidates)
        row['sample_node_count'] = len(candidates)
        row['python_differential'] = 'match' if kind in accepted else 'unverified'
        row['native_equivalence'] = 'unverified'
        row['template_compile'] = 'blocked'
        if not candidates:
            row['blocker'] = 'No configured native sample in the supplied corpus; a real fixture is required'
            row['gap_kind'] = 'external_prerequisite' if not row['implemented'] else 'missing_fixture'
            continue
        if kind not in probes:
            attempts = []
            seen = set()
            selected = None
            for workflow, node in sorted(candidates, key=lambda case: len(repr(case[1].config))):
                signature = repr(node.config.get('normalized', node.config))
                if signature in seen:
                    continue
                seen.add(signature)
                fixture = _probe_workflow(workflow, node)
                attempt = {'source_file': workflow.source_file, 'node_id': node.node_id}
                try:
                    ReadablePythonGenerator().generate(fixture, delivery_profile='html-draft-v1')
                except Exception as exc:
                    attempt.update(status='blocked', blocker=str(exc))
                else:
                    attempt.update(status='compiled', blocker=None)
                    selected = (workflow, node, fixture)
                attempts.append(attempt)
                if selected:
                    break
            if selected is None:
                workflow, node = candidates[0]
                selected = (workflow, node, _probe_workflow(workflow, node))
            probes[kind] = (selected, attempts)
        (workflow, node, fixture), attempts = probes[kind]
        row['configuration_probes'] = attempts
        row['template_compile'] = attempts[-1]['status']
        row['blocker'] = attempts[-1]['blocker']
        row['gap_kind'] = (None if row['template_compile'] == 'compiled' else
                           'external_prerequisite' if not row['implemented'] else 'unsupported_configuration')
        row['sample_file'] = workflow.source_file
        row['source_sha256'] = workflow.source_hash
        row['sample_node_id'] = node.node_id
        name = hashlib.sha256(row['plugin_id'].encode()).hexdigest()[:16] + '.ir.json'
        (fixtures / name).write_text(json.dumps(asdict(fixture), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        row['fixture'] = 'cases/' + name
    from collections import Counter
    report.update(format_version=2, samples_scanned=len(paths), sample_roots=[str(root) for root in roots],
        missing_sample_roots=[str(root) for root in roots if not root.exists()], parse_errors=parse_errors,
        gap_counts=dict(Counter(row['gap_kind'] for row in report['tools'] if row['gap_kind'])),
        official_inventory_sha256=hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        compiled_rows=sum(row['template_compile'] == 'compiled' for row in report['tools']),
        sample_rows=sum(row['sample_present'] for row in report['tools']),
        python_differential_rows=sum(row['python_differential'] == 'match' for row in report['tools']),
        native_verified_rows=0, fully_covered=False,
        probe_scope='Configured-node source-linking until one configuration compiles per tool type. Other configurations remain unverified. Probe inputs are synthetic and never executed.',
        local_tool_types=len({item.tool_type for item in CATALOG}))
    (destination / 'coverage.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    lines = ['# Missing component mappings', '',
             'This report covers the pinned official inventory. A compiled probe is not an executed or native-equivalent tool.', '',
             'Interface tools require connected question/Action/target fixtures. Static macros require their source; batch and iterative native compilation remain separate contracts.', '',
             '| Tool | XML identifier | Gap | Blocker |', '| --- | --- | --- | --- |']
    for row in report['tools']:
        if not row['gap_kind']:
            continue
        reason = row['blocker'] or ''
        try:
            detail = json.loads(reason)
            reason = '; '.join(item['reason'] for item in detail.get('nodes', [])) or reason
        except (ValueError, TypeError):
            pass
        cells = [row['name'], row['plugin_id'], row['gap_kind'], ' '.join(reason.split())]
        lines.append('| ' + ' | '.join(str(cell).replace('|', '\\|') for cell in cells) + ' |')
    (destination / 'missing-components.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    return {key: value for key, value in report.items() if key != 'tools'}

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
    paths = sorted(Path(samples_root).rglob('*.yxmd')) + sorted(Path(samples_root).rglob('*.yxwz'))
    for path in paths:
        try:
            workflow = parser.parse(path)
        except Exception as exc:
            parse_errors.append({'path': str(path), 'reason': str(exc)})
            continue
        for node in workflow.nodes:
            if node.tool_type not in cases or len(repr(node.config)) < len(repr(cases[node.tool_type][1].config)):
                cases[node.tool_type] = (workflow, node)
    accepted = {}
    if acceptance_source:
        proof = json.loads(Path(acceptance_source).read_text(encoding='utf-8'))
        if proof.get('status') != 'python_match':
            raise ValueError('Acceptance report does not record a successful differential run')
        accepted = {item['tool_type']: item for item in proof['nodes'] if item['status'] == 'match'}
    fixtures = destination / 'cases'
    fixtures.mkdir()
    for row in report['tools']:
        kind = row['tool_type']
        case = cases.get(kind)
        row['sample_present'] = case is not None
        row['python_differential'] = 'match' if kind in accepted else 'unverified'
        row['native_equivalence'] = 'unverified'
        row['template_compile'] = 'blocked'
        if case is None:
            row['blocker'] = 'No configured native sample in the supplied corpus; a real fixture is required'
            continue
        workflow, node = case
        row['sample_file'] = workflow.source_file
        row['source_sha256'] = workflow.source_hash
        row['sample_node_id'] = node.node_id
        fixture = _probe_workflow(workflow, node)
        name = hashlib.sha256(row['plugin_id'].encode()).hexdigest()[:16] + '.ir.json'
        (fixtures / name).write_text(json.dumps(asdict(fixture), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        row['fixture'] = 'cases/' + name
        try:
            ReadablePythonGenerator().generate(fixture, delivery_profile='html-draft-v1')
        except Exception as exc:
            row['blocker'] = str(exc)
        else:
            row['template_compile'] = 'compiled'
            row['blocker'] = None
    report.update(format_version=1, samples_scanned=len(paths), parse_errors=parse_errors,
        official_inventory_sha256=hashlib.sha256(inventory_path.read_bytes()).hexdigest(),
        compiled_rows=sum(row['template_compile'] == 'compiled' for row in report['tools']),
        sample_rows=sum(row['sample_present'] for row in report['tools']),
        python_differential_rows=sum(row['python_differential'] == 'match' for row in report['tools']),
        native_verified_rows=0, fully_covered=False,
        probe_scope='Configured-node source-linking only. Probe inputs are synthetic and never executed.',
        local_tool_types=len({item.tool_type for item in CATALOG}))
    (destination / 'coverage.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {key: value for key, value in report.items() if key != 'tools'}

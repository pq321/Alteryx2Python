"""Generate a frame-to-frame core with an explicit file adapter."""

import ast
import textwrap
from copy import deepcopy

from .source_linker import UnsupportedLowering
from .parameters import validation_lines


FRAME_TOOLS = {
    'TextInput', 'Select', 'Formula', 'Filter', 'Join', 'Union', 'AppendFields',
    'Summarize', 'Sort', 'Unique', 'RecordID', 'Sample', 'RunningTotal', 'Rank',
    'TextToColumns', 'Transpose', 'AutoField', 'RegEx', 'CrossTab', 'GenerateRows',
    'MultiFieldFormula', 'MultiRowFormula', 'DateTimeNow', 'BrowseV2',
}


def active_transform_graph(workflow):
    """Drop static canvas structure and branches that cannot execute."""
    from alteryx2python.runtime.scheduling import container_guards

    graph = deepcopy(workflow)
    by_id = {node.node_id: node for node in graph.nodes}
    if any(node.metadata.get('disabled_parameter') for node in graph.nodes):
        raise UnsupportedLowering('A container is enabled by an App answer. A conditional I/O adapter is required')
    omitted = {node.node_id for node in graph.nodes
               if node.tool_type in {'ToolContainer', 'TextBox', 'HtmlBox'}
               or None in container_guards(node, by_id, ())}
    for edge in graph.edges:
        if edge.source_node_id in omitted and edge.target_node_id not in omitted:
            raise UnsupportedLowering(f'An inactive branch feeds active node {edge.target_node_id}')
    graph.nodes = [node for node in graph.nodes if node.node_id not in omitted]
    graph.edges = [edge for edge in graph.edges if edge.target_node_id not in omitted]
    for node in graph.nodes:
        if node.config.get('container_id') in omitted:
            node.config.pop('container_id')
    return graph, sorted(omitted)


def validate_runtime_variables(unbound, bound):
    """A file's location can vary. Variable-dependent parser options and rules need their own argument."""
    from alteryx2python.runtime.executor import _normalized_config

    for before, after in zip(unbound.nodes, bound.nodes):
        original, resolved = _normalized_config(before), _normalized_config(after)
        if before.tool_type in {'DbFileInput', 'DbFileOutput'}:
            original = {**original, 'file': str(original.get('file', '')).partition('|||')[2]}
            resolved = {**resolved, 'file': str(resolved.get('file', '')).partition('|||')[2]}
        if original != resolved:
            raise UnsupportedLowering(f'Workflow variables need explicit arguments in {before.tool_type} (node {before.node_id})')


class ReusablePipeline:
    def __init__(self, workflow, omitted):
        from alteryx2python.workflow_events import workflow_events

        if workflow_events(workflow.source_xml):
            raise UnsupportedLowering('Reusable delivery requires an explicit adapter for workflow events')
        self.reads, self.writes = [], []
        self.sources, self.sinks = {}, {}
        self.needs_clock = False
        self.omitted = omitted
        for node in workflow.nodes:
            kind, node_id = node.tool_type, node.node_id
            if kind == 'DbFileInput':
                self.sources[node_id] = {'parameter': f'input_file_{node_id}'}
            elif kind == 'DbFileOutput':
                self.sinks[node_id] = {'parameter': f'output_file_{node_id}'}
            elif kind not in FRAME_TOOLS:
                raise UnsupportedLowering(f'Reusable delivery needs a transform boundary for {kind} (node {node_id})')
        if not self.sinks:
            raise UnsupportedLowering('Reusable delivery requires a file sink to identify returned frames')

    @property
    def reserved_names(self):
        return {entry['parameter'] for entry in (*self.sources.values(), *self.sinks.values())}

    def bind_io(self, config, node_id, runtime_arguments):
        if node_id in self.sources:
            entry = self.sources[node_id]
            question = config.get('_file_parameter')
            if question:
                entry['parameter'] = question
            config['_input_path_parameter'] = entry['parameter']
            runtime_arguments[:] = [entry['parameter']]
        elif node_id in self.sinks:
            if config.get('_file_parameter'):
                raise UnsupportedLowering('An App Action changes the file sink. An output adapter is required')
            parameter = self.sinks[node_id]['parameter']
            config['_output_path_parameter'] = parameter
            runtime_arguments[:] = [parameter]

    def validate_order(self, order):
        stages = [0 if node_id in self.sources else 2 if node_id in self.sinks else 1 for node_id in order]
        if stages != sorted(stages):
            raise UnsupportedLowering('File I/O interleaves with transformations. Moving it would change execution order')

    def partition(self, node_id, calls, start, input_vars, node_vars):
        if node_id in self.sources:
            self.sources[node_id]['frame'] = node_vars[0]
            self.reads.extend(calls[start:])
        elif node_id in self.sinks:
            self.sinks[node_id]['frame'] = input_vars['Input']
            self.writes.extend(calls[start:])
        else:
            return
        del calls[start:]

    def render(self, calls, parameters, linker):
        frames = [entry['frame'] for entry in self.sources.values()]
        results = list(dict.fromkeys(entry['frame'] for entry in self.sinks.values()))
        body = '\n'.join(calls) + '\n'
        loaded = {node.id for node in ast.walk(ast.parse('def transform():\n' + (body if calls else '    pass\n')))
                  if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
        core_answers = [item for item in parameters if item['python_name'] in loaded]
        core_names = frames + [item['python_name'] for item in core_answers]
        if self.needs_clock:
            core_names.append('as_of')
        signature = ', '.join(core_names + ['checkpoints=None'])
        core = f'def transform(*, {signature}):\n'
        core += '    """Transform supplied frames and return the data for the output files."""\n'
        if not self.needs_clock and 'as_of' in loaded:
            core += '    as_of = None\n'
        if self.needs_clock:
            core += '    if as_of is None:\n        raise ValueError("A run timestamp is required")\n'
        for item in core_answers:
            if item['kind'] == 'NumericUpDown':
                linker.imports.add('import math')
            elif item['kind'] == 'Date':
                linker.imports.add('from datetime import date')
            core += textwrap.indent('\n'.join(validation_lines(item, item['python_name'])), '    ') + '\n'
        core += body + '    return ' + ', '.join(results) + '\n'

        file_names = list(dict.fromkeys(item['parameter'] for item in (*self.sources.values(), *self.sinks.values())))
        adapter_names = list(dict.fromkeys(file_names + [item['python_name'] for item in parameters]))
        if self.needs_clock:
            adapter_names.append('as_of')
        adapter = 'def run_workflow(*, ' + ', '.join(adapter_names + ['checkpoints=None']) + '):\n'
        adapter += '    """Read input files, transform their data, and write the requested outputs."""\n'
        adapter += '\n'.join(self.reads + [
            '    ' + ', '.join(results) + ' = transform('
            + ', '.join(f'{name}={name}' for name in core_names + ['checkpoints']) + ')',
            *self.writes,
        ]) + '\n'
        main = ('if __name__ == "__main__":\n'
                '    import argparse\n'
                '    import json\n'
                '    parser = argparse.ArgumentParser(description="Run the migrated Python workflow")\n'
                '    parser.add_argument("--bindings", type=Path)\n')
        for name in adapter_names:
            main += f'    parser.add_argument("--{name.replace("_", "-")}", default=argparse.SUPPRESS)\n'
        main += ('    supplied = vars(parser.parse_args())\n'
                 '    bindings = supplied.pop("bindings")\n'
                 '    arguments = json.loads(bindings.read_text(encoding="utf-8")) if bindings else {}\n'
                 '    if not isinstance(arguments, dict):\n'
                 '        parser.error("Bindings must contain a JSON object")\n'
                 '    arguments.update(supplied)\n'
                 f'    expected = {adapter_names!r}\n'
                 '    if missing := sorted(set(expected) - arguments.keys()):\n'
                 '        parser.error("Missing runtime values: " + ", ".join(missing))\n'
                 '    if unexpected := sorted(arguments.keys() - set(expected)):\n'
                 '        parser.error("Unknown runtime values: " + ", ".join(unexpected))\n'
                 '    run_workflow(**arguments)\n')
        return '\n\n' + adapter + '\n\n' + core + '\n\n' + main

    def manifest(self):
        return {'inputs': self.sources, 'outputs': self.sinks, 'requires_as_of': self.needs_clock,
                'omitted_nodes': self.omitted}

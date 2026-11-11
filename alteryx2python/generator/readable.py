"""Deterministic phase-two compilation from preserved IR to ordinary Python."""
from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import hashlib
import inspect
import json
import keyword
from pathlib import Path
import re
import textwrap
from xml.etree import ElementTree as ET

from alteryx2python.generator.source_linker import SourceLinker, UnsupportedLowering, strip_annotations, RemoveTracing, simplify_template
from alteryx2python.ir.models import AnchorIR, EdgeIR, NodeIR, WorkflowIR


TEMPLATE_VERSION = 'readable-python/2.0.0'
# Each entry uses the checked-in implementation as a versioned source template.
# Metadata stubs, opaque model wrappers and graph interpreters are deliberately absent.
SOURCE_TEMPLATES = frozenset({
    'TextInput', 'DbFileInput', 'DbFileOutput', 'Select', 'Sort', 'Summarize',
    'Join', 'JoinMultiple', 'Union', 'Unique', 'RecordID', 'Sample', 'TextToColumns',
    'RegEx', 'DateTime', 'Rank', 'RunningTotal', 'Tile', 'CrossTab', 'Transpose',
    'AppendFields', 'AutoField', 'DataCleansing', 'FieldInfo', 'FindReplace',
    'JSONParse', 'XMLParse', 'CountRecords', 'MakeColumns', 'MakeGroup',
})
SPECIAL_TEMPLATES = frozenset({'Formula', 'Filter', 'BlockUntilDone', 'ToolContainer',
    'GenerateRows', 'MultiFieldFormula', 'MultiRowFormula',
    'TextBox', 'HtmlBox', 'BrowseV2', 'RunCommand', 'Email', 'PortfolioComposerText',
    'PortfolioComposerTable', 'PortfolioComposerLayout', 'PortfolioComposerRender',
    'MacroBoundaryInput', 'MacroOutput', 'MacroResult', 'ControlContainer', 'JupyterCode'})


def identifier(value):
    name = re.sub('[^a-zA-Z0-9_]+', '_', str(value)).strip('_').lower() or 'step'
    return 'step_' + name if name[0].isdigit() or keyword.iskeyword(name) else name


def _literal(value):
    return ast.parse(repr(value), mode='eval').body


def workflow_from_dict(value):
    value = deepcopy(value)
    nodes = value.pop('nodes')
    edges = value.pop('edges')
    for node in nodes:
        for key in ('input_anchors', 'output_anchors'):
            node[key] = [AnchorIR(**anchor) for anchor in node.get(key, [])]
    return WorkflowIR(**value, nodes=[NodeIR(**node) for node in nodes], edges=[EdgeIR(**edge) for edge in edges])


def read_phase_one(path):
    """Accept our literal IR assignments only; never execute an input script."""
    tree = ast.parse(Path(path).read_text(encoding='utf-8-sig'))
    values = {}
    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id in {'NODE_DATA', 'EDGE_DATA', 'WORKFLOW_DATA'}:
                    if target.id in values:
                        raise UnsupportedLowering(f'Duplicate phase-one assignment: {target.id}')
                    try:
                        values[target.id] = ast.literal_eval(statement.value)
                    except (ValueError, SyntaxError) as exc:
                        raise UnsupportedLowering('Phase-one IR must contain literal data only') from exc
    if set(values) != {'NODE_DATA', 'EDGE_DATA', 'WORKFLOW_DATA'}:
        raise UnsupportedLowering('Not a recognized phase-one script; preserved IR is required')
    workflow = workflow_from_dict({**values['WORKFLOW_DATA'], 'nodes': values['NODE_DATA'], 'edges': values['EDGE_DATA']})
    from alteryx2python.generator.python_generator import PythonGenerator
    def shape(parsed):
        for statement in parsed.body:
            if isinstance(statement, ast.Assign) and any(isinstance(target, ast.Name) and target.id in values for target in statement.targets):
                statement.value = ast.Constant(None)
        return ast.dump(parsed, include_attributes=False)
    actual = shape(tree)
    if not any(actual == shape(ast.parse(PythonGenerator().generate(workflow, include_main=main))) for main in (False, True)):
        raise UnsupportedLowering('Phase-one Python has manual behavioral edits; export its preserved IR explicitly for review')
    return workflow


class _Specialize(ast.NodeTransformer):
    def __init__(self, config, anchors, overrides=None):
        self.config, self.anchors = config, anchors
        self.overrides = overrides or {}

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            if isinstance(node.value.func.value, ast.Name) and node.value.func.value.id == 'context':
                if node.value.func.attr != 'record_node':
                    raise UnsupportedLowering(f'Observable context effect: {node.value.func.attr}')
                return None
        return self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            if node.func.value.id == 'config' and node.func.attr == 'get' and node.args:
                key = ast.literal_eval(node.args[0])
                if key in self.overrides:
                    return deepcopy(self.overrides[key])
                if key in self.config:
                    return ast.copy_location(_literal(self.config[key]), node)
                return self.visit(node.args[1]) if len(node.args) > 1 else ast.Constant(None)
        return self.generic_visit(node)

    def visit_Subscript(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == 'inputs' and isinstance(node.slice, ast.Constant):
            if node.slice.value in self.anchors:
                return ast.copy_location(ast.Name(self.anchors[node.slice.value], ast.Load()), node)
        return self.generic_visit(node)

    def visit_Name(self, node):
        if node.id == 'config' and isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Dict(keys=[ast.Constant(key) for key in self.config],
                values=[deepcopy(self.overrides[key]) if key in self.overrides else _literal(value)
                        for key, value in self.config.items()]), node)
        if node.id == 'inputs' and isinstance(node.ctx, ast.Load):
            return ast.copy_location(ast.Dict(keys=[ast.Constant(key) for key in self.anchors],
                values=[ast.Name(value, ast.Load()) for value in self.anchors.values()]), node)
        if node.id == 'context':
            return ast.copy_location(ast.Constant(None), node)
        return node

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == 'context':
            raise UnsupportedLowering(f'Operation requires context.{node.attr}')
        return self.generic_visit(node)


class _ReturnFrames(ast.NodeTransformer):
    def __init__(self, outputs):
        self.outputs = outputs
        self.entered = False

    def visit_FunctionDef(self, node):
        if self.entered:
            return node
        self.entered = True
        return self.generic_visit(node)

    def visit_Return(self, node):
        value = node.value or ast.Constant(None)
        node.value = (ast.Subscript(value=value, slice=ast.Constant(self.outputs[0]), ctx=ast.Load()) if len(self.outputs) == 1 else
            ast.Tuple(elts=[ast.Subscript(value=deepcopy(value),slice=ast.Constant(anchor),ctx=ast.Load()) for anchor in self.outputs],ctx=ast.Load()) if self.outputs else ast.Constant(None))
        return node


@dataclass
class ReadableArtifact:
    source: str
    manifest: dict
    workflow: WorkflowIR
    verification_source: str = ''

    def write(self, destination):
        destination = Path(destination)
        paths = [destination, destination.with_suffix('.manifest.json'), destination.with_suffix('.ir.json')]
        if any(path.exists() for path in paths):
            raise FileExistsError('Use a fresh destination; generated output may contain human changes')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(self.source, encoding='utf-8', newline='')
        paths[1].write_text(json.dumps(self.manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        paths[2].write_text(json.dumps(asdict(self.workflow), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
        return paths


class ReadablePythonGenerator:
    def __init__(self):
        self.linker = SourceLinker()
        self.functions = []
        self.mapping = []
        self.profile = None
        self.parameter_expressions = {}
        self.parameters = []
        self.parameter_names = {}

    def expression(self, expression):
        from alteryx2python.generator.parameters import ParameterExpression
        from alteryx2python.expressions.ast import (LiteralExpression, FieldReference, BinaryExpression,
            ConditionalExpression, UnaryExpression, FunctionExpression)
        from alteryx2python.expressions.functions import FUNCTION_REGISTRY
        if isinstance(expression, ParameterExpression):
            return self.parameter_names[expression.name]
        if isinstance(expression, LiteralExpression):
            return repr(expression.value)
        if isinstance(expression, FieldReference):
            return f'row[{expression.name!r}]'
        if isinstance(expression, ConditionalExpression):
            return f'({self.expression(expression.true_value)} if bool({self.expression(expression.condition)}) else {self.expression(expression.false_value)})'
        if isinstance(expression, UnaryExpression) and expression.operator == '!':
            return f'(not bool({self.expression(expression.operand)}))'
        if isinstance(expression, FunctionExpression):
            function = FUNCTION_REGISTRY.get(expression.name.upper())
            if function is None:
                raise UnsupportedLowering(f'Unknown expression function: {expression.name}')
            name = self.linker.function(function)
            return f'{name}(' + ', '.join(self.expression(arg) for arg in expression.args) + ')'
        if isinstance(expression, BinaryExpression):
            left, right = self.expression(expression.left), self.expression(expression.right)
            operator = expression.operator
            if operator in {'AND', 'OR'}:
                return f'(bool({left}) {operator.lower()} bool({right}))'
            if operator == '+':
                self.linker.definitions['_add_nullable'] = ('def _add_nullable(left, right):\n'
                    '    if left is None and isinstance(right, (int, float)):\n        left = 0\n'
                    '    if right is None and isinstance(left, (int, float)):\n        right = 0\n'
                    '    return left + right')
                return f'_add_nullable({left}, {right})'
            if operator in {'>', '>=', '<', '<='}:
                if ((isinstance(expression.left, LiteralExpression) and expression.left.value is None) or
                    (isinstance(expression.right, LiteralExpression) and expression.right.value is None)):
                    return 'False'
                checks = [f'{code} is not None' for part, code in [(expression.left,left),(expression.right,right)]
                          if not isinstance(part, LiteralExpression)]
                return '(' + ' and '.join([*checks, f'{left} {operator} {right}']) + ')'
            if operator in {'=', '==', '!=', '-', '*', '/'}:
                return f'({left} {"==" if operator == "=" else operator} {right})'
        raise UnsupportedLowering(f'Unsupported expression AST: {type(expression).__name__}')

    def _expand_macros(self, workflow, stack=()):
        from alteryx2python.parser.xml_parser import XmlWorkflowParser
        from alteryx2python.runtime.app_config import prepare_workflow
        result = deepcopy(workflow)
        for parent in list(result.nodes):
            if not parent.tool_type.startswith('Macro_'):
                continue
            config = parent.config.get('normalized', parent.config)
            raw = Path(config.get('macro_path', ''))
            candidates = [raw] if raw.is_absolute() else [Path(config.get('base_dir', '.')) / raw, Path('D:/Alteryx/bin/RuntimeData/Macros') / raw]
            embedded = workflow.metadata.get('embedded_macros', {})
            path = next((item.resolve() for item in candidates if item.is_file() or str(item.resolve()) in embedded), None)
            if path is None or str(path) in stack:
                raise UnsupportedLowering(f'Unresolved or recursive macro: {raw}')
            xml = embedded.get(str(path)) or path.read_text(encoding='utf-8-sig')
            root = ET.fromstring(xml)
            from alteryx2python.workflow_events import workflow_events
            if workflow_events(xml):
                raise UnsupportedLowering(f'Macro-local workflow events require a dedicated template: {raw}')
            if root.find('.//BatchMacro') is not None or root.find('.//IterativeMacro') is not None:
                raise UnsupportedLowering(f'Batch/iterative macro needs a dedicated verified template: {raw}')
            answers = dict(config.get('macro_answers', {}))
            values = config.get('Value', [])
            for value in values if isinstance(values, list) else [values]:
                if isinstance(value, dict):
                    attrs = value.get('attributes', value.get('@attributes', {}))
                    if attrs.get('name'):
                        answers[attrs['name']] = value.get('text', value.get('#text', ''))
            child = prepare_workflow(XmlWorkflowParser().parse_xml(xml, path), answers)
            child.metadata['embedded_macros'] = embedded
            child = self._expand_macros(child, (*stack, str(path)))
            names = {node.get('ToolID'): node.findtext('Properties/Configuration/Name', 'Input') for node in root.iter('Node')}
            prefix = parent.node_id + '__'
            incoming = [edge for edge in result.edges if edge.target_node_id == parent.node_id]
            result.edges = [edge for edge in result.edges if edge.target_node_id != parent.node_id]
            outputs = []
            for node in child.nodes:
                original = node.node_id
                node.node_id = prefix + original
                if node.config.get('container_id'):
                    node.config['container_id'] = prefix + node.config['container_id']
                if node.config.get('child_node_ids'):
                    node.config['child_node_ids'] = [prefix + value for value in node.config['child_node_ids']]
                node.metadata['macro_source'] = str(path)
                node.metadata['macro_parent'] = parent.node_id
                if node.tool_type == 'MacroInput':
                    node.tool_type = 'MacroBoundaryInput'
                    matches = [edge for edge in incoming if edge.target_anchor == names[original]]
                    if not matches and len(incoming) == 1:
                        matches = incoming
                    if len(matches) != 1:
                        raise UnsupportedLowering(f'Macro input binding is ambiguous: {path}/{original}')
                    edge = replace(matches[0], target_node_id=node.node_id, target_anchor='Input')
                    result.edges.append(edge)
                elif node.tool_type == 'MacroOutput':
                    name = names[original]
                    outputs.append(name)
                    result.edges.append(EdgeIR(prefix + 'return_' + original, node.node_id, 'Output', parent.node_id, name))
                result.nodes.append(node)
            for edge in child.edges:
                result.edges.append(replace(edge, edge_id=prefix + edge.edge_id,
                    source_node_id=prefix + edge.source_node_id, target_node_id=prefix + edge.target_node_id))
            if not outputs:
                raise UnsupportedLowering(f'Macro has no output: {path}')
            parent.tool_type = 'MacroResult'
            from alteryx2python.generator.macro_sources import ordered_macro_outputs
            ordered = ordered_macro_outputs(root)
            if ordered:
                parent.metadata['ordered_macro_outputs'] = ordered
            parent.output_anchors = [AnchorIR(name, 'output') for name in outputs]
        return result

    def _special_body(self, node, config, arguments, outputs):
        from alteryx2python.expressions.parser import parse_expression
        from alteryx2python.tools import delivery
        kind = node.tool_type
        frame = next(iter(arguments.values()), None)
        if kind == 'GenerateRows':
            from alteryx2python.tools.generaterows import _strip_comments
            field = config.get('update_field_name') if config.get('update_field') else config.get('create_field_name')
            if not field:
                raise UnsupportedLowering('GenerateRows needs a target field')
            initial, condition, loop = [self.expression(parse_expression(_strip_comments(config[key]))) for key in ('expression_init','expression_cond','expression_loop')]
            return [f'seeds = {frame}.to_dict("records")' if frame else 'seeds = [{}]', 'rows = []',
                'for seed in seeds:', '    row = dict(seed)', f'    row[{field!r}] = {initial}',
                f'    while bool({condition}):', '        rows.append(dict(row))',
                '        if len(rows) > 100000:', '            raise RuntimeError("GenerateRows exceeded safety limit of 100000 rows")',
                f'        row[{field!r}] = {loop}', 'return pd.DataFrame(rows)']
        if kind == 'MultiFieldFormula':
            expression = self.expression(parse_expression(config['expression']))
            fields = [str(field) for field in config.get('fields', [])]
            explicit = [field for field in fields if field != '*Unknown']
            lines = [f'output = {frame}.copy()', f'fields = [field for field in {explicit!r} if field in {frame}.columns]']
            if '*Unknown' in fields:
                lines += [f'fields.extend(column for column in {frame}.columns if column not in fields)']
            lines += [f'fields = fields or list({frame}.columns)', 'for field in fields:']
            addon = str(config.get('new_field_add_on', ''))
            target = ('field' if not config.get('copy_output') else f'{addon!r} + field' if str(config.get('new_field_add_on_pos', 'Suffix')).lower() == 'prefix' else f'field + {addon!r}')
            return lines + [f'    output_field = {target}', '    values = []',
                '    for row in output.to_dict("records"):', '        row["_CurrentField_"] = row[field]',
                f'        values.append({expression})', '    output[output_field] = values', 'return output']
        if kind == 'MultiRowFormula':
            from alteryx2python.tools.multirowformula import _target_field, _empty_value_for
            from alteryx2python.expressions.ast import FieldReference
            from dataclasses import fields, is_dataclass
            target = _target_field(config)
            parsed = parse_expression(config['expression'])
            expression = self.expression(parsed)
            groups, dtype = config.get('group_by_fields', []), config.get('create_field_type', '')
            references = {}
            def collect(value):
                if isinstance(value, FieldReference):
                    matched = re.fullmatch(r'Row(-?\d+):(.+)', value.name)
                    if matched and 0 < abs(int(matched[1])) <= int(config.get('num_rows', 1)):
                        references[value.name] = (int(matched[1]), matched[2])
                elif is_dataclass(value):
                    for field in fields(value):
                        collect(getattr(value, field.name))
                elif isinstance(value, list):
                    for item in value:
                        collect(item)
            collect(parsed)
            group_key = f'tuple(row.get(field) for field in {groups!r})' if groups else '()'
            record_key = f'tuple(record.get(field) for field in {groups!r})' if groups else '()'
            lines = [f'rows = {frame}.copy().to_dict("records")']
            if not config.get('update_field'):
                lines += ['for row in rows:', f'    row[{target!r}] = {_empty_value_for(target, target, dtype)!r}']
            lines += ['positions_by_group = {}', 'for index, row in enumerate(rows):',
                f'    positions_by_group.setdefault({group_key}, []).append(index)',
                'for index, record in enumerate(rows):', '    row = dict(record)',
                f'    positions = positions_by_group[{record_key}]', '    position = positions.index(index)']
            for reference, (offset, field) in references.items():
                fallback = '(positions[0] if relative < 0 else positions[-1])' if str(config.get('other_rows', 'Empty')).lower() == 'nearest' else 'None'
                lines += [f'    relative = position + {offset}', f'    neighbor = positions[relative] if 0 <= relative < len(positions) else {fallback}',
                          f'    row[{reference!r}] = {_empty_value_for(field, target, dtype)!r} if neighbor is None else rows[neighbor].get({field!r})']
            conversion = ('bool' if dtype.lower() == 'bool' else 'int' if dtype.lower() in {'byte','int16','int32','int64'} else 'float' if dtype.lower() in {'fixeddecimal','double','float'} else None)
            computed = f'computed if computed is None or pd.isna(computed) else {conversion}(computed)' if conversion else 'computed'
            return lines + ['    try:', f'        computed = {expression}', '    except TypeError:', '        computed = None',
                            f'    record[{target!r}] = {computed}', 'return pd.DataFrame(rows)']
        if kind == 'Formula':
            lines = [f'output = {frame}.copy()']
            for index, field in enumerate(config.get('formula_fields', [])):
                if field.get('enabled', True):
                    parsed = self.parameter_expressions.get((node.node_id,('formula_fields',index,'expression')), parse_expression(field['expression']))
                    expression = self.expression(parsed)
                    from alteryx2python.expressions.ast import LiteralExpression
                    from alteryx2python.generator.parameters import ParameterExpression
                    values = f'[{expression}] * len(output)' if isinstance(parsed, (LiteralExpression, ParameterExpression)) else f'[{expression} for row in output.to_dict("records")]'
                    lines.append(f'output[{field["field"]!r}] = {values}')
                    if field.get('type'):
                        from alteryx2python.generator.native_fields import coerce, declaration
                        series = f'output[{field["field"]!r}]'
                        lines.append(f'{series} = {coerce(self, series, field["type"], field.get("size"))}')
                        lines.append(declaration(self, 'output', field['field'], field['type'], field.get('size')))
            return lines + ['return output']
        if kind == 'Filter':
            if config.get('unsupported_operator'):
                raise UnsupportedLowering(f"Simple Filter operator requires a template: {config['unsupported_operator']}")
            expression = self.expression(self.parameter_expressions.get((node.node_id,('expression',)), parse_expression(config['expression'])))
            return [f'mask = pd.Series([bool({expression}) for row in {frame}.to_dict("records")], index={frame}.index)',
                    f'return {frame}.loc[mask].copy(), {frame}.loc[~mask].copy()']
        if kind == 'BlockUntilDone':
            return [f'return {frame}.copy(), {frame}.copy(), {frame}.copy()']
        if kind in {'MacroBoundaryInput', 'MacroOutput'}:
            return [f'return {frame}.copy()']
        if kind == 'MacroResult':
            return ['return ' + ', '.join(arguments[anchor] for anchor in outputs)]
        if kind == 'ControlContainer':
            if not outputs:
                return ['return None']
            active = 'False' if config.get('disabled') else (f'len({arguments["Control"]}.index) > 0' if 'Control' in arguments else 'True')
            return [f'return pd.DataFrame({{"Message": [{config.get("caption", "Container completed")!r}]}} if {active} else {{"Message": []}})']
        if kind in {'ToolContainer', 'TextBox', 'HtmlBox', 'BrowseV2'}:
            return ['return None']
        if kind == 'RunCommand':
            function = self.linker.function(delivery.run_checked_command)
            program = config.get('program_name', '')
            return [f'program = {program!r}',
                    'if not Path(program).is_absolute() and (input_dir / program).is_file():',
                    '    program = str((input_dir / program).resolve())',
                    f'return {function}(program, {config.get("arguments", "")!r}, command_working_dir or input_dir / {config.get("working_dir", "")!r}, '
                    f'{frame}, {config.get("input_file", "")!r}, {config.get("output_file", "")!r}, allowed_commands)']
        if kind.startswith('PortfolioComposer') or kind == 'Email':
            if self.profile != delivery.PROFILE:
                raise UnsupportedLowering(f'{kind} requires explicit html-draft-v1 profile; metadata output is not a report')
            if kind == 'PortfolioComposerTable':
                if config.get('grouping_fields') or config.get('table_mode', 'Basic') != 'Basic' or config.get('show_bar_graph'):
                    raise UnsupportedLowering('Only an ungrouped Basic HTML table is supported')
                function = self.linker.function(delivery.report_table)
                return [f'return {function}({frame}, {config.get("table_fields", [])!r}, {config.get("show_header") is not False!r})']
            if kind == 'PortfolioComposerText':
                if config.get('raw_mode') or config.get('rich_text_mode') or config.get('header_mode'):
                    raise UnsupportedLowering('Rich/dynamic report text needs a verified template')
                function = self.linker.function(delivery.report_text)
                return [f'return {function}({config.get("message", "")!r}, {config.get("output_field", "Report")!r})']
            if kind == 'PortfolioComposerLayout':
                if config.get('grouping_fields') or config.get('orientation', '').lower() not in {'', 'vertical'}:
                    raise UnsupportedLowering('Only ungrouped vertical HTML layout is supported')
                function = self.linker.function(delivery.report_layout)
                return [f'return {function}({frame}, {config.get("layout_fields", [])!r})']
            if kind == 'PortfolioComposerRender':
                if config.get('temp_file_type', '').lower() not in {'html', 'htm'} or config.get('batch_mode'):
                    raise UnsupportedLowering('Only non-batched HTML rendering is supported')
                function = self.linker.function(delivery.render_html)
                filename = Path(config.get('output_file') or 'report.html').name
                return [f'{function}({frame}, {config.get("data_field") or "Report"!r}, output_dir / {filename!r})', 'return None']
            if kind == 'Email':
                if config.get('unsupported_options'):
                    raise UnsupportedLowering(f"Email configuration needs a template: {config['unsupported_options']}")
                function = self.linker.function(delivery.draft_email)
                attachments = '[output_dir / name for name in ' + repr([Path(value).name for value in config.get('attachments', [])]) + ']'
                return [f'{function}({frame}, {config.get("from", "")!r}, {config.get("to", "")!r}, {config.get("subject", "")!r}, '
                        f'{config.get("body") or "Report"!r}, {attachments}, output_dir / {"email-" + node.node_id + ".eml"!r})', 'return None']
        raise UnsupportedLowering(f'No deterministic template for {kind}')

    def generate(self, workflow, *, answers=None, delivery_profile=None):
        # Generator instances are reusable without leaking previous helpers/configuration.
        self.__init__()
        self.profile = delivery_profile
        from alteryx2python.generator.parameters import prepare_parameters, ParameterExpression
        from alteryx2python.runtime.executor import _topological_order, _next_input_anchor_name, _edge_connection_name
        from alteryx2python.tools.registry import TOOL_REGISTRY
        original = deepcopy(workflow)
        prepared, self.parameter_expressions, self.parameters = prepare_parameters(workflow, answers)
        reserved_parameters = {'input_dir', 'output_dir', 'allowed_commands', 'event_working_dir', 'command_working_dir',
            'checkpoints', 'config', 'inputs', 'context', 'pd', 'math', 'warnings', 're', 'html', 'os', 'hashlib', 'mimetypes', 'shlex', 'shutil',
            'subprocess', 'argparse', 'bounded_text', 'nullable_integer', 'declare_field', 'workflow_warnings'}
        import builtins
        reserved_parameters.update(dir(builtins))
        for parameter in self.parameters:
            base = identifier(parameter['name'])
            if base in reserved_parameters or base.endswith('_frame'):
                base += '_input'
            name, suffix = base, 1
            while name in reserved_parameters:
                suffix += 1
                name = f'{base}_{suffix}'
            reserved_parameters.add(name)
            parameter['python_name'] = name
            self.parameter_names[parameter['name']] = name
        workflow = self._expand_macros(prepared)
        by_id = {node.node_id: node for node in workflow.nodes}
        order = _topological_order(workflow.nodes, workflow.edges)
        variables = {}
        used_names = {'run_workflow'}
        calls = []
        issues = []
        for node_id in order:
            node = by_id[node_id]
            config = deepcopy(node.config.get('normalized', node.config))
            config.update(node_id=node_id, source_tool_id=node.source_tool_id,
                          expected_output_schema=node.expected_output_schema)
            arguments, input_vars, connection_names = {}, {}, {}
            for edge in workflow.edges:
                if edge.target_node_id != node_id:
                    continue
                anchor = _next_input_anchor_name(arguments, edge.target_anchor)
                arguments[anchor] = identifier(anchor) + '_frame'
                input_vars[anchor] = variables.get((edge.source_node_id, edge.source_anchor), 'missing_input')
                connection_name = _edge_connection_name(edge)
                if connection_name:
                    connection_names[anchor] = connection_name
            if connection_names:
                config['input_connection_names'] = connection_names
            annotation = node.metadata.get('annotation', {}).get('Name', '')
            if isinstance(annotation, dict):
                annotation = annotation.get('text', '')
            roles = {'DbFileInput': 'load_data', 'TextInput': 'reference_data', 'Select': 'select_fields',
                     'Formula': 'calculate_fields', 'Filter': 'filter_rows', 'Sort': 'sort_rows',
                     'Summarize': 'summarize_rows', 'MacroBoundaryInput': 'macro_input',
                     'MacroOutput': 'macro_output', 'MacroResult': 'macro_result'}
            if node.tool_type == 'Formula':
                fields = [field['field'] for field in config.get('formula_fields', []) if field.get('enabled', True)]
                roles['Formula'] = 'calculate_' + '_and_'.join(fields[:2]) if fields else 'calculate_fields'
            elif node.tool_type == 'Select':
                fields = [field.get('rename') or field['source'] for field in config.get('select_fields', []) if field.get('selected', True) and field.get('source') != '*Unknown']
                roles['Select'] = 'select_' + '_and_'.join(fields[:2]) if fields else 'select_fields'
            elif node.tool_type in {'Sort', 'Rank'}:
                fields = [field['field'] for field in config.get('sort_fields', [])]
                roles[node.tool_type] = node.tool_type.lower() + '_by_' + '_and_'.join(fields[:2])
            elif node.tool_type == 'Summarize':
                fields = [field['field'] for field in config.get('summarize_fields', []) if field.get('action') == 'GroupBy']
                roles['Summarize'] = 'summarize_by_' + '_and_'.join(fields[:2]) if fields else 'summarize_rows'
            base_name = identifier(annotation or roles.get(node.tool_type, node.tool_type))
            name, suffix = '_operation_' + base_name, 1
            while name in used_names:
                suffix += 1
                name = f'_operation_{base_name}_{suffix}'
            used_names.add(name)
            try:
                metadata = TOOL_REGISTRY.get(node.tool_type) if node.tool_type not in {'MacroResult', 'MacroBoundaryInput'} else None
                outputs = tuple(anchor.name for anchor in node.output_anchors) if node.tool_type in {'MacroResult', 'ControlContainer'} else (
                    ('Output',) if node.tool_type == 'MacroBoundaryInput' else metadata.output_anchors)
                runtime_arguments = (['input_dir'] if node.tool_type == 'DbFileInput' else
                    ['input_dir', 'command_working_dir', 'allowed_commands'] if node.tool_type == 'RunCommand' else
                    ['output_dir'] if node.tool_type in {'DbFileOutput', 'Email', 'PortfolioComposerRender'} else [])
                parameter_names = set()
                def collect_parameters(value):
                    from dataclasses import fields, is_dataclass
                    if isinstance(value, ParameterExpression):
                        parameter_names.add(self.parameter_names[value.name])
                    elif is_dataclass(value):
                        for field in fields(value):
                            collect_parameters(getattr(value,field.name))
                    elif isinstance(value,list):
                        for item in value:
                            collect_parameters(item)
                for (parameter_node,_), expression in self.parameter_expressions.items():
                    if parameter_node == node_id:
                        collect_parameters(expression)
                for binding in prepared.metadata.get('parameter_bindings', []):
                    if binding['node_id'] != node_id:
                        continue
                    parameter_name = self.parameter_names[binding['name']]
                    parameter_names.add(parameter_name)
                    if binding['kind'] == 'file':
                        config['_file_parameter'] = parameter_name
                    elif binding['kind'] == 'cell':
                        config.setdefault('_cell_parameters', {})[':'.join(map(str, binding['path'][1:]))] = parameter_name
                runtime_arguments.extend(sorted(parameter_names))
                from alteryx2python.generator.native_io import lower_io
                from alteryx2python.generator.native_tabular import lower_tabular
                from alteryx2python.generator.native_relational import lower_relational
                from alteryx2python.generator.native_reshape import lower_reshape
                if node.tool_type == 'JupyterCode':
                    from alteryx2python.generator.python_tool import lower_python_script
                    body, outputs = lower_python_script(config.get('production_mode_script', ''), arguments, prepared.metadata.get('workflow_constants'))
                else:
                    body = lower_io(node.tool_type, config, next(iter(arguments.values()), None), self)
                if body is None:
                    body = lower_tabular(self, node.tool_type, config, next(iter(arguments.values()), None))
                if body is None:
                    body = lower_relational(self, node.tool_type, config, arguments)
                if body is None:
                    body = lower_reshape(self, node.tool_type, config, next(iter(arguments.values()), None))
                if body is not None:
                    parameters = ', '.join(arguments.values())
                    signature = parameters + ((', ' if parameters else '') + '*, ' + ', '.join(runtime_arguments) if runtime_arguments else '')
                    self.functions.append(f'def {name}({signature}):\n' + textwrap.indent('\n'.join(body), '    '))
                    template_hash = hashlib.sha256((inspect.getsource(lower_io) + inspect.getsource(lower_tabular) + inspect.getsource(lower_relational) + inspect.getsource(lower_reshape)).encode()).hexdigest()
                elif node.tool_type in SOURCE_TEMPLATES or (metadata is not None and node.tool_type not in SPECIAL_TEMPLATES and metadata.execution_profile != 'unavailable'):
                    function = inspect.unwrap(metadata.function)
                    if function.__module__.endswith(('.baseline', '.unavailable', '.reporting')):
                        raise UnsupportedLowering('Metadata/passthrough implementation is not an executable template')
                    source = textwrap.dedent(inspect.getsource(function))
                    tree = strip_annotations(ast.parse(source).body[0])
                    tree.name, tree.decorator_list = name, []
                    tree.args = ast.arguments(posonlyargs=[], args=[ast.arg(value) for value in arguments.values()],
                        kwonlyargs=[ast.arg(value) for value in runtime_arguments],
                        kw_defaults=[None for value in runtime_arguments], defaults=[], vararg=None, kwarg=None)
                    overrides = {}
                    if node.tool_type in {'DbFileInput', 'DbFileOutput'}:
                        overrides['base_dir'] = ast.parse('str(input_dir)' if node.tool_type == 'DbFileInput' else 'str(output_dir)', mode='eval').body
                        raw_file = str(config.get('file', ''))
                        path, separator, selector = raw_file.partition('|||')
                        if node.tool_type == 'DbFileOutput':
                            expression = f'str(output_dir / {Path(path).name!r})'
                            if separator:
                                expression += f' + {separator + selector!r}'
                            overrides['file'] = ast.parse(expression, mode='eval').body
                        elif Path(path).is_absolute():
                            try:
                                relative = Path(path).relative_to(Path(config.get('base_dir', '.')))
                            except ValueError as exc:
                                raise UnsupportedLowering('External absolute input requires an explicit portable binding') from exc
                            overrides['file'] = ast.Constant(relative.as_posix() + (separator + selector if separator else ''))
                    tree = RemoveTracing().visit(tree)
                    tree = _Specialize(config, arguments, overrides).visit(tree)
                    # Return ordinary dataframes/tuples rather than runtime anchor objects.
                    tree = _ReturnFrames(outputs).visit(tree)
                    tree = simplify_template(tree)
                    import warnings
                    namespace = {**function.__globals__, **inspect.getclosurevars(function).nonlocals, 'warnings':warnings}
                    tree = self.linker.bind_globals(tree, namespace)
                    self.functions.append(ast.unparse(ast.fix_missing_locations(tree)))
                    template_hash = hashlib.sha256(source.encode()).hexdigest()
                else:
                    body = self._special_body(node, config, arguments, outputs)
                    parameters = ', '.join(arguments.values())
                    signature = parameters + ((', ' if parameters else '') + '*, ' + ', '.join(runtime_arguments) if runtime_arguments else '')
                    self.functions.append(f'def {name}({signature}):\n' + textwrap.indent('\n'.join(body), '    '))
                    template_hash = hashlib.sha256(inspect.getsource(type(self)._special_body).encode()).hexdigest()
                variable_name = name.removeprefix('_operation_')
                node_vars = [variable_name + (('' if variable_name.endswith('_data') else '_data') if len(outputs) == 1 else '_' + {'True': 'matched', 'False': 'unmatched'}.get(anchor, identifier(anchor))) for anchor in outputs]
                node_vars = [variable + '_result' if variable in reserved_parameters else variable for variable in node_vars]
                for anchor, variable in zip(outputs, node_vars):
                    variables[node_id, anchor] = variable
                args = ', '.join(input_vars.values())
                kwargs = ', '.join(f'{value}={value}' for value in runtime_arguments)
                call = f'{name}(' + ', '.join(value for value in [args, kwargs] if value) + ')'
                calls.append('    # ' + node.tool_type + ' / source node ' + node_id)
                from alteryx2python.runtime.scheduling import container_guards
                guards = container_guards(node, by_id, workflow.edges)
                if guards:
                    condition = ' and '.join('False' if guard is None else f'len({variables[guard]}.index) > 0' for guard in guards)
                    calls.append('    if ' + condition + ':')
                    calls.append('        ' + (', '.join(node_vars) + ' = ' if node_vars else '') + call)
                    if node_vars:
                        calls.append('    else:')
                        empty = next(iter(input_vars.values()), None)
                        if node.tool_type == 'Select' and empty:
                            empty_args = ', '.join(f'{value}.iloc[:0].copy()' for value in input_vars.values())
                            calls.append('        ' + ', '.join(node_vars) + ' = ' + name + '(' + empty_args + ')')
                        else:
                            from alteryx2python.generator.native_fields import empty_frame
                            for variable in node_vars:
                                calls.extend('        ' + line for line in empty_frame(self, node.tool_type, config, empty, node.expected_output_schema, variable))
                else:
                    calls.append('    ' + (', '.join(node_vars) + ' = ' if node_vars else '') + call)
                checkpoint = '{' + ', '.join(f'{anchor!r}: {variable}.copy()' for anchor, variable in zip(outputs, node_vars)) + '}'
                calls.extend(['    if checkpoints is not None:', f'        checkpoints[{node_id!r}] = {checkpoint}'])
                self.mapping.append({'node_id': node_id, 'source_tool_id': node.source_tool_id,
                    'tool_type': node.tool_type, 'function': name, 'template_sha256': template_hash,
                    'inputs': dict(input_vars), 'variables': dict(zip(outputs, node_vars)),
                    'template_version': TEMPLATE_VERSION, 'outputs': list(outputs), 'config_sha256': hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()})
            except (UnsupportedLowering, KeyError, ValueError) as exc:
                issues.append({'node_id': node_id, 'tool_type': node.tool_type, 'reason': str(exc)})
        if issues:
            error = UnsupportedLowering(json.dumps({'status': 'blocked', 'nodes': issues}, indent=2))
            error.issues = issues
            raise error
        self.linker.imports.add('from pathlib import Path')
        header = '"""Editable Python generated with deterministic templates. See the sidecar manifest."""\n'
        parameter_signature = ''.join(f', {item["python_name"]}={item["default"]!r}' for item in self.parameters)
        pipeline = '\n\ndef run_workflow(*, input_dir=None, output_dir=None, allowed_commands=(), event_working_dir=None, command_working_dir=None, checkpoints=None' + parameter_signature + '):\n'
        pipeline += '    input_dir = Path(input_dir or Path(__file__).resolve().parent).resolve()\n'
        pipeline += '    output_dir = Path(output_dir or Path(__file__).resolve().parent / "output").resolve()\n'
        pipeline += '    output_dir.mkdir(parents=True, exist_ok=True)\n'
        for item in self.parameters:
            name = item['python_name']
            from alteryx2python.generator.parameters import validation_lines
            if item['kind'] == 'NumericUpDown':
                self.linker.imports.add('import math')
            elif item['kind'] == 'Date':
                self.linker.imports.add('from datetime import date')
            pipeline += textwrap.indent('\n'.join(validation_lines(item, name)), '    ') + '\n'
        from alteryx2python.workflow_events import workflow_events
        from alteryx2python.tools.delivery import run_checked_command
        events = workflow_events(original.source_xml)
        if events:
            command = self.linker.function(run_checked_command)
            def event_calls(timings, success=False):
                result = []
                for event in events:
                    timing = event['when']
                    condition = ('bool(workflow_warnings)' if timing in {'warnings', 'failure_or_warnings'} else
                                 'not workflow_warnings' if timing == 'clean_success' else None)
                    if timing not in timings and not (success and condition):
                        continue
                    call = f'{command}(' + (repr(event['program']) if Path(event['program']).is_absolute() else f'(str(input_dir / {event["program"]!r}) if (input_dir / {event["program"]!r}).is_file() else {event["program"]!r})') + f', {event["arguments"]!r}, event_working_dir or input_dir / {event["working_dir"]!r}, None, "", "", allowed_commands, {event["timeout"]!r})'
                    result.append(('if ' + condition + ':\n    ' if condition and timing not in timings else '') + call)
                return result
            self.linker.imports.add('import warnings')
            pipeline += '    try:\n'
            pipeline += '        with warnings.catch_warnings(record=True) as workflow_warnings:\n'
            pipeline += '            warnings.simplefilter("always", RuntimeWarning)\n'
            pipeline += textwrap.indent('\n'.join(event_calls({'before'})), '            ') + '\n'
            pipeline += textwrap.indent('\n'.join(calls), '        ') + '\n'
            pipeline += '    except Exception:\n'
            pipeline += textwrap.indent('\n'.join(event_calls({'failure', 'after', 'failure_or_warnings'}) + ['raise']), '        ') + '\n'
            pipeline += '    else:\n'
            pipeline += textwrap.indent('\n'.join(event_calls({'success', 'after'}, success=True) + ['pass']), '        ') + '\n'
        else:
            pipeline += '\n'.join(calls) + '\n'
        pipeline += '    return output_dir\n'
        main = ('\n\nif __name__ == "__main__":\n    import argparse\n'
            '    parser = argparse.ArgumentParser(description="Run the migrated Python workflow")\n'
            '    parser.add_argument("--input-dir", type=Path)\n'
            '    parser.add_argument("--output-dir", type=Path)\n'
            '    parser.add_argument("--event-working-dir", type=Path)\n'
            '    parser.add_argument("--command-working-dir", type=Path)\n'
            '    parser.add_argument("--allow-command", action="append", default=[])\n'
            + ''.join(f'    parser.add_argument("--{item["python_name"].replace("_","-")}", type={"float" if item["kind"] == "NumericUpDown" else "str"}, default={item["default"]!r})\n' for item in self.parameters)
            + '    args = parser.parse_args()\n'
            + '    print(run_workflow(input_dir=args.input_dir, output_dir=args.output_dir, event_working_dir=args.event_working_dir, command_working_dir=args.command_working_dir, allowed_commands=args.allow_command'
            + ''.join(f', {item["python_name"]}=args.{item["python_name"]}' for item in self.parameters) + '))\n')
        source = header + self.linker.render() + '\n\n' + '\n\n'.join(self.functions) + pipeline + main
        from alteryx2python.generator.business_source import assemble
        source, verification_source = assemble(source, self.mapping)
        parsed_source = ast.parse(source)
        from alteryx2python.generator.business_source import validate_business_source
        validate_business_source(parsed_source)
        for item in ast.walk(parsed_source):
            modules = [item.module or ''] if isinstance(item, ast.ImportFrom) else [alias.name for alias in item.names] if isinstance(item, ast.Import) else []
            if any(module.startswith(('alteryx2python', 'alteryx_runtime')) for module in modules):
                raise UnsupportedLowering('A project dependency remained in generated Python')
        forbidden = ('run_workflow_graph', 'WorkflowContext', 'NODE_DATA', 'EDGE_DATA', 'evaluate_expression', 'parse_expression')
        if any(token in source for token in forbidden):
            raise UnsupportedLowering('Opaque runtime or expression interpreter remained in generated source')
        lines = source.splitlines()
        for item in self.mapping:
            item['line'] = next(index + 1 for index, line in enumerate(lines) if line.startswith('def ' + item['function'] + '('))
        manifest = {'format_version': 1, 'template_version': TEMPLATE_VERSION,
            'workflow_id': original.workflow_id, 'source_sha256': original.source_hash,
            'generated_sha256': hashlib.sha256(source.encode()).hexdigest(),
            'delivery_profile': delivery_profile, 'bound_answers': answers or {},
            'native_equivalence': 'unverified', 'python_differential': 'unverified',
            'helper_sha256': self.linker.digests, 'nodes': self.mapping}
        manifest['events'] = events
        manifest['parameters'] = self.parameters
        manifest['verification_sha256'] = hashlib.sha256(verification_source.encode()).hexdigest()
        manifest['compiler_sha256'] = {name:hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                                       for name in ('readable.py','source_linker.py','parameters.py', 'native_io.py', 'native_tabular.py', 'native_relational.py', 'native_reshape.py', 'native_fields.py', 'business_source.py', 'partial_eval.py', 'python_tool.py')}
        package = Path(__file__).resolve().parents[1]
        compiler_paths = {Path(__file__).with_name(name).resolve() for name in manifest['compiler_sha256']}
        manifest['semantic_sha256'] = {path.relative_to(package).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                                       for path in sorted(package.rglob('*.py')) if path.resolve() not in compiler_paths}
        from alteryx2python.tools.field_contracts import DEFAULT_SIZES, INTEGER_BYTES, STRING_TYPES
        from alteryx2python.tools.rank import RANK_METHODS
        manifest['semantic_constants'] = {'field_default_sizes': dict(DEFAULT_SIZES), 'integer_bytes': dict(INTEGER_BYTES),
                                          'string_types': sorted(STRING_TYPES), 'rank_methods': dict(RANK_METHODS)}
        import pandas as pd
        import platform
        manifest['compiler_environment'] = {'python': platform.python_version(), 'pandas': pd.__version__}
        return ReadableArtifact(source, manifest, original, verification_source)

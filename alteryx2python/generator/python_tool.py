"""Lower Python Tool boundary APIs without interpreting the configured program."""
from __future__ import annotations

import ast

from alteryx2python.generator.source_linker import UnsupportedLowering


def output_anchor(number):
    if isinstance(number, bool) or not isinstance(number, int) or not 1 <= number <= 5:
        raise UnsupportedLowering('Python Tool output must be a literal number from 1 to 5')
    return 'Output' if number == 1 else f'Output{number}'


def lower_python_script(script, inputs, constants=None):
    """Return native statements and output anchors; never execute during compilation."""
    if not script or not str(script).strip():
        raise UnsupportedLowering('Python Tool has no saved production script')
    try:
        tree = ast.parse(script)
    except SyntaxError as exc:
        raise UnsupportedLowering(f'Invalid saved Python Tool script: {exc}') from exc
    aliases, packages = {'Alteryx'}, set()
    for item in ast.walk(tree):
        if isinstance(item, ast.ImportFrom) and item.module == 'ayx':
            for name in item.names:
                if name.name == 'Alteryx':
                    aliases.add(name.asname or name.name)
                else:
                    packages.add(name.asname or name.name)
    reserved = {item.id for item in ast.walk(tree) if isinstance(item, ast.Name)}
    rebound = {item.id for item in ast.walk(tree) if isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del))}
    rebound.update(item.arg for item in ast.walk(tree) if isinstance(item, ast.arg))
    rebound.update(item.name for item in ast.walk(tree) if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)))
    if aliases & rebound:
        raise UnsupportedLowering('Python Tool vendor API aliases must not be rebound')
    if any(isinstance(item, (ast.Global, ast.Nonlocal)) for item in ast.walk(tree)):
        raise UnsupportedLowering('Python Tool global/nonlocal statements need a module isolation template')

    def fresh(base):
        name = base
        while name in reserved:
            name += '_'
        reserved.add(name)
        return name

    pandas = fresh('_python_pandas')
    outputs = {}

    class Boundaries(ast.NodeTransformer):
        depth = 0

        def visit_ImportFrom(self, node):
            if node.module == 'ayx':
                return None
            return node

        def visit_Import(self, node):
            if any(name.name == 'ayx' or name.name.startswith('ayx.') for name in node.names):
                raise UnsupportedLowering('Use an explicit from ayx import Alteryx boundary import')
            return node

        def api(self, node):
            return node.func.attr if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id in aliases else None

        def visit_FunctionDef(self, node):
            self.depth += 1
            try:
                return self.generic_visit(node)
            finally:
                self.depth -= 1

        visit_AsyncFunctionDef = visit_FunctionDef
        visit_Lambda = visit_FunctionDef
        visit_ClassDef = visit_FunctionDef

        def visit_Expr(self, node):
            if self.api(node.value) != 'write':
                return self.generic_visit(node)
            call = node.value
            if self.depth or len(call.args) != 2 or call.keywords:
                raise UnsupportedLowering('Python Tool write requires a top-level statement with dataframe and literal output number')
            if not isinstance(call.args[1], ast.Constant):
                raise UnsupportedLowering('Python Tool write output must be a literal number')
            anchor = output_anchor(call.args[1].value)
            name = outputs.setdefault(anchor, fresh('_python_' + anchor.lower()))
            value = self.visit(call.args[0])
            return ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=ast.Call(func=ast.Attribute(value=value, attr='copy', ctx=ast.Load()), args=[], keywords=[]))

        def visit_Call(self, node):
            method = self.api(node)
            if method is None:
                return self.generic_visit(node)
            if method == 'read' and len(node.args) == 1 and isinstance(node.args[0], ast.Constant) and not node.keywords:
                anchor = str(node.args[0].value)
                if anchor.startswith('#'):
                    number = anchor[1:]
                    anchor = 'Input' if number == '1' else 'Input' + number
                if anchor not in inputs:
                    raise UnsupportedLowering(f'Python Tool input is not connected: {anchor}')
                return ast.parse(inputs[anchor] + '.copy()', mode='eval').body
            if method == 'getIncomingConnectionNames' and not node.args and not node.keywords:
                names = ['#' + ('1' if name == 'Input' else name.removeprefix('Input')) for name in inputs]
                return ast.parse(repr(names), mode='eval').body
            if method == 'getWorkflowConstant' and len(node.args) == 1 and isinstance(node.args[0], ast.Constant) and not node.keywords:
                name = node.args[0].value
                if name not in (constants or {}):
                    raise UnsupportedLowering(f'Python Tool constant is unresolved: {name}')
                return ast.parse(repr(constants[name]), mode='eval').body
            raise UnsupportedLowering(f'Python Tool API requires a native mapping: Alteryx.{method}')

    tree = Boundaries().visit(tree)
    residual = {item.id for item in ast.walk(tree) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load) and item.id in aliases | packages}
    if residual:
        raise UnsupportedLowering('Unmapped Python Tool vendor API: ' + ', '.join(sorted(residual)))
    anchors = sorted(outputs, key=lambda name: 1 if name == 'Output' else int(name[6:]))
    prefix = [ast.Import(names=[ast.alias(name='pandas', asname=pandas)])]
    prefix += [ast.Assign(targets=[ast.Name(id=outputs[name], ctx=ast.Store())], value=ast.Constant(None)) for name in anchors]
    checks = [ast.parse(f'if not isinstance({outputs[name]}, {pandas}.DataFrame):\n    raise ValueError("Python Tool did not write dataframe to {name}")').body[0] for name in anchors]
    values = [ast.Name(id=outputs[name], ctx=ast.Load()) for name in anchors]
    returned = values[0] if len(values) == 1 else ast.Tuple(elts=values, ctx=ast.Load()) if values else ast.Constant(None)
    tree.body = prefix + tree.body + checks + [ast.Return(value=returned)]
    return ast.unparse(ast.fix_missing_locations(tree)).splitlines(), tuple(anchors)

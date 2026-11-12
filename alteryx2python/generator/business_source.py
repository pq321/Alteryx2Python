"""Assemble native operations into dependency-bounded Python stages.

The compiler keeps capture statements in a verification build. Delivery contains
neither node captures nor their parameters. Both builds share the same AST.
"""
import ast
from copy import deepcopy


def validate_business_source(tree, native_functions=()):
    from alteryx2python.generator.source_linker import UnsupportedLowering
    inspected = ast.Module(body=[item for item in tree.body if not isinstance(item, ast.FunctionDef) or item.name not in native_functions], type_ignores=[])
    residual = {item.id for item in ast.walk(inspected) if isinstance(item, ast.Name)
                and isinstance(item.ctx, ast.Load) and item.id in {'config', 'inputs', 'checkpoints'}}
    if residual:
        raise UnsupportedLowering('A native template is required; runtime configuration/anchor machinery remains: ' + ', '.join(sorted(residual)))


class _Names(ast.NodeTransformer):
    def __init__(self, names):
        self.names = names

    def visit_Name(self, node):
        if node.id in self.names:
            return ast.copy_location(ast.Name(id=self.names[node.id], ctx=node.ctx), node)
        return node


def _checkpoint(statement):
    if not isinstance(statement, ast.If) or not isinstance(statement.test, ast.Compare):
        return None
    if not isinstance(statement.test.left, ast.Name) or statement.test.left.id != 'checkpoints':
        return None
    assignment = statement.body[0]
    return assignment.targets[0].slice.value


def _inline(statement, functions, reserved):
    """Inline only single-exit functions; retain complex lexical scopes intact."""
    if isinstance(statement, ast.If):
        statement.body = [part for item in statement.body for part in _inline(item, functions, reserved)]
        statement.orelse = [part for item in statement.orelse for part in _inline(item, functions, reserved)]
        return [statement]
    value = statement.value if isinstance(statement, (ast.Assign, ast.Expr)) else None
    if not isinstance(value, ast.Call) or not isinstance(value.func, ast.Name) or value.func.id not in functions:
        return [statement]
    function = deepcopy(functions[value.func.id])
    if function.args.defaults or any(default is not None for default in function.args.kw_defaults) or function.args.vararg or function.args.kwarg:
        return [statement]
    if function.args.posonlyargs or any(isinstance(item, ast.ExceptHandler) and item.name for item in ast.walk(function)):
        return [statement]
    returns = [item for item in ast.walk(function) if isinstance(item, ast.Return)]
    if len(returns) != 1 or not isinstance(function.body[-1], ast.Return):
        return [statement]
    if any(isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
                             ast.Yield, ast.YieldFrom, ast.NamedExpr, ast.Global, ast.Nonlocal,
                             ast.Import, ast.ImportFrom, ast.GeneratorExp)) for line in function.body for item in ast.walk(line)):
        return [statement]
    supplied = {arg.arg: item for arg, item in zip(function.args.args, value.args)}
    supplied.update({item.arg: item.value for item in value.keywords})
    names, prefix = {}, []
    local_names = {item.id for item in ast.walk(function) if isinstance(item, ast.Name) and isinstance(item.ctx, (ast.Store, ast.Del))}
    for name in sorted(local_names):
        candidate, count = name, 1
        while candidate in reserved:
            count += 1
            candidate = f'{name}_{count}'
        names[name] = candidate
        reserved.add(candidate)
    for name, argument in supplied.items():
        if isinstance(argument, ast.Name) and name not in local_names:
            names[name] = argument.id
        else:
            candidate, suffix = names.get(name, name), 0
            while name not in names and candidate in reserved:
                suffix += 1
                candidate = name + '_argument' + (str(suffix) if suffix > 1 else '')
            names[name] = candidate
            reserved.add(candidate)
            prefix.append(ast.Assign(targets=[ast.Name(id=candidate, ctx=ast.Store())], value=deepcopy(argument)))
    returned = function.body[-1].value or ast.Constant(None)
    target = statement.targets[0] if isinstance(statement, ast.Assign) else None
    if isinstance(returned, ast.Name) and isinstance(target, ast.Name) and returned.id not in supplied:
        names[returned.id] = target.id
    body = [_Names(names).visit(line) for line in function.body[:-1]]
    returned = _Names(names).visit(returned)
    if target is not None:
        if not (isinstance(returned, ast.Name) and isinstance(target, ast.Name) and returned.id == target.id):
            body.append(ast.Assign(targets=[deepcopy(target)], value=returned))
    elif not isinstance(returned, ast.Constant):
        body.append(ast.Expr(value=returned))
    return prefix + body or [ast.Pass()]


class _Delivery(ast.NodeTransformer):
    def __init__(self, native_functions=()):
        self.native_functions = set(native_functions)

    def visit_FunctionDef(self, node):
        if node.name in self.native_functions:
            return node
        node = self.generic_visit(node)
        # Only the assembler's positional stage argument and run_workflow's
        # keyword-only argument are instrumentation parameters.
        node.args.args = [arg for arg in node.args.args if arg.arg != 'checkpoints']
        pairs = [(arg, default) for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults) if arg.arg != 'checkpoints']
        node.args.kwonlyargs = [arg for arg, _ in pairs]
        node.args.kw_defaults = [default for _, default in pairs]
        return node

    def visit_Call(self, node):
        node = self.generic_visit(node)
        node.keywords = [item for item in node.keywords if item.arg != 'checkpoints']
        return node

    def visit_If(self, node):
        if _checkpoint(node) is not None:
            return None
        node = self.generic_visit(node)
        node.body = node.body or [ast.Pass()]
        return node

    def visit_Pass(self, node):
        return None


def _prune(tree):
    """Keep only definitions reachable from entry points, then only used imports."""
    definitions = {line.name: line for line in tree.body if isinstance(line, (ast.FunctionDef, ast.ClassDef))}
    constants = {target.id: line for line in tree.body if isinstance(line, ast.Assign) for target in line.targets if isinstance(target, ast.Name)}
    roots = [line for line in tree.body if not isinstance(line, (ast.FunctionDef, ast.ClassDef, ast.Assign, ast.Import, ast.ImportFrom))]
    pending = ['run_workflow'] + [item.id for line in roots for item in ast.walk(line) if isinstance(item, ast.Name)]
    reachable = set()
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        line = definitions.get(name, constants.get(name))
        if line is not None:
            pending.extend(item.id for item in ast.walk(line) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load))
    body = []
    for line in tree.body:
        if isinstance(line, (ast.FunctionDef, ast.ClassDef)) and line.name not in reachable:
            continue
        if isinstance(line, ast.Assign) and all(isinstance(target, ast.Name) and target.id not in reachable for target in line.targets):
            continue
        if isinstance(line, (ast.Import, ast.ImportFrom)):
            line.names = [alias for alias in line.names if (alias.asname or alias.name.split('.')[0]) in reachable]
            if not line.names:
                continue
        body.append(line)
    merged, rewritten = {}, []
    for line in body:
        if isinstance(line, ast.ImportFrom):
            key = (line.module, line.level)
            if key in merged:
                existing = {(alias.name, alias.asname) for alias in merged[key].names}
                merged[key].names.extend(alias for alias in line.names if (alias.name, alias.asname) not in existing)
                continue
            merged[key] = line
        rewritten.append(line)
    tree.body = rewritten
    return tree


def assemble(source, mapping, native_functions=()):
    tree = ast.parse(source)
    functions = {line.name: line for line in tree.body if isinstance(line, ast.FunctionDef) and line.name in {item['function'] for item in mapping if item.get('tool_type') != 'JupyterCode'}}
    by_id = {item['node_id']: item for item in mapping}
    variables = {name for item in mapping for name in item['variables'].values()}
    consumers = {name: set() for name in variables}
    for item in mapping:
        for name in item['inputs'].values():
            if name in consumers:
                consumers[name].add(item['node_id'])
    pipeline = next(line for line in tree.body if isinstance(line, ast.FunctionDef) and line.name == 'run_workflow')
    runtime = {arg.arg for arg in pipeline.args.kwonlyargs}
    reserved = variables | runtime | {line.name for line in tree.body if isinstance(line, (ast.FunctionDef, ast.ClassDef))}
    reserved.update(item.id for item in ast.walk(pipeline) if isinstance(item, ast.Name))
    stages = []

    def blocks(statements, owner):
        result = []
        index = 0
        while index < len(statements):
            if index + 1 < len(statements) and (node_id := _checkpoint(statements[index + 1])) is not None:
                chunks = [(statements[index], statements[index + 1], by_id[node_id])]
                index += 2
                while index + 1 < len(statements) and (next_id := _checkpoint(statements[index + 1])) is not None:
                    previous = chunks[-1][2]
                    candidate = by_id[next_id]
                    outputs = list(previous['variables'].values())
                    if isinstance(statements[index], ast.If) or isinstance(chunks[-1][0], ast.If):
                        break
                    if not any(name in candidate['inputs'].values() for name in outputs):
                        break
                    if any(consumers[name] - {next_id} for name in outputs):
                        break
                    chunks.append((statements[index], statements[index + 1], candidate))
                    index += 2
                body = []
                for statement, capture, item in chunks:
                    body.extend(_inline(statement, functions, set(reserved)))
                    body.append(capture)
                complexity = sum(isinstance(part, ast.stmt) for line in body for part in ast.walk(line))
                complex_single = len(chunks) == 1 and complexity > 14 and not isinstance(chunks[0][0], ast.If)
                if len(chunks) == 1 and not complex_single:
                    chunks[0][2]['function'] = owner
                    result.extend(body)
                    continue
                base = chunks[-1][2]['function'].removeprefix('_operation_')
                name = base if complex_single else 'prepare_' + base
                if complex_single:
                    name += '_stage'
                count = 1
                while name in reserved:
                    count += 1
                    name = 'prepare_' + base + '_' + str(count)
                reserved.add(name)
                ids = {item['node_id'] for _, _, item in chunks}
                produced = {name for _, _, item in chunks for name in item['variables'].values()}
                loaded = {item.id for statement, _, _ in chunks for item in ast.walk(statement) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}
                inputs = sorted((loaded & (variables | runtime)) - produced - {'checkpoints'})
                last_outputs = set(chunks[-1][2]['variables'].values())
                outputs = [name for _, _, item in chunks for name in item['variables'].values() if consumers[name] - ids or name in last_outputs]
                returned = ast.Name(id=outputs[0], ctx=ast.Load()) if len(outputs) == 1 else ast.Tuple(elts=[ast.Name(id=name, ctx=ast.Load()) for name in outputs], ctx=ast.Load())
                body.append(ast.Return(value=returned if outputs else ast.Constant(None)))
                stage = ast.FunctionDef(name=name, args=ast.arguments(posonlyargs=[], args=[ast.arg(arg) for arg in inputs], kwonlyargs=[ast.arg('checkpoints')], kw_defaults=[ast.Constant(None)], defaults=[]), body=body, decorator_list=[])
                stages.append(stage)
                call = ast.Call(func=ast.Name(id=name, ctx=ast.Load()), args=[ast.Name(id=arg, ctx=ast.Load()) for arg in inputs], keywords=[ast.keyword(arg='checkpoints', value=ast.Name(id='checkpoints', ctx=ast.Load()))])
                target = ast.Name(id=outputs[0], ctx=ast.Store()) if len(outputs) == 1 else ast.Tuple(elts=[ast.Name(id=arg, ctx=ast.Store()) for arg in outputs], ctx=ast.Store())
                result.append(ast.Assign(targets=[target], value=call) if outputs else ast.Expr(value=call))
                for _, _, item in chunks:
                    item['function'] = name
                continue
            statement = statements[index]
            for attribute in ('body', 'orelse', 'finalbody'):
                if isinstance(getattr(statement, attribute, None), list):
                    setattr(statement, attribute, blocks(getattr(statement, attribute), owner))
            if isinstance(statement, ast.Try):
                for handler in statement.handlers:
                    handler.body = blocks(handler.body, owner)
            result.append(statement)
            index += 1
        return result

    pipeline.body = blocks(pipeline.body, 'run_workflow')
    position = tree.body.index(pipeline)
    tree.body[position:position] = stages
    # Show the orchestration first, followed by stages and their small helpers.
    imports = [line for line in tree.body if isinstance(line, (ast.Import, ast.ImportFrom))]
    other = [line for line in tree.body if line not in imports and line is not pipeline and line not in stages]
    definitions = [line for line in other if isinstance(line, (ast.FunctionDef, ast.ClassDef, ast.Assign))]
    main = [line for line in other if line not in definitions]
    docstrings = [line for line in main if isinstance(line, ast.Expr) and isinstance(line.value, ast.Constant) and isinstance(line.value.value, str)]
    tree.body = docstrings + imports + [pipeline] + stages + definitions + [line for line in main if line not in docstrings]
    class LocalAnnotations(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            class Assignments(ast.NodeTransformer):
                def visit_ClassDef(self, node):
                    return node

                def visit_AnnAssign(self, node):
                    if node.value is not None:
                        return ast.copy_location(ast.Assign(targets=[node.target], value=node.value), node)
                    return node
            node.body = [Assignments().visit(line) for line in node.body]
            return node
    tree = LocalAnnotations().visit(tree)
    verification = ast.unparse(ast.fix_missing_locations(_prune(deepcopy(tree)))) + '\n'
    delivery_tree = _prune(_Delivery(native_functions).visit(tree))
    delivery = ast.unparse(ast.fix_missing_locations(delivery_tree)) + '\n'
    return delivery, verification

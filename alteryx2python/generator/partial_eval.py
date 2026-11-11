"""Conservative, deterministic specialization of operation-template ASTs.

Mutable bindings are snapshots usable for pure reads until an alias or opaque
effect invalidates them. Loops and exception regions remain unspecialized.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import math
import operator


_UNKNOWN = object()
_LIMIT = 16_384
_BINARY = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.LShift: operator.lshift, ast.RShift: operator.rshift,
    ast.BitAnd: operator.and_, ast.BitOr: operator.or_, ast.BitXor: operator.xor,
}
_COMPARE = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
}
_CONVERSIONS = {
    'bool': bool, 'int': int, 'float': float, 'str': str,
    'list': list, 'tuple': tuple, 'dict': dict, 'set': set,
    'len': len, 'abs': abs, 'round': round,
}
_STRING_METHODS = frozenset({
    'lower', 'upper', 'casefold', 'strip', 'lstrip', 'rstrip', 'capitalize',
    'title', 'swapcase', 'startswith', 'endswith', 'removeprefix', 'join',
    'removesuffix', 'replace', 'split', 'rsplit', 'partition', 'rpartition',
    'find', 'rfind', 'index', 'rindex', 'count', 'isalnum', 'isalpha',
    'isascii', 'isdecimal', 'isdigit', 'isidentifier', 'islower', 'isnumeric',
    'isprintable', 'isspace', 'istitle', 'isupper',
})


def _safe(value: object, depth: int = 0, budget: list[int] | None = None) -> bool:
    """Exclude user protocols, cycles, huge results and nonliteral numbers."""
    if budget is None:
        budget = [2048]
    budget[0] -= 1
    if depth > 24 or budget[0] < 0:
        return False
    kind = type(value)
    if value is None or kind is bool:
        return True
    if kind is int:
        return value.bit_length() <= 4096
    if kind is float:
        return math.isfinite(value)
    if kind in (str, bytes):
        return len(value) <= _LIMIT
    if kind in (list, tuple, dict, set) and len(value) <= 256:
        values = (part for pair in value.items() for part in pair) if kind is dict else value
        return all(_safe(part, depth + 1, budget) for part in values)
    return False


def _immutable(value: object) -> bool:
    return type(value) not in (dict, list, set) and (
        type(value) is not tuple or all(_immutable(part) for part in value)
    )


def _same(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is tuple:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    if type(left) is float:
        return left == right and math.copysign(1, left) == math.copysign(1, right)
    return left == right


def _literal(value: object) -> ast.expr:
    if type(value) is tuple:
        return ast.Tuple(elts=[_literal(part) for part in value], ctx=ast.Load())
    return ast.Constant(value=value)


def _fresh_literal(value: object) -> ast.expr | None:
    """Rebuild fresh comprehension containers without duplicating aliases."""
    if type(value) is list and all(_immutable(part) for part in value):
        return ast.List(elts=[_literal(part) for part in value], ctx=ast.Load())
    if type(value) is dict and all(_immutable(part) for part in value.values()):
        return ast.Dict(keys=[_literal(key) for key in value],
                        values=[_literal(part) for part in value.values()])
    return None


def _writes(tree: ast.AST) -> set[str]:
    """Overapproximate writes, including string-valued binders."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            names.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
        elif isinstance(node, ast.alias):
            names.add(node.asname or node.name.split('.')[0])
        elif isinstance(node, (ast.ExceptHandler, ast.MatchAs, ast.MatchStar)) and node.name:
            names.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            names.add(node.rest)
    return names


class _LocalNames(ast.NodeVisitor):
    """Python locals, excluding bindings owned by nested scopes."""

    def __init__(self):
        self.names: set[str] = set()

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.names.add(node.id)

    def visit_FunctionDef(self, node):
        self.names.add(node.name)
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        arguments.extend(arg for arg in (node.args.vararg, node.args.kwarg) if arg is not None)
        for expression in [*node.decorator_list, *node.args.defaults,
                           *node.args.kw_defaults, node.returns,
                           *[arg.annotation for arg in arguments]]:
            if expression is not None:
                self.visit(expression)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.names.add(node.name)
        for expression in [*node.bases, *node.decorator_list, *node.keywords]:
            self.visit(expression)

    def visit_Lambda(self, node):
        for expression in [*node.args.defaults,
                           *[value for value in node.args.kw_defaults if value is not None]]:
            self.visit(expression)

    def visit_ListComp(self, node):
        self.visit(node.generators[0].iter)
        for child in ast.walk(node):
            if isinstance(child, ast.NamedExpr):
                self.visit(child.target)

    visit_SetComp = visit_ListComp
    visit_DictComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp

    def visit_Import(self, node):
        self.names.update(alias.asname or alias.name.split('.')[0] for alias in node.names)

    visit_ImportFrom = visit_Import

    def visit_ExceptHandler(self, node):
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    def visit_MatchAs(self, node):
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node):
        if node.rest:
            self.names.add(node.rest)
        self.generic_visit(node)


def _locals(body: list[ast.stmt]) -> set[str]:
    collector = _LocalNames()
    for statement in body:
        collector.visit(statement)
    return collector.names


def _docstring(body: list[ast.stmt]) -> bool:
    return bool(body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and type(body[0].value.value) is str)


class _Evaluator:
    def __init__(self, bindings, shadowed, local_names=(), captured=()):
        self.env = dict(bindings)
        self.shadowed = shadowed
        self.local_names = set(local_names)
        self.captured = set(captured)

    def invalidate(self, node: ast.AST):
        written = _writes(node)
        self.env = {
            name: value for name, value in self.env.items()
            if name not in written and name in self.local_names
            and name not in self.captured and _immutable(value)
        }

    def value(self, node: ast.AST):
        try:
            value = self._value(node)
            return value if value is not _UNKNOWN and _safe(value) else _UNKNOWN
        except (ArithmeticError, LookupError, TypeError, ValueError, RecursionError):
            # Preserve failing operations so exceptions occur at runtime.
            return _UNKNOWN

    def _value(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            return self.env.get(node.id, _UNKNOWN)
        if isinstance(node, (ast.ListComp, ast.DictComp)):
            return self.comprehension(node)
        if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
            values = [self.value(part) for part in node.elts]
            if any(value is _UNKNOWN for value in values):
                return _UNKNOWN
            return {ast.Tuple: tuple, ast.List: list, ast.Set: set}[type(node)](values)
        if isinstance(node, ast.Dict):
            result = {}
            for key, part in zip(node.keys, node.values):
                key_value, value = self.value(key), self.value(part)
                if key is None or key_value is _UNKNOWN or value is _UNKNOWN:
                    return _UNKNOWN
                result[key_value] = value
            return result
        if isinstance(node, ast.UnaryOp):
            value = self.value(node.operand)
            if value is not _UNKNOWN:
                operation = {ast.Not: operator.not_, ast.USub: operator.neg,
                             ast.UAdd: operator.pos, ast.Invert: operator.invert}.get(type(node.op))
                return operation(value) if operation else _UNKNOWN
        if isinstance(node, ast.BinOp):
            left, right = self.value(node.left), self.value(node.right)
            if left is _UNKNOWN or right is _UNKNOWN:
                return _UNKNOWN
            if isinstance(node.op, ast.Pow):
                if type(right) not in (int, float) or abs(right) > 128:
                    return _UNKNOWN
                if type(left) is int and left.bit_length() * max(1, right) > 4096:
                    return _UNKNOWN
            if isinstance(node.op, (ast.LShift, ast.RShift)) and (
                type(right) is not int or not 0 <= right <= 4096
            ):
                return _UNKNOWN
            if isinstance(node.op, ast.Mult):
                for sequence, count in ((left, right), (right, left)):
                    if type(sequence) in (str, bytes, tuple, list) and type(count) is int:
                        if len(sequence) * max(0, count) > _LIMIT:
                            return _UNKNOWN
            if isinstance(node.op, ast.Mod) and type(left) in (str, bytes):
                return _UNKNOWN
            operation = _BINARY.get(type(node.op))
            return operation(left, right) if operation else _UNKNOWN
        if isinstance(node, ast.BoolOp):
            value = _UNKNOWN
            for part in node.values:
                value = self.value(part)
                if value is _UNKNOWN:
                    return _UNKNOWN
                if isinstance(node.op, ast.And) and not value:
                    break
                if isinstance(node.op, ast.Or) and value:
                    break
            return value
        if isinstance(node, ast.Compare):
            left = self.value(node.left)
            if left is _UNKNOWN:
                return _UNKNOWN
            for operation, part in zip(node.ops, node.comparators):
                right = self.value(part)
                if right is _UNKNOWN:
                    return _UNKNOWN
                if isinstance(operation, (ast.Is, ast.IsNot)):
                    if not isinstance(part, ast.Constant) or not (
                        part.value is None or type(part.value) is bool
                    ):
                        return _UNKNOWN
                    result = left is right
                    if isinstance(operation, ast.IsNot):
                        result = not result
                elif type(operation) in _COMPARE:
                    result = _COMPARE[type(operation)](left, right)
                else:
                    return _UNKNOWN
                if not result:
                    return False
                left = right
            return True
        if isinstance(node, ast.IfExp):
            test = self.value(node.test)
            if test is not _UNKNOWN:
                return self.value(node.body if test else node.orelse)
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load):
            value = self.value(node.value)
            if isinstance(node.slice, ast.Slice):
                parts = [self.value(part) if part is not None else None
                         for part in (node.slice.lower, node.slice.upper, node.slice.step)]
                key = slice(*parts) if all(part is not _UNKNOWN for part in parts) else _UNKNOWN
            else:
                key = self.value(node.slice)
            if value is not _UNKNOWN and key is not _UNKNOWN:
                return value[key]
        if isinstance(node, ast.Call) and not node.keywords:
            args = [self.value(arg) for arg in node.args]
            if any(arg is _UNKNOWN for arg in args):
                return _UNKNOWN
            if isinstance(node.func, ast.Name) and node.func.id not in self.shadowed:
                conversion = _CONVERSIONS.get(node.func.id)
                if conversion is None:
                    return _UNKNOWN
                # Container reprs and unordered iteration are not deterministic.
                if node.func.id == 'str' and any(type(arg) in (dict, list, tuple, set) for arg in args):
                    return _UNKNOWN
                if node.func.id in ('list', 'tuple', 'dict') and any(type(arg) is set for arg in args):
                    return _UNKNOWN
                return conversion(*args)
            if isinstance(node.func, ast.Attribute):
                receiver = self.value(node.func.value)
                if type(receiver) is dict and node.func.attr == 'get' and len(args) in (1, 2):
                    return receiver.get(*args)
                if type(receiver) is str and node.func.attr in _STRING_METHODS:
                    if node.func.attr == 'join':
                        if (len(args) != 1 or type(args[0]) not in (tuple, list)
                                or any(type(part) is not str for part in args[0])):
                            return _UNKNOWN
                        if sum(map(len, args[0])) + len(receiver) * max(0, len(args[0]) - 1) > _LIMIT:
                            return _UNKNOWN
                    if node.func.attr == 'replace' and len(args) >= 2 and type(args[1]) is str:
                        if (len(receiver) + 1) * len(args[1]) > _LIMIT:
                            return _UNKNOWN
                    return getattr(receiver, node.func.attr)(*args)
        return _UNKNOWN

    def comprehension(self, node):
        scope = _Evaluator(self.env, self.shadowed)
        outer_sequence = self.value(node.generators[0].iter)
        # Only the first iterable executes in the enclosing scope. All targets
        # are comprehension locals, including targets of later generators.
        for generator in node.generators:
            for name in _writes(generator.target):
                scope.env.pop(name, None)
        result = {} if isinstance(node, ast.DictComp) else []
        remaining = 256

        def bind(target, value):
            if isinstance(target, ast.Name):
                scope.env[target.id] = value
                return True
            if isinstance(target, (ast.Tuple, ast.List)) and type(value) in (tuple, list, str, bytes):
                return len(target.elts) == len(value) and all(
                    bind(part, item) for part, item in zip(target.elts, value))
            return False

        def collect(index):
            nonlocal remaining
            if index == len(node.generators):
                if isinstance(node, ast.DictComp):
                    key, value = scope.value(node.key), scope.value(node.value)
                    if key is _UNKNOWN or value is _UNKNOWN:
                        return False
                    result[key] = value
                else:
                    value = scope.value(node.elt)
                    if value is _UNKNOWN:
                        return False
                    result.append(value)
                return True
            generator = node.generators[index]
            sequence = outer_sequence if index == 0 else scope.value(generator.iter)
            if generator.is_async or type(sequence) not in (list, tuple, str, bytes, dict):
                return False
            for item in sequence:
                remaining -= 1
                if remaining < 0 or not bind(generator.target, item):
                    return False
                for condition in generator.ifs:
                    condition_value = scope.value(condition)
                    if condition_value is _UNKNOWN:
                        return False
                    if not condition_value:
                        break
                else:
                    if not collect(index + 1):
                        return False
            return True

        return result if collect(0) else _UNKNOWN

    def expression(self, node):
        if isinstance(node, ast.IfExp):
            test = self.value(node.test)
            if test is not _UNKNOWN:
                return self.expression(node.body if test else node.orelse)
        if isinstance(node, ast.BoolOp):
            for index, part in enumerate(node.values[:-1]):
                value = self.value(part)
                if value is _UNKNOWN:
                    if index:
                        node.values = node.values[index:]
                    break
                if bool(value) == isinstance(node.op, ast.Or):
                    return self.expression(part)
            else:
                return self.expression(node.values[-1])
        value = self.value(node)
        if value is _UNKNOWN:
            # Do not descend into opaque expressions: order, lazy evaluation,
            # walrus bindings and comprehension scopes must remain intact.
            self.invalidate(node)
        elif _immutable(value):
            node = ast.copy_location(_literal(value), node)
        elif isinstance(node, (ast.ListComp, ast.DictComp)):
            literal = _fresh_literal(value)
            if literal is not None:
                node = ast.copy_location(literal, node)
        return node, value

    def assign(self, target, value):
        if isinstance(target, ast.Name):
            self.env.pop(target.id, None)
            if value is not _UNKNOWN and _immutable(value):
                self.env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            values = value if type(value) in (tuple, list, str, bytes) else ()
            if len(values) != len(target.elts) or any(isinstance(part, ast.Starred) for part in target.elts):
                values = [_UNKNOWN] * len(target.elts)
            for part, item in zip(target.elts, values):
                self.assign(part, item)
        else:
            self.invalidate(target)

    def block(self, body):
        result = []
        for statement in body:
            result.extend(self.statement(statement))
        return result

    def statement(self, node):
        if isinstance(node, ast.If):
            node.test, test = self.expression(node.test)
            if test is not _UNKNOWN:
                return self.block(node.body if test else node.orelse)
            entry = self.env.copy()
            node.body = self.block(node.body) or [ast.copy_location(ast.Pass(), node)]
            then = self.env
            self.env = entry
            node.orelse = self.block(node.orelse)
            self.env = {
                name: value for name, value in then.items()
                if _immutable(value) and name in self.env
                and _same(value, self.env[name])
            }
        elif isinstance(node, ast.Assign):
            node.value, value = self.expression(node.value)
            simple = all(isinstance(part, (ast.Name, ast.Tuple, ast.List, ast.Load, ast.Store))
                         for target in node.targets for part in ast.walk(target))
            if not simple:
                self.invalidate(node)
            else:
                fresh = not any(isinstance(part, ast.Name) for part in ast.walk(node.value))
                if value is not _UNKNOWN and not _immutable(value) and not fresh:
                    # A mutable alias could be modified through either name.
                    self.env = {name: item for name, item in self.env.items() if _immutable(item)}
                for target in node.targets:
                    self.assign(target, value)
                if (len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                        and value is not _UNKNOWN and not _immutable(value)
                        and fresh):
                    self.env[node.targets[0].id] = value
        elif isinstance(node, ast.Return) and node.value is not None:
            node.value, _ = self.expression(node.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Nested functions can outlive/rebind their enclosing environment.
            self.invalidate(node)
        elif isinstance(node, (ast.Pass, ast.Break, ast.Continue)):
            pass
        else:
            # Never use one loop iteration or the successful path through a
            # try/with/match as evidence about subsequent code.
            self.invalidate(node)
        return [node]


def _sensitive(node):
    """These constructs need stronger analysis than literal propagation."""
    for child in ast.walk(node):
        if isinstance(child, (ast.Yield, ast.YieldFrom, ast.Await, ast.Global, ast.Nonlocal)):
            return True
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            if child.func.id in {'id', 'locals', 'globals', 'vars'}:
                return True
        if isinstance(child, ast.Compare):
            for operation, right in zip(child.ops, child.comparators):
                if isinstance(operation, (ast.Is, ast.IsNot)) and not (
                    isinstance(right, ast.Constant)
                    and (right.value is None or type(right.value) is bool)
                ):
                    return True
    return False


def _function(node, bindings, shadowed):
    if _sensitive(node):
        return node
    parameters = {arg.arg for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]}
    parameters.update(arg.arg for arg in (node.args.vararg, node.args.kwarg) if arg is not None)
    original_locals = _locals(node.body)
    captured = set()
    for statement in node.body:
        for child in ast.walk(statement):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                captured.update(part.id for part in ast.walk(child) if isinstance(part, ast.Name))
    engine = _Evaluator({name: value for name, value in bindings.items() if name in parameters},
                        shadowed, original_locals | parameters, captured)
    had_docstring = _docstring(node.body)
    node.body = engine.block(node.body) or [ast.copy_location(ast.Pass(), node)]
    if not had_docstring and _docstring(node.body):
        node.body.insert(0, ast.copy_location(ast.Pass(), node))
    # Preserve local/cell classification after removing dead assignments.
    missing = sorted(original_locals - _locals(node.body) - parameters)
    declarations = [ast.copy_location(ast.AnnAssign(target=ast.Name(id=name, ctx=ast.Store()),
                    annotation=ast.Constant(None), value=None, simple=1), node) for name in missing]
    insertion = 1 if _docstring(node.body) else 0
    node.body[insertion:insertion] = declarations
    return node


def specialize(tree: ast.AST, bindings: dict[str, object] | None = None) -> ast.AST:
    """Return an independent, compilable AST specialized using safe literal data.

    Bindings apply to top-level statements/expressions and immediate function
    parameters. Free globals and nested function bodies are not frozen at
    definition time. Unsupported values and operations remain dynamic.
    """
    tree = deepcopy(tree)
    shadowed = _writes(tree) | (bindings or {}).keys()
    bindings = {name: value for name, value in (bindings or {}).items() if _safe(value)}
    if any(isinstance(node, ast.ImportFrom) and any(alias.name == '*' for alias in node.names)
           for node in ast.walk(tree)):
        shadowed |= _CONVERSIONS.keys()
    sensitive_root = tree
    if isinstance(tree, ast.Module):
        sensitive_root = ast.Module(body=[node for node in tree.body if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))], type_ignores=[])
    if _sensitive(sensitive_root):
        return ast.fix_missing_locations(tree)
    engine = _Evaluator(bindings, shadowed)
    if isinstance(tree, (ast.FunctionDef, ast.AsyncFunctionDef)):
        tree = _function(tree, bindings, shadowed)
    elif isinstance(tree, ast.Module):
        had_docstring = _docstring(tree.body)
        body = []
        for statement in tree.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                engine.invalidate(statement)
                body.append(_function(statement, bindings, shadowed))
            else:
                body.extend(engine.statement(statement))
        if not had_docstring and _docstring(body):
            body.insert(0, ast.Pass())
        tree.body = body
    elif isinstance(tree, ast.Expression):
        tree.body, _ = engine.expression(tree.body)
    elif isinstance(tree, ast.expr):
        tree, _ = engine.expression(tree)
    elif isinstance(tree, ast.ClassDef):
        # Class namespaces and metaclass hooks are observable execution scopes.
        pass
    elif isinstance(tree, ast.stmt):
        statements = engine.statement(tree)
        tree = statements[0] if len(statements) == 1 else ast.Module(body=statements, type_ignores=[])
    return ast.fix_missing_locations(tree)

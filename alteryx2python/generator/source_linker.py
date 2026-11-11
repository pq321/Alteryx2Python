"""Link audited Python helpers into generated code without project imports."""
from __future__ import annotations

import ast
import builtins
import hashlib
import inspect
import textwrap
import warnings
import re


class UnsupportedLowering(ValueError):
    """The compiler cannot preserve this operation using audited templates."""


class _Simplify(ast.NodeTransformer):
    """Remove template scaffolding using syntax and literal values only."""

    def visit_Assign(self, node):
        node = self.generic_visit(node)
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and isinstance(node.value, ast.Name) and node.targets[0].id == node.value.id:
            return None
        return node

    def visit_Call(self, node):
        node = self.generic_visit(node)
        conversions = {'str': str, 'int': int, 'float': float, 'bool': bool, 'list': list, 'tuple': tuple, 'dict': dict, 'set': set}
        if isinstance(node.func, ast.Name) and node.func.id in conversions and not node.keywords:
            try:
                values = [ast.literal_eval(arg) for arg in node.args]
                return ast.copy_location(ast.parse(repr(conversions[node.func.id](*values)), mode='eval').body, node)
            except (ValueError, TypeError, SyntaxError, OverflowError):
                pass
        return node

    def visit_Compare(self, node):
        node = self.generic_visit(node)
        if len(node.ops) == 1 and isinstance(node.ops[0], (ast.In, ast.NotIn)) and isinstance(node.left, ast.Constant) and isinstance(node.comparators[0], ast.Dict):
            dictionary = node.comparators[0]
            if all(isinstance(key, ast.Constant) for key in dictionary.keys) and all(isinstance(value, (ast.Name, ast.Constant)) for value in dictionary.values):
                present = node.left.value in [key.value for key in dictionary.keys]
                return ast.copy_location(ast.Constant(not present if isinstance(node.ops[0], ast.NotIn) else present), node)
        return node

    def visit_If(self, node):
        node = self.generic_visit(node)
        if isinstance(node.test, ast.Constant):
            return node.body if node.test.value else node.orelse
        return node

    def visit_Subscript(self, node):
        node = self.generic_visit(node)
        if isinstance(node.value, ast.Dict) and isinstance(node.slice, ast.Constant) and all(isinstance(key, ast.Constant) for key in node.value.keys):
            if all(isinstance(value, (ast.Name, ast.Constant)) for value in node.value.values):
                for key,value in zip(node.value.keys,node.value.values):
                    if key.value == node.slice.value:
                        return ast.copy_location(value, node)
        return node


def simplify_template(tree):
    tree = _Simplify().visit(tree)
    # The original tool returned an anchor dictionary. Its dataframes are now
    # ordinary return values, so eliminate the temporary dictionary when safe.
    outputs = next((node.value for node in tree.body if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'outputs' and isinstance(node.value, ast.Dict)), None)
    parents = {child:parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
    references = [node for node in ast.walk(tree) if isinstance(node,ast.Name) and node.id == 'outputs' and isinstance(node.ctx,ast.Load)]
    def in_return(reference):
        parent = parents.get(reference)
        if not isinstance(parent,ast.Subscript) or not isinstance(parent.ctx,ast.Load):
            return False
        while parent in parents:
            parent = parents[parent]
            if isinstance(parent,ast.Return):
                return True
            if not isinstance(parent,(ast.Tuple,ast.List)):
                return False
        return False
    stores = [node for node in ast.walk(tree) if isinstance(node,ast.Name) and node.id == 'outputs' and isinstance(node.ctx,ast.Store)]
    if outputs is not None and len(stores) == 1 and all(in_return(node) for node in references) and all(isinstance(value,(ast.Name,ast.Constant)) for value in outputs.values):
        class InlineOutput(ast.NodeTransformer):
            def visit_Subscript(self, node):
                if isinstance(node.value, ast.Name) and node.value.id == 'outputs':
                    node.value = outputs
                return self.generic_visit(node)
        tree = _Simplify().visit(InlineOutput().visit(tree))
        if not any(isinstance(node,ast.Name) and node.id == 'outputs' and isinstance(node.ctx,ast.Load) for node in ast.walk(tree)):
            tree.body = [node for node in tree.body if not (isinstance(node,ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id == 'outputs')]
    return tree


class _Lexical(ast.NodeTransformer):
    """Resolve globals with Python's scope tables, including comprehensions."""

    def apply(self, tree):
        import symtable
        source = ast.unparse(ast.fix_missing_locations(tree))
        parsed = ast.parse(source)
        self.scope = symtable.symtable(source, '<template>', 'exec')
        self.used_scopes = set()
        self.comprehension_bindings = []
        result = self.visit(parsed)
        return result if isinstance(tree, ast.Module) else result.body[0]

    def is_global(self, name):
        if any(name in bindings for bindings in self.comprehension_bindings):
            return False
        try:
            return self.scope.lookup(name).is_global()
        except KeyError:
            return False

    def child_scope(self, name, line):
        for scope in self.scope.get_children():
            if scope.get_name() == name and scope.get_lineno() == line and scope.get_id() not in self.used_scopes:
                self.used_scopes.add(scope.get_id())
                return scope
        raise UnsupportedLowering(f'Cannot resolve template scope: {name}:{line}')

    def visit_FunctionDef(self, node):
        node.decorator_list = [self.visit(item) for item in node.decorator_list]
        node.args = self.visit(node.args)
        if node.returns is not None:
            node.returns = self.visit(node.returns)
        parent = self.scope
        self.scope = self.child_scope(node.name, node.lineno)
        node.body = [self.visit(item) for item in node.body]
        self.scope = parent
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        node.decorator_list = [self.visit(item) for item in node.decorator_list]
        node.bases = [self.visit(item) for item in node.bases]
        node.keywords = [self.visit(item) for item in node.keywords]
        parent = self.scope
        self.scope = self.child_scope(node.name, node.lineno)
        node.body = [self.visit(item) for item in node.body]
        self.scope = parent
        return node

    def visit_Lambda(self, node):
        node.args = self.visit(node.args)
        parent = self.scope
        self.scope = self.child_scope('lambda', node.lineno)
        node.body = self.visit(node.body)
        self.scope = parent
        return node

    def comprehension(self, node, name):
        node.generators[0].iter = self.visit(node.generators[0].iter)
        parent = self.scope
        # Python 3.12 inlines list/set/dict comprehensions (PEP 709), so their
        # target bindings no longer have a child symtable. Keep them lexical.
        children = [scope for scope in parent.get_children() if scope.get_name() == name and scope.get_lineno() == node.lineno and scope.get_id() not in self.used_scopes]
        if children:
            self.scope = self.child_scope(name, node.lineno)
        elif name == 'genexpr' or parent.get_type() == 'class':
            raise UnsupportedLowering(f'Cannot resolve template comprehension: {name}:{node.lineno}')
        bindings = {item.id for generator in node.generators for item in ast.walk(generator.target) if isinstance(item, ast.Name)}
        self.comprehension_bindings.append(bindings)
        for index, generator in enumerate(node.generators):
            generator.target = self.visit(generator.target)
            if index:
                generator.iter = self.visit(generator.iter)
            generator.ifs = [self.visit(item) for item in generator.ifs]
        for attribute in ('elt', 'key', 'value'):
            if hasattr(node, attribute):
                setattr(node, attribute, self.visit(getattr(node, attribute)))
        self.scope = parent
        self.comprehension_bindings.pop()
        return node

    def visit_ListComp(self, node):
        return self.comprehension(node, 'listcomp')

    def visit_SetComp(self, node):
        return self.comprehension(node, 'setcomp')

    def visit_DictComp(self, node):
        return self.comprehension(node, 'dictcomp')

    def visit_GeneratorExp(self, node):
        return self.comprehension(node, 'genexpr')


class _Rename(_Lexical):
    def __init__(self, names):
        self.names = names

    def visit_Name(self, node):
        if node.id in self.names and self.is_global(node.id):
            return ast.copy_location(ast.Name(self.names[node.id], node.ctx), node)
        return node

    def visit_Global(self, node):
        node.names = [self.names.get(name, name) for name in node.names]
        return node


class RemoveTracing(ast.NodeTransformer):
    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            owner = node.value.func.value
            if isinstance(owner, ast.Name) and owner.id == 'context':
                if node.value.func.attr == 'record_node':
                    return None
                if node.value.func.attr == 'record_warning':
                    return ast.Expr(ast.Call(ast.Attribute(ast.Name('warnings', ast.Load()), 'warn', ast.Load()),
                        args=[self.visit(node.value.args[0]), ast.Name('RuntimeWarning', ast.Load())], keywords=[]))
            if isinstance(owner, ast.Attribute) and isinstance(owner.value, ast.Name) and owner.value.id == 'context' and owner.attr == 'traces' and node.value.func.attr == 'pop':
                return None
        return self.generic_visit(node)

    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == 'context':
            raise UnsupportedLowering(f'Observable runtime dependency: context.{node.attr}')
        return self.generic_visit(node)


class _RemoveContextArguments(_Lexical):
    def __init__(self, namespace):
        self.namespace = namespace

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and self.is_global(node.func.id):
            function = self.namespace.get(node.func.id)
            if inspect.isfunction(function) and function.__module__.startswith('alteryx2python.'):
                parameters = list(inspect.signature(function).parameters)
                if 'context' in parameters:
                    position = parameters.index('context')
                    if len(node.args) > position:
                        node.args.pop(position)
                    node.keywords = [item for item in node.keywords if item.arg != 'context']
        return self.generic_visit(node)


def strip_annotations(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.returns = None
        elif isinstance(node, ast.arg):
            node.annotation = None
        elif isinstance(node, ast.AnnAssign):
            node.annotation = ast.Name('object', ast.Load())
    return tree


class SourceLinker:
    """Copy a closed, versioned source dependency set; never import the runtime."""

    def __init__(self):
        self.imports = {'from __future__ import annotations', 'import pandas as pd'}
        self.definitions = {}
        self.digests = {}
        self._active = set()
        self._names = {}

    def function(self, function, bindings=None):
        module = function.__module__
        if not module.startswith(('alteryx2python.tools.', 'alteryx2python.expressions.functions',
                                  'alteryx2python.expressions.errors', 'alteryx2python.comparison.schema_diff')):
            raise UnsupportedLowering(f'Helper outside audited source boundary: {module}.{function.__name__}')
        identity = (module, function.__qualname__, repr(sorted((bindings or {}).items())))
        if identity not in self._names:
            base = '_' + module.rsplit('.', 1)[-1] + '_' + function.__name__.lstrip('_')
            name, suffix = base, 1
            while name in self._names.values():
                suffix += 1
                name = f'{base}_{suffix}'
            self._names[identity] = name
        name = self._names[identity]
        if name in self.definitions or name in self._active:
            return name
        self._active.add(name)
        source = textwrap.dedent(inspect.getsource(function))
        tree = strip_annotations(ast.parse(source).body[0])
        if not isinstance(tree, (ast.FunctionDef, ast.ClassDef)):
            raise UnsupportedLowering(f'Non-function helper: {name}')
        tree.decorator_list = []
        if isinstance(tree, ast.FunctionDef) and any(arg.arg == "context" for arg in tree.args.args):
            tree = RemoveTracing().visit(tree)
        if isinstance(tree, ast.FunctionDef):
            tree.args.args = [arg for arg in tree.args.args if arg.arg != 'context']
            if bindings:
                defaults = dict(zip([arg.arg for arg in tree.args.args[-len(tree.args.defaults):]], tree.args.defaults)) if tree.args.defaults else {}
                tree.args.args = [arg for arg in tree.args.args if arg.arg not in bindings]
                tree.args.defaults = [defaults[arg.arg] for arg in tree.args.args if arg.arg in defaults]
                pairs = [(arg, default) for arg, default in zip(tree.args.kwonlyargs, tree.args.kw_defaults) if arg.arg not in bindings]
                tree.args.kwonlyargs = [arg for arg, _ in pairs]
                tree.args.kw_defaults = [default for _, default in pairs]
                tree.body[0:0] = [ast.Assign(targets=[ast.Name(id=key, ctx=ast.Store())], value=ast.parse(repr(value), mode='eval').body) for key, value in bindings.items()]
        from alteryx2python.generator.partial_eval import specialize
        if not isinstance(tree, ast.ClassDef):
            tree = specialize(tree)
        tree.name = name
        namespace = {**vars(inspect.getmodule(function)), 'warnings': warnings}
        if inspect.isfunction(function):
            namespace.update(inspect.getclosurevars(function).nonlocals)
        tree = self.bind_globals(tree, namespace)
        self.definitions[name] = ast.unparse(ast.fix_missing_locations(tree))
        self.digests[name] = hashlib.sha256(source.encode()).hexdigest()
        self._active.remove(name)
        return name

    def bind_globals(self, tree, namespace):
        tree = _RemoveContextArguments(namespace).apply(tree)
        from alteryx2python.generator.partial_eval import specialize
        if not isinstance(tree, ast.ClassDef):
            tree = specialize(tree)
        linker = self
        class BindStaticCalls(_Lexical):
            def visit_Call(self, node):
                node = self.generic_visit(node)
                if isinstance(node.func, ast.Name) and not self.is_global(node.func.id):
                    return node
                function = namespace.get(node.func.id) if isinstance(node.func, ast.Name) else None
                if not inspect.isfunction(function) or not function.__module__.startswith('alteryx2python.'):
                    return node
                signature = inspect.signature(function)
                if any(arg.kind in (arg.VAR_POSITIONAL, arg.VAR_KEYWORD) for arg in signature.parameters.values()):
                    return node
                parameters = [key for key, arg in signature.parameters.items() if key != 'context' and arg.kind in (arg.POSITIONAL_ONLY, arg.POSITIONAL_OR_KEYWORD)]
                bindings, remove = {}, set()
                for index, argument in enumerate(node.args):
                    if index >= len(parameters):
                        return node
                    try:
                        bindings[parameters[index]] = ast.literal_eval(argument)
                        remove.add(index)
                    except (ValueError, TypeError):
                        pass
                for item in node.keywords:
                    if item.arg in signature.parameters:
                        try:
                            bindings[item.arg] = ast.literal_eval(item.value)
                        except (ValueError, TypeError):
                            pass
                if not bindings:
                    return node
                node.func.id = linker.function(function, bindings)
                node.args = [argument for index, argument in enumerate(node.args) if index not in remove]
                node.keywords = [item for item in node.keywords if item.arg not in bindings]
                return node
        tree = BindStaticCalls().apply(tree)
        # symtable distinguishes function locals/comprehension bindings from globals.
        import symtable
        source = ast.unparse(ast.fix_missing_locations(tree))
        table = symtable.symtable(source, '<template>', 'exec')
        globals_used = set()

        def collect(scope):
            for symbol in scope.get_symbols():
                if symbol.is_global() and symbol.is_referenced():
                    globals_used.add(symbol.get_name())
            for child in scope.get_children():
                collect(child)

        collect(table)
        imports = {}
        module_name = namespace.get('__name__', '')
        module = inspect.getmodule(next((value for value in namespace.values()
                                        if inspect.isfunction(value) and value.__module__ == module_name), None))
        if module is not None:
            for statement in ast.parse(inspect.getsource(module)).body:
                if isinstance(statement, ast.Import):
                    for alias in statement.names:
                        imports[alias.asname or alias.name.split('.')[0]] = ast.Import(names=[alias])
                elif isinstance(statement, ast.ImportFrom) and statement.module:
                    for alias in statement.names:
                        imports[alias.asname or alias.name] = ast.ImportFrom(module=statement.module, names=[alias], level=0)
        renames = {}
        for name in sorted(globals_used):
            if name in self.definitions or name in self._active:
                continue
            if name in {'eval', 'exec', '__import__', 'compile'}:
                raise UnsupportedLowering(f'Dynamic execution in template: {name}')
            if name not in namespace:
                if hasattr(builtins, name):
                    continue
                raise UnsupportedLowering(f'Unbound template symbol: {name}')
            value = namespace[name]
            origin = getattr(value, '__module__', '')
            if inspect.isfunction(value) and origin.startswith('alteryx2python.'):
                renames[name] = self.function(value)
            elif isinstance(value, type) and origin.startswith('alteryx2python.tools.') and name.startswith('_'):
                renames[name] = self.function(value)
            elif isinstance(value, re.Pattern):
                self.imports.add('import re')
                constant = '_' + module_name.rsplit('.', 1)[-1] + '_' + name
                self.definitions[constant] = f'{constant} = re.compile({value.pattern!r}, {value.flags!r})'
                renames[name] = constant
            elif isinstance(value, type) and origin == 'alteryx2python.expressions.errors':
                self.definitions[name] = f'class {name}(ValueError):\n    pass'
            elif name in imports:
                statement = imports[name]
                if isinstance(statement, ast.ImportFrom) and statement.module.startswith('alteryx2python'):
                    raise UnsupportedLowering(f'Runtime dependency remains: {statement.module}.{name}')
                self.imports.add(ast.unparse(statement))
            elif inspect.ismodule(value) and not value.__name__.startswith('alteryx2python'):
                self.imports.add(f'import {value.__name__} as {name}')
            elif isinstance(value, (dict, list, tuple, set, str, int, float, bool, type(None))):
                constant = '_' + module_name.rsplit('.', 1)[-1] + '_' + name
                try:
                    ast.literal_eval(repr(value))
                except (ValueError, SyntaxError) as exc:
                    raise UnsupportedLowering(f'Non-literal global: {name}') from exc
                self.definitions[constant] = f'{constant} = {value!r}'
                renames[name] = constant
            elif not hasattr(builtins, name):
                raise UnsupportedLowering(f'Unsupported global: {name}')
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or '').startswith('alteryx2python'):
                raise UnsupportedLowering(f'Late runtime import: {node.module}')
        return _Rename(renames).apply(tree)

    def render(self):
        return '\n'.join(sorted(self.imports)) + '\n\n' + '\n\n'.join(self.definitions.values())

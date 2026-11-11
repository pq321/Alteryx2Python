"""Literal folding and adversarial differential tests for template specialization."""
import ast
from copy import deepcopy
import re
import textwrap
from types import SimpleNamespace

import pytest

from alteryx2python.generator.partial_eval import specialize


def _tree(source):
    return ast.parse(textwrap.dedent(source))


def _namespace(tree, extra=None):
    namespace = dict(extra or {})
    exec(compile(tree, '<partial-eval-test>', 'exec'), namespace)
    # The source linker ultimately prints this AST, so verify that path too.
    compile(ast.unparse(tree), '<printed-partial-eval-test>', 'exec')
    return namespace


def _compare(source, cases, bindings=None, extra=None):
    original = _tree(source)
    optimized = specialize(original, bindings)
    for args in cases:
        outcomes = []
        for tree in (original, optimized):
            arguments = deepcopy(args)
            function = _namespace(tree, extra)['f']
            try:
                outcome = ('return', function(*arguments))
            except Exception as error:
                outcome = ('raise', type(error), str(error))
            outcomes.append((outcome, arguments))
        assert outcomes[0] == outcomes[1]
    return optimized


def test_static_config_branch_and_local_propagation():
    config = {'mode': ' CSV ', 'count': '2', 'enabled': True}
    tree = _compare('''
        def f(config):
            mode = config.get('mode', '').strip().lower()
            count = int(config['count']) * 2
            if mode == 'csv' and count >= 4 and config.get('enabled', False):
                result = count + 1
            else:
                raise RuntimeError('dead configuration')
            return result
    ''', [(config,)], {'config': config})
    assert not any(isinstance(node, (ast.If, ast.Call)) for node in ast.walk(tree))
    assert ast.literal_eval(tree.body[0].body[-1].value) == 5


@pytest.mark.parametrize(('expression', 'expected'), [
    ('(2 + 3) * 4 - 1', 19),
    ('17 // 3 + 17 % 3', 7),
    ('8 / 2', 4.0),
    ('2 ** 8', 256),
    ('(3 << 2) | (7 & 2) ^ 1', 15),
    ('~2', -3),
    ('+3 + -2', 1),
    ('1 < 2 <= 2 != 3', True),
    ('2 > 1 >= 1 == 1', True),
    ("'b' in {'a': 1, 'b': 2}", True),
    ("'z' not in ('a', 'b')", True),
    ('not []', True),
    ('0 or 3', 3),
    ('2 and 4', 4),
    ('False and missing()', False),
    ('True or missing()', True),
    ('2 < 1 < missing()', False),
    ('3 if True else missing()', 3),
    ("{'x': (3, 4)}.get('x')[1]", 4),
    ("{}.get('x', 'fallback')", 'fallback'),
    ("{}.get('x')", None),
    ("'abcdef'[1:5:2]", 'bd'),
    ("(1, 2, 3)[::-1]", (3, 2, 1)),
    ("str(int('10') + 2)", '12'),
    ("float('2.5') + bool(1)", 3.5),
    ("tuple('ab')", ('a', 'b')),
    ("len('abc') + abs(-2)", 5),
    ("round(2.75, 1)", 2.8),
    ("' A-B '.strip().lower().replace('-', '_')", 'a_b'),
    ("'alpha.csv'.endswith(('.csv', '.txt'))", True),
    ("'a,b'.split(',')[1]", 'b'),
    ("'prefix_name'.removeprefix('prefix_')", 'name'),
    ("'_'.join(['a', 'b'])", 'a_b'),
    ('None is None', True),
    ('1 is not None', True),
])
def test_safe_literal_expressions(expression, expected):
    tree = specialize(ast.parse(expression, mode='eval'))
    assert ast.literal_eval(tree.body) == expected
    compile(tree, '<expression>', 'eval')


@pytest.mark.parametrize('expression', [
    '1 / 0', "int('not-an-int')", "{'x': 1}['missing']", '(1,)[9]',
    '{[]: 1}', "'x'.index('y')", "{'x': missing(), 'y': 2}['y']",
    "{'x': 1}.get('x', missing())", '1 < missing() < 0',
    "'x' * (10 ** 12)", '2 ** (10 ** 8)', '1 << (10 ** 9)',
    "'%1000000000s' % 'x'", "'x'.format(missing())", "tuple({'b', 'a'})",
])
def test_unsupported_or_failing_expressions_stay_dynamic(expression):
    original = ast.parse(expression, mode='eval')
    assert ast.dump(specialize(original)) == ast.dump(original)


@pytest.mark.parametrize('expression', [
    '1 / 0', "int('not-an-int')", "{'x': 1}['missing']", '(1,)[9]',
    '{[]: 1}', "'x'.index('y')",
])
def test_runtime_exceptions_are_not_compile_time_errors(expression):
    _compare(f'def f():\n    return {expression}', [()])


@pytest.mark.parametrize('expression', [
    "{'x': events.append('dictionary'), 'y': 2}['y']",
    "{'x': 1}.get('x', events.append('default'))",
    "events.append('left') or True",
    "[events.append('list'), 2][1]",
])
def test_discarded_values_still_have_side_effects(expression):
    tree = _compare(f'''
        def f(events):
            result = {expression}
            return result, events
    ''', [([], )])
    assert any(isinstance(node, ast.Call) for node in ast.walk(tree))


@pytest.mark.parametrize('branch', [
    'if flag:\n    x = 2',
    'if flag:\n    x = 2\nelse:\n    x = 3',
    'if flag:\n    del x',
    'if (x := flag):\n    pass',
])
def test_dynamic_branches_invalidate_writes(branch):
    source = 'def f(flag):\n    x = 1\n' + textwrap.indent(branch, '    ') + '\n    return x'
    _compare(source, [(False,), (True,)])


def test_branch_merge_distinguishes_signed_zero():
    _compare('''
        import math
        def f(flag):
            if flag:
                x = -0.0
            else:
                x = 0.0
            y = x
            return math.copysign(1.0, y)
    ''', [(False,), (True,)])


@pytest.mark.parametrize('loop', [
    'for x in values:\n    pass',
    'for item in values:\n    x += item',
    'for item in values:\n    x = item\n    if item == 2:\n        break\nelse:\n    x = 9',
    'while x < len(values):\n    x += 1\nelse:\n    x += 1',
    'for item in values:\n    if item == 2:\n        continue\n    x = item',
])
def test_dynamic_loops_do_not_use_one_iteration_as_a_constant(loop):
    source = 'def f(values):\n    x = 0\n' + textwrap.indent(loop, '    ') + '\n    return x'
    _compare(source, [([],), ([1],), ([1, 2, 3],)])


def test_try_handlers_finally_and_exception_target_cleanup():
    _compare('''
        def f(fail):
            x = 1
            try:
                x = 2
                if fail:
                    raise ValueError('fail')
                x = 3
            except ValueError:
                x = 4
            finally:
                x += 10
            return x
    ''', [(False,), (True,)])
    _compare('''
        def f():
            error = 1
            try:
                raise ValueError('fail')
            except ValueError as error:
                pass
            return error
    ''', [()])


@pytest.mark.parametrize('setup', [
    "a = b = []\na.append(1)\nreturn b",
    "config = {'x': []}\na = config['x']\na.append(1)\nreturn config['x']",
    "config = {'x': []}\na = config.get('x')\na.append(1)\nreturn config['x']",
    "config = {'x': []}\na = (config,)\na[0]['x'].append(1)\nreturn config['x']",
    "config = {'x': 1}\na = config\na['x'] = 2\nreturn config['x']",
    "config = {'x': 1}\nconfig.update(x=2)\nreturn config['x']",
    "config = {'x': 1}\nconfig['x'] += 1\nreturn config['x']",
])
def test_mutable_aliases_and_mutations(setup):
    _compare('def f():\n' + textwrap.indent(setup, '    '), [()])


def test_external_config_mutation_invalidates_snapshot():
    config = {'x': 1}
    _compare('''
        def f(config, flag):
            if flag:
                config['x'] = 2
            return config.get('x')
    ''', [(config, False), (config, True)], {'config': config})
    _compare('''
        def f(config):
            config.clear()
            return config.get('x', 3)
    ''', [(config,)], {'config': config})
    assert config == {'x': 1}


def test_opaque_call_and_dynamic_truthiness_can_mutate_config():
    source = '''
        def f(config, change):
            if change:
                pass
            return config['x']
    '''
    tree = specialize(_tree(source), {'config': {'x': 1}})
    config = {'x': 1}

    class Change:
        def __bool__(self):
            config['x'] = 2
            return True

    assert _namespace(tree)['f'](config, Change()) == 2
    _compare('''
        def f(config):
            def change():
                config['x'] = 2
            change()
            return config['x']
    ''', [({'x': 1},)], {'config': {'x': 1}})


def test_multiple_assignments_and_nested_unpacking_are_valid():
    tree = _compare('''
        def f():
            a = b = 3
            c, (d, e) = [1, [2, 4]]
            if a + b + c + d + e == 13:
                return 'folded'
            return 'wrong'
    ''', [()])
    assert not any(isinstance(node, ast.If) for node in ast.walk(tree))
    _compare('''
        def f(values):
            first = 9
            first, *rest = values
            return first, rest
    ''', [([1, 2, 3],), ([],)])


def test_local_literal_dictionary_can_be_read_statically():
    tree = _compare('''
        def f():
            config = {'kind': 'CSV', 'enabled': True}
            kind = config.get('kind').lower()
            if kind == 'csv':
                return 1
            return 2
    ''', [()])
    assert not any(isinstance(node, ast.If) for node in ast.walk(tree))


@pytest.mark.parametrize('source', [
    '''
        def f(values):
            x = 7
            result = [x * 2 for x in values]
            return x, result
    ''',
    '''
        def f(values):
            x = 7
            result = [(x := item) for item in values]
            return x, result
    ''',
    '''
        def f(values):
            x = 7
            result = {x: [x for x in values] for x in values}
            return x, result
    ''',
    '''
        def f(values):
            x = 1
            read = lambda: x
            x = 2
            return read()
    ''',
    '''
        def f(values):
            x = 1
            def read():
                return x
            x = 2
            return read()
    ''',
])
def test_comprehensions_and_deferred_scopes(source):
    _compare(source, [([],), ([2, 3],)])


def test_nested_nonlocal_writes_and_defaults_are_not_frozen():
    _compare('''
        def f():
            x = 1
            def change():
                nonlocal x
                x = 2
            change()
            return x
    ''', [()])
    _compare('''
        def f():
            x = 1
            def read(value=(x := 2)):
                return value
            return x, read()
    ''', [()])


@pytest.mark.parametrize('source', [
    '''
        def f():
            if False:
                x = 1
            return x
    ''',
    '''
        def f():
            if False:
                x = 1
            def read():
                return x
            return read()
    ''',
    '''
        def f():
            if False:
                import x
            return x
    ''',
])
def test_dead_assignments_preserve_unbound_locals_and_cells(source):
    tree = _compare(source, [()], extra={'x': 99})
    assert not any(isinstance(node, ast.If) for node in ast.walk(tree))


def test_empty_functions_docstrings_and_generator_classification():
    for source in [
        'def f():\n    if False:\n        pass',
        'def f():\n    if True:\n        "not a docstring"',
        'def f():\n    "a docstring"\n    if False:\n        pass',
    ]:
        original = _namespace(_tree(source))['f']
        optimized = _namespace(specialize(_tree(source)))['f']
        assert optimized() == original()
        assert optimized.__doc__ == original.__doc__
    tree = specialize(_tree('def f():\n    if False:\n        yield 1'))
    assert list(_namespace(tree)['f']()) == []
    assert any(isinstance(node, ast.Yield) for node in ast.walk(tree))
    namespace = _namespace(specialize(_tree('if True:\n    "not a docstring"')))
    assert namespace.get('__doc__') is None


def test_shadowed_builtins_are_not_executed_by_the_specializer():
    _compare('''
        def f(int):
            value = int('3')
            return value
    ''', [(lambda value: 'custom',)])
    _compare('''
        str = lambda value: 'custom'
        def f():
            return str(3)
    ''', [()])
    _compare('''
        def f():
            result = int('3')
            int = lambda value: 9
            return result
    ''', [()])


def test_unsafe_binding_protocols_are_never_invoked():
    class Poison(dict):
        def get(self, *args):
            raise AssertionError('must not call user code')

        def __bool__(self):
            raise AssertionError('must not call user code')

    source = ast.parse("config.get('x') or bool(config)", mode='eval')
    assert ast.dump(specialize(source, {'config': Poison(x=1)})) == ast.dump(source)
    cycle = []
    cycle.append(cycle)
    specialize(ast.parse('config', mode='eval'), {'config': cycle})


def test_identity_observation_is_conservative():
    _compare('''
        def f():
            a = int('5000')
            b = int('5000')
            return a is b
    ''', [()])
    source = _tree("a = int('5000')\nb = int('5000')\nresult = a is b")
    assert _namespace(specialize(source))['result'] == _namespace(source)['result']


def test_bindings_do_not_freeze_free_globals_or_nested_parameters():
    _compare('''
        config = 7
        def f():
            return config
        config = 8
    ''', [()], {'config': 1})
    _compare('''
        def f(config):
            def read(config):
                return config
            return read(8)
    ''', [(1,)], {'config': 1})


def test_independent_deterministic_output_and_supported_roots():
    original = _tree('def f(config):\n    if config:\n        return 2 + 3')
    before = ast.dump(original, include_attributes=True)
    first = specialize(original, {'config': True})
    second = specialize(original, {'config': True})
    assert ast.dump(first, include_attributes=True) == ast.dump(second, include_attributes=True)
    assert ast.dump(specialize(first, {'config': True})) == ast.dump(first)
    assert ast.dump(original, include_attributes=True) == before
    assert first is not original
    function = specialize(original.body[0], {'config': True})
    assert isinstance(function, ast.FunctionDef)
    assert _namespace(ast.Module(body=[function], type_ignores=[]))['f'](True) == 5
    expression = specialize(ast.parse('2 + 3', mode='eval').body)
    assert isinstance(expression, ast.Constant) and expression.value == 5


def test_class_and_assignment_root_types_survive_linker_renaming():
    tree = specialize(_tree('class Original:\n    value = 1').body[0])
    assert isinstance(tree, ast.ClassDef)
    tree.name = 'Renamed'
    assert _namespace(ast.Module(body=[tree], type_ignores=[]))['Renamed'].value == 1
    assignment = specialize(_tree('value = 1 + 2').body[0])
    assert isinstance(assignment, ast.Assign)
    assert ast.literal_eval(assignment.value) == 3


@pytest.mark.parametrize('enabled', [False, True])
def test_linker_literal_config_selects_dynamic_return_expression(enabled):
    source = f'''
        def f():
            config = {{'case_insensitive': {enabled!r}, 'fields': []}}
            return re.IGNORECASE if config.get('case_insensitive', True) else 0
    '''
    tree = _compare(source, [()], extra={'re': re})
    assert not any(isinstance(node, (ast.IfExp, ast.Call)) for node in ast.walk(tree))
    returned = tree.body[0].body[-1].value
    assert isinstance(returned, ast.Attribute if enabled else ast.Constant)


@pytest.mark.parametrize('fields', [[], ['a', 'b'], ['*Unknown', 'b']])
def test_linker_autofield_config_comprehension(fields):
    source = f'''
        def f(frame):
            config = {{'fields': {fields!r}}}
            configured = [str(field) for field in config.get('fields', [])]
            explicit = [field for field in configured if field != '*Unknown' and field in frame.columns]
            if '*Unknown' in configured:
                explicit.extend(column for column in frame.columns if column not in explicit)
            return explicit or list(frame.columns)
    '''
    tree = _compare(source, [(SimpleNamespace(columns=['b', 'c']),)])
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                   and node.func.attr == 'get' for node in ast.walk(tree))
    if not fields:
        assert not any(isinstance(node, (ast.If, ast.ListComp, ast.BoolOp)) for node in ast.walk(tree))


@pytest.mark.parametrize('expression', [
    'False or flag', 'True and flag', '[] or flag or False',
    'True and flag and False', 'False and flag', 'True or flag',
    'flag and False and missing()', 'flag or True or missing()',
])
def test_partial_boolean_reduction_preserves_short_circuit(expression):
    _compare(f'def f(flag):\n    return {expression}', [(False,), (True,), (0,), (3,)])


@pytest.mark.parametrize('expression', [
    '[str(x) for x in (1, 2, 3)]',
    '[(x, y) for x in (1, 2) for y in (3, 4) if y > x]',
    '{x: x * 2 for x in (1, 2)}',
    '[missing() for x in []]',
    '[x for x, y in [(1, 2), (3, 4)]]',
    '[x for x, y in [(1,)]]',
    '[x for x in [1] if y for y in []]',
    '[x for x in [y] for y in []]',
    '[(y := x) for x in (1, 2)]',
])
def test_pure_comprehension_scope_unpacking_and_failures(expression):
    _compare(f'def f():\n    y = 9\n    result = {expression}\n    return result, y', [()])


def test_comprehension_opaque_body_cannot_freeze_its_mutable_iterator():
    _compare('''
        def f():
            config = {'items': [1, 2]}
            result = [config['items'].pop() for item in config['items']]
            return result, config
    ''', [()])
    _compare('''
        def f():
            config = {'items': [[]]}
            result = [item for item in config['items']]
            result[0].append(1)
            return config
    ''', [()])


def test_dead_nested_annotation_walrus_preserves_outer_local():
    _compare('''
        def f():
            if False:
                def inner(value: (x := int)):
                    pass
            return x
    ''', [()], extra={'x': 99})


def test_exception_with_and_match_regions_invalidate_bindings():
    _compare('''
        def f(flag):
            x = 1
            match flag:
                case [x]:
                    pass
            return x
    ''', [([],), ([2],)])
    _compare('''
        from contextlib import nullcontext
        def f():
            x = 1
            with nullcontext(2) as x:
                pass
            return x
    ''', [()])


def test_other_sensitive_functions_do_not_disable_plain_module_functions():
    source = '''
        def generator():
            yield 1
        def f():
            if True:
                return 2 + 3
    '''
    tree = _compare(source, [()])
    assert isinstance(tree.body[1].body[0], ast.Return)
    assert ast.literal_eval(tree.body[1].body[0].value) == 5

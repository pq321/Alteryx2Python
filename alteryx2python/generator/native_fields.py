"""Compile declared field conversions; type dispatch belongs to the compiler."""
from alteryx2python.tools.field_contracts import field_contract, INTEGER_BYTES, STRING_TYPES, _fixed_decimal


def coerce(compiler, series, dtype, size=None):
    contract = field_contract(dtype, size)
    if not contract:
        return series + '.copy()'
    width = contract['size']
    if dtype in STRING_TYPES:
        compiler.linker.imports.add('import warnings')
        compiler.linker.definitions['bounded_text'] = '''def bounded_text(values, width, kind, ansi=False):
    values = values.astype('string')
    if ansi:
        values = values.map(lambda value: value if pd.isna(value) else value.encode('latin-1', errors='replace').decode('latin-1')).astype('string')
    if values.str.len().gt(width).fillna(False).any():
        warnings.warn(f'{kind} values truncated to {width} characters', RuntimeWarning, stacklevel=2)
    return values.str.slice(0, width)'''
        return f'bounded_text({series}, {width!r}, {dtype!r}' + (', ansi=True)' if dtype in {'String', 'V_String'} else ')')
    if dtype in INTEGER_BYTES:
        compiler.linker.imports.update({'from decimal import Decimal, InvalidOperation', 'import warnings'})
        compiler.linker.definitions['nullable_integer'] = '''def nullable_integer(values, dtype, minimum, maximum):
    converted = []
    for value in values:
        if value is None or pd.isna(value):
            converted.append(pd.NA)
            continue
        try:
            number = int(Decimal(str(value)))
            if not minimum <= number <= maximum:
                raise ValueError('integer overflow')
            converted.append(number)
        except (ValueError, InvalidOperation, OverflowError):
            warnings.warn(f'{"Byte" if dtype == "UInt8" else dtype} conversion overflow/invalid input; converted to null', RuntimeWarning, stacklevel=2)
            converted.append(pd.NA)
    return pd.Series(converted, index=values.index, name=values.name, dtype=dtype)'''
        bits = INTEGER_BYTES[dtype] * 8
        low, high = (0, 255) if dtype == 'Byte' else (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1)
        return f'nullable_integer({series}, {"UInt8" if dtype == "Byte" else dtype!r}, {low}, {high})'
    if dtype == 'FixedDecimal':
        function = compiler.linker.function(_fixed_decimal)
        precision, scale = map(int, width.split('.'))
        return f'pd.Series([{function}(value, {precision}, {scale}) for value in {series}], index={series}.index, name={series}.name, dtype=object)'
    mapping = {'Float': 'float32', 'Double': 'float64', 'Bool': 'boolean', 'int64': 'Int64', 'float64': 'float64', 'bool': 'boolean'}
    if dtype in mapping:
        return f'{series}.astype({mapping[dtype]!r})'
    formats = {'Date': '%Y-%m-%d', 'DateTime': '%Y-%m-%d %H:%M:%S', 'Time': '%H:%M:%S'}
    if dtype in formats:
        return f'pd.to_datetime({series}, errors="coerce").dt.strftime({formats[dtype]!r}).astype("string")'
    raise ValueError(f'Unsupported declared field type: {dtype}')


def declaration(compiler, frame, name, dtype, size=None):
    contract = field_contract(dtype, size)
    compiler.linker.definitions['declare_field'] = '''def declare_field(frame, name, declaration):
    fields = {field['name']: dict(field) for field in frame.attrs.get('alteryx_schema', [])}
    fields[name] = {'name': name, **declaration}
    frame.attrs['alteryx_schema'] = list(fields.values())'''
    return f'declare_field({frame}, {name!r}, {contract!r})'


def empty_frame(compiler, kind, config, frame, expected, target):
    lines = [f'{target} = {frame}.iloc[:0].copy()' if frame else f'{target} = pd.DataFrame()']
    if kind == 'TextInput':
        lines = [f'{target} = pd.DataFrame(columns={config["fields"]!r})']
    def fields(declarations, indent=''):
        result = []
        for field in declarations:
            name = field.get('field', field.get('name'))
            result += [indent + f'{target}[{name!r}] = pd.Series(index={target}.index, dtype=object)']
            if field.get('type'):
                result += [indent + f'{target}[{name!r}] = {coerce(compiler, f"{target}[{name!r}]", field["type"], field.get("size"))}',
                           indent + declaration(compiler, target, name, field['type'], field.get('size'))]
        return result
    if kind == 'Formula':
        lines += fields([field for field in config.get('formula_fields', []) if field.get('enabled', True)])
    expected_fields = (expected or {}).get('fields', [])
    if expected_fields:
        lines += [f'if not len({target}.columns):', *fields(expected_fields, '    ')]
    return lines

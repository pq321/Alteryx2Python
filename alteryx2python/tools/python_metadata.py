"""Dataframe metadata boundaries for saved Python Tool programs."""
from __future__ import annotations

import pandas as pd

from alteryx2python.tools.field_contracts import DEFAULT_SIZES, set_field_contract


def dataframe_metadata(frame):
    declared = {item['name']: item for item in frame.attrs.get('alteryx_schema', [])}
    result = {}
    for name in frame.columns:
        field = declared.get(name, {})
        dtype = field.get('type')
        if dtype is None:
            dtype = {'bool': 'Bool', 'boolean': 'Bool', 'uint8': 'Byte', 'UInt8': 'Byte',
                     'int16': 'Int16', 'Int16': 'Int16', 'int32': 'Int32', 'Int32': 'Int32',
                     'int64': 'Int64', 'Int64': 'Int64', 'float32': 'Float', 'float64': 'Double',
                     'object': 'V_WString', 'str': 'V_WString', 'string': 'V_WString'}.get(str(frame[name].dtype))
        if dtype is None:
            raise ValueError(f'Python Tool metadata type needs a mapping: {frame[name].dtype}')
        length = field.get('size', 2147483647 if dtype == 'V_WString' else DEFAULT_SIZES.get(dtype))
        if dtype == 'FixedDecimal':
            length = tuple(map(int, str(length).split('.')))
        result[name] = {'name': name, 'type': dtype, 'length': length}
        for key in ('source', 'description'):
            result[name][key] = field.get(key)
    return result


def write_dataframe_metadata(frame, columns):
    if not isinstance(frame, pd.DataFrame):
        raise TypeError('Python Tool write requires a dataframe')
    if not isinstance(columns, (dict, list)):
        raise TypeError('Python Tool columns must be a mapping or list')
    output = frame.copy()
    renames, declarations = {}, []
    declared = {item['name']: item for item in frame.attrs.get('alteryx_schema', [])}
    for index, name in enumerate(frame.columns):
        supplied = columns.get(name, {}) if isinstance(columns, dict) else columns[index] if index < len(columns) else {}
        if not isinstance(supplied, dict) or set(supplied) - {'name', 'type', 'length', 'source', 'description'}:
            raise ValueError('Unsupported Python Tool column metadata')
        if 'type' in supplied:
            dtype = {'Boolean': 'Bool', 'Fixed Decimal': 'FixedDecimal'}.get(supplied['type'], supplied['type'])
            defaults = {'name': name, 'type': dtype, 'length': DEFAULT_SIZES.get(dtype),
                        **{key: declared.get(name, {}).get(key) for key in ('source', 'description')}}
        else:
            defaults = dataframe_metadata(frame[[name]])[name]
        field = {**defaults, **supplied}
        dtype = {'Boolean': 'Bool', 'Fixed Decimal': 'FixedDecimal'}.get(field['type'], field['type'])
        size = field['length']
        if isinstance(size, (list, tuple)):
            if not 1 <= len(size) <= 2:
                raise ValueError('Invalid Python Tool column length')
            size = '.'.join(map(str, size)) if dtype == 'FixedDecimal' else size[0]
        # Numeric storage widths belong to the output type, not the input type.
        if 'type' in supplied and 'length' not in supplied:
            size = DEFAULT_SIZES.get(dtype)
        set_field_contract(output, name, dtype, size)
        renames[name] = field['name']
        declaration = next(item for item in output.attrs['alteryx_schema'] if item['name'] == name).copy()
        declaration['name'] = field['name']
        declaration.update({key: field[key] for key in ('source', 'description') if field.get(key) is not None})
        declarations.append(declaration)
    if len(set(renames.values())) != len(renames):
        raise ValueError('Python Tool output column names must be unique')
    output = output.rename(columns=renames)
    output.attrs['alteryx_schema'] = declarations
    return output

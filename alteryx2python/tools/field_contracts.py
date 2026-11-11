"""Declared field widths for Select and Formula, shared by both compilers."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import warnings

import pandas as pd


INTEGER_BYTES = {'Byte': 1, 'Int16': 2, 'Int32': 4, 'Int64': 8}
STRING_TYPES = {'String', 'V_String', 'WString', 'V_WString', 'string'}
DEFAULT_SIZES = {'String': 254, 'WString': 254, 'V_String': 65535, 'V_WString': 65535,
                 'FixedDecimal': '19.6', 'Float': 4, 'Double': 8, 'Bool': 1,
                 'Date': 10, 'Time': 8, 'DateTime': 19, **INTEGER_BYTES}


def field_contract(dtype, size=None):
    if not dtype:
        return None
    size = DEFAULT_SIZES.get(dtype) if size in (None, '') else size
    if dtype in INTEGER_BYTES or dtype in {'Float', 'Double', 'Bool'}:
        expected = DEFAULT_SIZES[dtype]
        if int(size) != expected:
            raise ValueError(f'{dtype} has fixed storage size {expected} bytes, not {size}')
        size = expected
    elif dtype in STRING_TYPES:
        size = int(size or 65535)
        if size <= 0 or (dtype in {'String', 'WString'} and size > 8192):
            raise ValueError(f'Invalid {dtype} width: {size}')
    elif dtype == 'FixedDecimal':
        parts = str(size).split('.')
        precision, scale = int(parts[0]), int(parts[1]) if len(parts) == 2 else 0
        if len(parts) > 2 or not 1 <= precision <= 50 or not 0 <= scale < precision:
            raise ValueError(f'Invalid FixedDecimal size: {size}')
        size = f'{precision}.{scale}'
    return {'type': dtype, 'size': size}


def _fixed_decimal(value, width, scale):
    if value is None or pd.isna(value):
        return None
    try:
        with localcontext() as context:
            context.prec = 60
            number = Decimal(str(value)).quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)
        if not number.is_finite() or len(format(number, 'f')) > width:
            raise InvalidOperation
        return number
    except (InvalidOperation, ValueError):
        warnings.warn('FixedDecimal conversion overflow/invalid input; converted to null', RuntimeWarning, stacklevel=2)
        return None


def coerce_field(series, dtype, size=None):
    contract = field_contract(dtype, size)
    if contract is None:
        return series.copy()
    size = contract['size']
    if dtype in STRING_TYPES:
        result = series.astype('string')
        if dtype in {'String', 'V_String'}:
            result = result.map(lambda value: value if pd.isna(value) else value.encode('latin-1', errors='replace').decode('latin-1')).astype('string')
        too_long = result.str.len().gt(size).fillna(False)
        if too_long.any():
            warnings.warn(f'{dtype} values truncated to {size} characters', RuntimeWarning, stacklevel=2)
        return result.str.slice(0, size)
    if dtype in INTEGER_BYTES:
        bits = INTEGER_BYTES[dtype] * 8
        minimum, maximum = (0, 255) if dtype == 'Byte' else (-(2 ** (bits - 1)), 2 ** (bits - 1) - 1)
        values = []
        for value in series:
            if value is None or pd.isna(value):
                values.append(pd.NA)
                continue
            try:
                number = Decimal(str(value))
                integer = int(number)
                if not minimum <= integer <= maximum:
                    raise ValueError('integer overflow')
                values.append(integer)
            except (ValueError, InvalidOperation, OverflowError):
                warnings.warn(f'{dtype} conversion overflow/invalid input; converted to null', RuntimeWarning, stacklevel=2)
                values.append(pd.NA)
        return pd.Series(values, index=series.index, name=series.name, dtype='UInt8' if dtype == 'Byte' else dtype)
    if dtype == 'FixedDecimal':
        width, scale = map(int, str(size).split('.'))
        return pd.Series([_fixed_decimal(value, width, scale) for value in series], index=series.index, name=series.name, dtype=object)
    mapping = {'Float': 'float32', 'Double': 'float64', 'Bool': 'boolean',
               'int64': 'Int64', 'float64': 'float64', 'bool': 'boolean'}
    if dtype in mapping:
        return series.astype(mapping[dtype])
    if dtype in {'Date', 'DateTime', 'Time'}:
        formats = {'Date': '%Y-%m-%d', 'DateTime': '%Y-%m-%d %H:%M:%S', 'Time': '%H:%M:%S'}
        return pd.to_datetime(series, errors='coerce').dt.strftime(formats[dtype]).astype('string')
    raise ValueError(f'Unsupported declared field type: {dtype}')


def set_field_contract(frame, name, dtype, size=None):
    frame[name] = coerce_field(frame[name], dtype, size)
    contract = field_contract(dtype, size)
    if contract:
        schemas = {item['name']: dict(item) for item in frame.attrs.get('alteryx_schema', [])}
        schemas[name] = {'name': name, **contract}
        frame.attrs['alteryx_schema'] = list(schemas.values())

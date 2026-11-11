"""Schema propagation for skipped containers without executing side effects."""
from __future__ import annotations

import pandas as pd

from alteryx2python.tools.field_contracts import set_field_contract


def skipped_frame(kind, config, frame, expected=None):
    result = frame.iloc[:0].copy() if frame is not None else pd.DataFrame()
    if kind == 'TextInput':
        result = pd.DataFrame(columns=config['fields'])
    elif kind == 'Formula':
        for field in config.get('formula_fields', []):
            if field.get('enabled', True):
                result[field['field']] = pd.Series(index=result.index, dtype=object)
                if field.get('type'):
                    set_field_contract(result, field['field'], field['type'], field.get('size'))
    fields = (expected or {}).get('fields', [])
    if fields and not len(result.columns):
        for field in fields:
            result[field['name']] = pd.Series(dtype=object)
            if field.get('type'):
                set_field_contract(result, field['name'], field['type'], field.get('size'))
    return result

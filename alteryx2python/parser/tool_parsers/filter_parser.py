from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, text, child, as_list
import json


def parse_filter_config(raw_config: dict[str, Any]) -> ToolParserResult:
    normalized = {
        "expression": text(raw_config.get("Expression"), ""),
        "mode": text(raw_config.get("Mode"), "Unknown"),
    }
    if normalized['mode'] == 'Simple' and not normalized['expression']:
        simple = child(raw_config, 'Simple')
        field = text(child(simple, 'Field'))
        operator = text(child(simple, 'Operator'))
        operands = [text(item) for item in as_list(child(child(simple, 'Operands'), 'Operand'))]
        if not field or ']' in field:
            raise ValueError('Simple Filter requires a valid field name')
        if operator in {'=', '!=', '>', '>=', '<', '<='} and len(operands) == 1:
            normalized['expression'] = f'[{field}] {operator} {json.dumps(operands[0])}'
        elif operator in {'IsNull', 'IsNotNull', 'IsEmpty', 'IsNotEmpty'}:
            function = 'IsNull' if 'Null' in operator else 'IsEmpty'
            normalized['expression'] = ('!' if 'Not' in operator else '') + f'{function}([{field}])'
        elif operator in {'Contains', 'DoesNotContain'} and len(operands) == 1:
            normalized['expression'] = ('!' if operator == 'DoesNotContain' else '') + f'Contains([{field}], {json.dumps(operands[0])})'
        else:
            normalized['unsupported_operator'] = operator
    return ToolParserResult(normalized_config=normalized)

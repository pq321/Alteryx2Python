"""Static configurations for parsing and reshaping become explicit Python."""
from pprint import pformat

from alteryx2python.generator.source_linker import UnsupportedLowering


def lower_reshape(compiler, kind, config, frame):
    if kind == 'Transpose':
        from alteryx2python.comparison.schema_diff import ensure_fields_exist
        from alteryx2python.tools.transpose import transpose_fields, transpose_frame

        keys = config.get('key_fields', [])
        configured = config.get('data_fields', [])
        fields = [field['field'] for field in configured if field.get('selected') and field['field'] != '*Unknown']
        required = keys if str(config.get('error_warn', '')).lower() == 'warn' else [*keys, *fields]
        validate = compiler.linker.function(ensure_fields_exist)
        lines = [f'{validate}({frame}, {pformat(required, width=75)})'] if required else []
        select_fields = compiler.linker.function(transpose_fields)
        function = compiler.linker.function(transpose_frame)
        lines += [f'selections = {pformat(configured, width=75, sort_dicts=False)}',
                  f'data_fields = {select_fields}({frame}.columns, {keys!r}, selections)',
                  f'return {function}({frame}, {keys!r}, data_fields)']
        return lines
    if kind == 'AutoField':
        from alteryx2python.tools.autofield import _auto_convert
        function = compiler.linker.function(_auto_convert)
        fields = [str(field) for field in config.get('fields', [])]
        explicit = [field for field in fields if field != '*Unknown']
        if not fields:
            return [f'output = {frame}.copy()', 'for field in output.columns:', f'    output[field] = {function}(output[field])', 'return output']
        lines = [f'output = {frame}.copy()', f'fields = [field for field in {explicit!r} if field in output.columns]']
        if '*Unknown' in fields:
            lines += ['fields.extend(column for column in output.columns if column not in fields)']
        return lines + ['for field in fields or list(output.columns):', f'    output[field] = {function}(output[field])', 'return output']
    if kind == 'RegEx':
        from alteryx2python.tools.regex import _replacement
        compiler.linker.imports.add('import re')
        field, method = config.get('field', ''), config.get('method', 'Match')
        flags = 're.IGNORECASE' if config.get('case_insensitive', True) else '0'
        lines = [f'output = {frame}.copy()', f'pattern = re.compile({config.get("regex_expression", "")!r}, flags={flags})']
        if method == 'Match':
            lines += [f'output[{config.get("match_field", field + "_Matched")!r}] = [pattern.search("" if pd.isna(value) else str(value)) is not None for value in output[{field!r}]]']
        elif method == 'Replace':
            replacement = compiler.linker.function(_replacement)
            fallback = 'text' if config.get('copy_unmatched', True) else '""'
            lines += ['values = []', f'for value in output[{field!r}]:', '    text = "" if pd.isna(value) else str(value)',
                      '    match = pattern.search(text)', f'    values.append({replacement}({config.get("replace_expression", "")!r}, match) if match else {fallback})',
                      f'output[{field!r}] = values']
        elif method in {'ParseSimple', 'ParseComplex'}:
            settings = config.get('parse_simple', {})
            names = ([str(name) for name in config.get('parse_complex_fields', [])] if method == 'ParseComplex' else
                     [str(settings.get('root_name', field)) + str(index) for index in range(1, int(settings.get('num_fields', 1)) + 1)])
            for name in names:
                lines += [f'output[{name!r}] = ""']
            lines += [f'for index, value in output[{field!r}].items():', '    text = "" if pd.isna(value) else str(value)']
            if method == 'ParseComplex':
                lines += ['    match = pattern.search(text)', '    if match is None:', '        continue', '    parts = match.groups()']
            else:
                lines += [f'    parts = [part if isinstance(part, str) else part[0] for part in pattern.findall(text)][: {len(names)}]']
            lines += [f'    for name, part in zip({names!r}, parts):', '        output.at[index, name] = "" if part is None else part']
        else:
            raise UnsupportedLowering(f'Unsupported RegEx method: {method}')
        return lines + ['return output']
    if kind == 'CrossTab':
        from alteryx2python.tools.crosstab import crosstab_methods, pivot_crosstab

        groups, header, data = config.get('group_fields', []), config.get('header_field', ''), config.get('data_field', '')
        method = str(config.get('method', 'First')).lower()
        if not header or not data:
            raise UnsupportedLowering('CrossTab requires header and data fields')
        if methods := config.get('methods'):
            try:
                methods = crosstab_methods(methods)
            except (NotImplementedError, ValueError) as exc:
                raise UnsupportedLowering(str(exc)) from exc
            pivot = compiler.linker.function(pivot_crosstab)
            return [f'return {pivot}({frame}, {groups!r}, {header!r}, {data!r}, {methods!r}, '
                    f'{config.get("separator", ",")!r}, {config.get("field_size")!r})']
        numeric = 'pd.to_numeric(pd.Series(values), errors="coerce")'
        aggregates = {'first': 'values[0]', 'last': 'values[-1]', 'count': 'len(values)',
                      'sum': numeric + '.sum(min_count=1)', 'avg': numeric + '.mean()', 'average': numeric + '.mean()',
                      'min': numeric + '.min()', 'max': numeric + '.max()', 'median': numeric + '.median()',
                      'concat': f'{config.get("separator", ",")!r}.join(str(value) for value in values if value is not None and not pd.isna(value))'}
        aggregates['concatenate'] = aggregates['concat']
        if method not in aggregates:
            raise UnsupportedLowering(f'Unsupported CrossTab method: {method}')
        return [f'{frame}[{groups + [header, data]!r}]',
                f'headers = list(dict.fromkeys({frame}[{header!r}].dropna().astype(str)))', 'grouped_rows = {}', 'cells = {}',
                f'for row in {frame}.to_dict("records"):', f'    key = tuple(row[field] for field in {groups!r})',
                f'    grouped_rows.setdefault(key, {{field: row[field] for field in {groups!r}}})', f'    header = row[{header!r}]',
                '    if not pd.isna(header):', f'        cells.setdefault((key, str(header)), []).append(row[{data!r}])',
                'rows = []', 'for key, row in grouped_rows.items():', '    for header in headers:',
                f'        if header in {groups!r}:', '            continue', '        values = cells.get((key, header))',
                f'        row[header] = {aggregates[method]} if values else None', '    rows.append(row)',
                f'output = pd.DataFrame(rows, columns={groups!r} + headers)', 'return output.astype(object).where(pd.notna(output), None)']
    return None

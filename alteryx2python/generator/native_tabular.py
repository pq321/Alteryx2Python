"""Configuration-specific pandas templates shared by every compiled workflow."""
from alteryx2python.generator.native_fields import coerce
from alteryx2python.generator.source_linker import UnsupportedLowering
from alteryx2python.tools.field_contracts import field_contract


def lower_tabular(compiler, kind, config, frame):
    if kind == 'Select':
        from alteryx2python.tools.select import _normalize_select_fields, _expected_output_columns
        fields = _normalize_select_fields(config)
        explicit = [field['source'] for field in fields if field['source'] != '*Unknown']
        selected = [field for field in fields if field['selected'] and field['source'] != '*Unknown']
        names = [field['rename'] for field in selected]
        if len(set(names)) != len(names):
            raise UnsupportedLowering('Duplicate selected output names')
        unknown = any(field['source'] == '*Unknown' and field['selected'] for field in fields)
        lines = ['columns = {}', 'names = []'] if unknown else []
        fixed_columns = []
        for field in fields:
            if not field['selected']:
                continue
            source, target = field['source'], field['rename']
            if source == '*Unknown':
                lines += [f'for column in {frame}.columns:', f'    if column not in {explicit!r} and column not in columns:',
                          '        names.append(column)', f'        columns[column] = {frame}[column].copy()']
            else:
                expression = coerce(compiler, f"{frame}[{source!r}]", field["dtype"], field.get('size'))
                if unknown:
                    lines += [f'names.append({target!r})', f'columns[{target!r}] = {expression}']
                else:
                    fixed_columns.append(f'{target!r}: {expression}')
        if unknown:
            lines += ['if len(set(names)) != len(names):', '    raise ValueError("Duplicate output field names")',
                      f'output = pd.DataFrame(columns, index={frame}.index)']
        else:
            lines += [f'output = pd.DataFrame({{{", ".join(fixed_columns)}}}, index={frame}.index)']
        order = _expected_output_columns(config.get('expected_output_schema'))
        if order:
            lines += [f'ordered = [name for name in {order!r} if name in output.columns]',
                      'output = output.reindex(columns=ordered + [name for name in output.columns if name not in ordered])']
        declarations = {field['rename']: field_contract(field['dtype'], field.get('size')) for field in selected if field['dtype']}
        if len(declarations) == len(selected) and not any(field['source'] == '*Unknown' and field['selected'] for field in fields):
            schema = [{'name': field['rename'], **declarations[field['rename']]} for field in selected]
            lines += [f'output.attrs["alteryx_schema"] = {schema!r}']
            if order:
                lines += ['by_name = {field["name"]: field for field in output.attrs["alteryx_schema"]}',
                          'output.attrs["alteryx_schema"] = [by_name[name] for name in output.columns]']
        else:
            renames = {field['rename']: field['source'] for field in selected}
            lines += [f'inherited = {{field["name"]: field for field in {frame}.attrs.get("alteryx_schema", [])}}',
                      'schema = []', 'for name in output.columns:', f'    source = {renames!r}.get(name, name)',
                      f'    declaration = {declarations!r}.get(name, inherited.get(source))',
                      '    if declaration:', '        schema.append({**declaration, "name": name})',
                      'output.attrs["alteryx_schema"] = schema']
        return lines + ['return output']
    if kind == 'Sort':
        from alteryx2python.tools.sort import _is_ascending
        fields = config.get('sort_fields', [])
        if not fields:
            raise UnsupportedLowering('Sort requires fields')
        return [f'return {frame}.sort_values(by={[field["field"] for field in fields]!r}, ascending={[_is_ascending(field.get("order", "Ascending")) for field in fields]!r}, kind="mergesort").reset_index(drop=True)']
    if kind == 'Unique':
        subset = config.get('unique_fields') or None
        return [f'duplicate = {frame}.duplicated(subset={subset!r}, keep="first")', f'return {frame}.loc[~duplicate].copy(), {frame}.loc[duplicate].copy()']
    if kind == 'RecordID':
        from alteryx2python.tools.recordid import TYPE_MAP
        field, start, position = config.get('field_name', 'RecordID'), int(config.get('start_value', 1)), int(config.get('position', 0))
        dtype, groups = config.get('field_type', 'Int32'), config.get('group_fields', [])
        if dtype not in TYPE_MAP or position not in (0, 1):
            raise UnsupportedLowering('Unsupported RecordID type/position')
        lines = [f'output = {frame}.copy()']
        if groups:
            lines += [f'output[{field!r}] = (output.groupby({groups!r}, sort=False, dropna=False).cumcount() + {start}).astype({dtype!r})']
        else:
            lines += [f'output[{field!r}] = pd.Series(range({start}, {start} + len(output)), index=output.index, dtype={dtype!r})']
        if position == 0:
            lines += [f'output = output[[{field!r}] + [name for name in output.columns if name != {field!r}]]']
        return lines + ['return output']
    if kind == 'Sample':
        mode, n = str(config.get('mode', 'First')).lower(), int(config.get('n', 0))
        if n < 0:
            raise UnsupportedLowering('Sample N must be non-negative')
        def sample(value):
            if mode in {'first', 'last'}:
                return f'{value}.{"head" if mode == "first" else "tail"}({n}).copy()'
            if mode in {'sample', 'everynth'}:
                return f'{value}.iloc[::{n}].copy()' if n else f'{value}.iloc[:0].copy()'
            if mode == 'npercent':
                return f'{value}.head(int(len({value}) * ({n} / 100))).copy()'
            if mode == 'random':
                return f'{value}.sample(n=min({n}, len({value})), random_state=0).sort_index().copy()'
            raise UnsupportedLowering(f'Unsupported Sample mode: {mode}')
        groups = config.get('group_fields', [])
        if not groups:
            return ['return ' + sample(frame)]
        return [f'pieces = [{sample("group")} for _, group in {frame}.groupby({groups!r}, sort=False, dropna=False)]',
                f'return pd.concat(pieces, ignore_index=True) if pieces else {frame}.iloc[:0].copy()']
    if kind in {'RunningTotal', 'Rank'}:
        groups = config.get('group_by_fields' if kind == 'RunningTotal' else 'group_fields', [])
        if kind == 'RunningTotal':
            lines = [f'output = {frame}.copy()']
            for field in config.get('running_total_fields', []):
                numeric = f'pd.to_numeric(output[{field!r}], errors="coerce").fillna(0)'
                grouped = f'.groupby([output[field] for field in {groups!r}], sort=False)' if groups else ''
                lines += [f'output[{"RunningTotal_" + field!r}] = {numeric}{grouped}.cumsum()']
        else:
            from alteryx2python.tools.rank import RANK_METHODS
            fields, modes = config.get('sort_fields', []), config.get('ranking_modes', ['Ordinal'])
            if not fields:
                raise UnsupportedLowering('Rank requires sort fields')
            by = [field['field'] for field in fields]
            ascending = [field.get('order', 'Ascending').lower() != 'descending' for field in fields]
            lines = [f'output = {frame}.sort_values(by={by!r}, ascending={ascending!r}, kind="mergesort").reset_index(drop=True)']
            for mode in modes:
                column = 'Rank' if len(modes) == 1 else 'Rank_' + mode
                grouped = f'.groupby([output[field] for field in {groups!r}], sort=False)' if groups else ''
                lines += [f'output[{column!r}] = pd.to_numeric(output[{by[0]!r}], errors="coerce"){grouped}.rank(method={RANK_METHODS.get(mode, "first")!r}, ascending={ascending[0]!r}).astype("Float64")']
                if mode in {'Ordinal', 'Dense', 'Standard', 'Competition'}:
                    lines += [f'output[{column!r}] = output[{column!r}].astype("Int64")']
        return lines + ['return output']
    if kind == 'Summarize':
        from alteryx2python.tools import summarize
        fields = config.get('summarize_fields', [])
        if not fields:
            raise UnsupportedLowering('Summarize requires fields')
        groups = [field['field'] for field in fields if field['action'] == 'GroupBy']
        entries = []
        for field in [field for field in fields if field['action'] == 'GroupBy'] + [field for field in fields if field['action'] != 'GroupBy']:
            column, action = field['field'], field['action']
            values = f'group[{column!r}]'
            numeric = f'pd.to_numeric({values}, errors="coerce")'
            operations = {'Sum': numeric + '.sum()', 'Avg': numeric + '.mean()', 'Median': numeric + '.median()',
                          'StdDev': numeric + '.std()', 'Variance': numeric + '.var()', 'Count': f'int(len({values}))',
                          'Min': values + '.min()', 'Max': values + '.max()', 'GroupBy': f'group.iloc[0][{column!r}]',
                          'First': f'({values}.iloc[0] if len({values}) else None)', 'Last': f'({values}.iloc[-1] if len({values}) else None)'}
            if action in operations:
                expression = operations[action]
            elif action in {'Mode', 'Longest', 'Shortest'}:
                expression = f'{compiler.linker.function(getattr(summarize, "_" + action.lower()))}({values})'
            elif action in {'CountBlank', 'CountNonBlank', 'Concat'}:
                blank = compiler.linker.function(summarize._is_blank)
                if action == 'Concat':
                    expression = f'{field.get("concat_start", "")!r} + {field.get("separator", "")!r}.join(str(value) for value in {values} if not {blank}(value)) + {field.get("concat_end", "")!r}'
                else:
                    expression = f'int(({"~" if action == "CountNonBlank" else ""}{values}.map({blank})).sum())'
            else:
                raise UnsupportedLowering(f'Unsupported Summarize action: {action}')
            entries.append(f'{field.get("rename") or column!r}: {expression}')
        row = '{' + ', '.join(entries) + '}'
        if groups:
            return [f'return pd.DataFrame([{row} for _, group in {frame}.groupby({groups!r}, sort=False, dropna=False)])']
        return [f'group = {frame}', f'return pd.DataFrame([{row}])']
    if kind == 'TextToColumns':
        from alteryx2python.tools.texttocolumns import _delimiter_pattern
        field, delimiters = config.get('field', ''), str(config.get('delimiters', ''))
        compiler.linker.imports.add('import re')
        split = f're.split({_delimiter_pattern(delimiters)!r}, text)' if delimiters else '[text]'
        if int(config.get('flags', 0)) & 1:
            return ['rows = []', f'for record in {frame}.to_dict("records"):',
                    f'    text = "" if pd.isna(record[{field!r}]) else str(record[{field!r}])',
                    f'    for part in {split}:', f'        rows.append({{**record, {field!r}: part}})', f'return pd.DataFrame(rows, columns={frame}.columns)']
        count = int(config.get('num_fields', 1))
        root = str(config.get('root_name', field))
        names = [root + str(index) for index in range(1, count + 1)]
        lines = [f'output = {frame}.copy()', f'parts_by_column = {{name: [] for name in {names!r}}}',
                 f'for value in {frame}[{field!r}]:', '    text = "" if pd.isna(value) else str(value)', f'    parts = {split}']
        if str(config.get('error_handling', 'Last')).lower() == 'last':
            lines += [f'    if len(parts) > {count}:', f'        parts = parts[:{count - 1}] + [{delimiters[:1]!r}.join(parts[{count - 1}:])]']
        lines += [f'    padded = parts[:{count}] + [""] * max(0, {count} - len(parts))', f'    for name, part in zip({names!r}, padded):',
                  '        parts_by_column[name].append(part)', 'for name, values in parts_by_column.items():', '    output[name] = values', 'return output']
        return lines
    return None

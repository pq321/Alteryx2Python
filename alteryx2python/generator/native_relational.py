"""Resolve keys, selections and stream ordering before emitting relational code."""
from alteryx2python.generator.native_fields import coerce
from alteryx2python.generator.source_linker import UnsupportedLowering


def lower_relational(compiler, kind, config, arguments):
    if kind == 'Union':
        from alteryx2python.tools.union import _ordered_input_anchors, _expected_output_columns
        ordered = _ordered_input_anchors(arguments, config)
        if not ordered:
            raise UnsupportedLowering('Union needs input data')
        frames = '[' + ', '.join(arguments[name] for name in ordered) + ']'
        lines = [f'frames = {frames}']
        mode = str(config.get('mode', 'ByName')).lower()
        if mode == 'byname':
            lines += ['columns = list(dict.fromkeys(column for frame in frames for column in frame.columns))',
                      'aligned = [frame.reindex(columns=columns) for frame in frames]']
        elif mode == 'bypos':
            expected = _expected_output_columns(config.get('expected_output_schema'))
            lines += [f'columns = {expected!r}' if expected else 'columns = list(frames[0].columns)',
                      'aligned = []', 'for frame in frames:', '    renamed = frame.copy()',
                      '    renamed.columns = columns[:len(renamed.columns)]', '    aligned.append(renamed.reindex(columns=columns))']
        else:
            raise UnsupportedLowering(f'Unsupported Union mode: {mode}')
        return lines + ['combined = pd.concat(aligned, ignore_index=True)', 'return combined.astype(object).where(pd.notna(combined), None)']
    if kind == 'Join':
        from alteryx2python.tools.join import _join_field
        left, right = arguments['Left'], arguments['Right']
        left_key, right_key = _join_field(config, 'Left'), _join_field(config, 'Right')
        if not left_key or not right_key:
            raise UnsupportedLowering('Join requires both join keys')
        lines = [f'left = {left}.reset_index(drop=True).add_prefix("Left_")',
                 f'right = {right}.reset_index(drop=True).add_prefix("Right_")',
                 f'left["__left_index"] = range(len({left}))', f'right["__right_index"] = range(len({right}))',
                 f'merged = left.merge(right, how="inner", left_on={"Left_" + left_key!r}, right_on={"Right_" + right_key!r}, sort=True)',
                 f'joined = pd.concat([merged[["Left_" + column for column in {left}.columns]], merged[["Right_" + column for column in {right}.columns]]], axis=1)']
        fields = config.get('select_fields', [])
        if fields:
            selected = {str(field.get('rename', field.get('source', ''))): str(field.get('source', '')) for field in fields if field.get('selected', True) and field.get('source') != '*Unknown'}
            mapping = '{' + ', '.join(f'{name!r}: joined[{source!r}]' for name, source in selected.items()) + '}'
            lines += [f'joined = pd.DataFrame({mapping}, index=joined.index)']
        return lines + [f'unmatched_left = {left}.iloc[[index for index in range(len({left})) if index not in set(merged["__left_index"])]].reset_index(drop=True)',
                        f'unmatched_right = {right}.iloc[[index for index in range(len({right})) if index not in set(merged["__right_index"])]].reset_index(drop=True)',
                        'return joined.reset_index(drop=True), unmatched_left, unmatched_right']
    if kind == 'AppendFields':
        targets, source = arguments['Targets'], arguments['Source']
        lines = []
        if config.get('cartesian_mode', 'Error') == 'Error':
            lines += [f'if len({targets}) * len({source}) > max(len({targets}), len({source})):',
                      '    raise ValueError("AppendFields CartesianMode=Error rejects many-to-many append")']
        lines += [f'columns = list({targets}.columns) + [column if column not in {targets}.columns else "Source_" + column for column in {source}.columns]',
                  'rows = []', f'for target in {targets}.to_dict("records"):', f'    for record in {source}.to_dict("records"):',
                  '        row = dict(target)', '        for column, value in record.items():',
                  '            row[column if column not in row else "Source_" + column] = value', '        rows.append(row)',
                  'output = pd.DataFrame(rows, columns=columns)']
        fields = config.get('select_fields', [])
        if fields:
            lines += ['selected = {}', 'explicit = set()']
            for field in fields:
                name = str(field['source'])
                if name == '*Unknown':
                    continue
                if name.startswith('Target_'):
                    name = name[len('Target_'):]
                    expression = repr(name)
                elif name.startswith('Source_'):
                    expression = f'({name[len("Source_"):]!r} if {name[len("Source_"):]!r} not in {targets}.columns else {name!r})'
                else:
                    expression = repr(name)
                lines += [f'name = {expression}', 'explicit.add(name)']
                if field.get('selected', True):
                    rename = repr(field['rename']) if field.get('rename') else 'name'
                    lines += [f'selected[{rename}] = {coerce(compiler, "output[name]", field.get("dtype"), field.get("size"))}']
            if any(field['source'] == '*Unknown' and field.get('selected', True) for field in fields):
                lines += ['selected.update({column: output[column] for column in output.columns if column not in explicit and column not in selected})']
            lines += ['output = pd.DataFrame(selected, index=output.index)']
        return lines + ['return output']
    return None

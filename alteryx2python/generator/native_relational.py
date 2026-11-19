"""Resolve keys, selections and stream ordering before emitting relational code."""
from alteryx2python.generator.native_fields import coerce
from alteryx2python.generator.source_linker import UnsupportedLowering


def lower_relational(compiler, kind, config, arguments):
    if kind == 'Union':
        from alteryx2python.tools.union import _ordered_input_anchors, _expected_output_columns, rename_union_fields, stack_union_rows
        ordered = _ordered_input_anchors(arguments, config)
        if not ordered:
            raise UnsupportedLowering('Union needs input data')
        frames = '[' + ', '.join(arguments[name] for name in ordered) + ']'
        lines = [f'frames = {frames}']
        mode = str(config.get('mode', 'ByName')).lower()
        if mode == 'byname':
            lines += ['columns = list(dict.fromkeys(column for frame in frames for column in frame.columns))']
        elif mode == 'bypos':
            expected = _expected_output_columns(config.get('expected_output_schema'))
            rename = compiler.linker.function(rename_union_fields)
            lines += [f'columns = {expected!r}' if expected else 'columns = list(frames[0].columns)',
                      f'frames = [{rename}(frame, columns[:len(frame.columns)]) for frame in frames]']
        else:
            raise UnsupportedLowering(f'Unsupported Union mode: {mode}')
        stack = compiler.linker.function(stack_union_rows)
        return lines + [f'return {stack}(frames, columns)']
    if kind == 'Join':
        from alteryx2python.tools.join import join_frames, join_keys
        left, right = arguments['Left'], arguments['Right']
        by_position = config.get('join_by_record_pos', False)
        left_keys = [] if by_position else join_keys(config, 'Left')
        right_keys = [] if by_position else join_keys(config, 'Right')
        if not by_position and (not left_keys or len(left_keys) != len(right_keys)):
            raise UnsupportedLowering('Join requires equally many Left and Right fields')
        function = compiler.linker.function(join_frames)
        return [f'return {function}({left}, {right}, {left_keys!r}, {right_keys!r}, '
                f'{config.get("select_fields", [])!r}, {config.get("order_changed", True)!r}, {by_position!r})']
    if kind == 'AppendFields':
        from alteryx2python.tools.appendfields import append_rows

        targets, source = arguments['Targets'], arguments['Source']
        lines = []
        if config.get('cartesian_mode', 'Error') == 'Error':
            lines += [f'if len({targets}) * len({source}) > max(len({targets}), len({source})):',
                      '    raise ValueError("AppendFields CartesianMode=Error rejects many-to-many append")']
        fields = config.get('select_fields', [])
        selection = [{key: field[key] for key in ('source', 'selected', 'rename') if key in field} for field in fields]
        append = compiler.linker.function(append_rows)
        lines.append(f'output, names = {append}({targets}, {source}, {selection!r}, {bool(config.get("order_changed"))!r})')
        for field in fields:
            reference, dtype = field['source'], field.get('dtype')
            if dtype and field.get('selected', True) and reference != '*Unknown':
                conversion = coerce(compiler, 'output[name]', dtype, field.get('size'))
                lines += [f'if {reference!r} in names:', f'    name = names[{reference!r}]',
                          f'    output[name] = {conversion}']
        return lines + ['return output']
    return None

"""Editable Python generated with deterministic templates. See the sidecar manifest."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
import hashlib
import html
import math
import mimetypes
import os
import pandas as pd
import re
import shlex
import shutil
import subprocess
import warnings

def run_workflow(*, input_dir=None, output_dir=None, allowed_commands=(), event_working_dir=None, command_working_dir=None, minimum_sepal_length=5):
    input_dir = Path(input_dir or Path(__file__).resolve().parent).resolve()
    output_dir = Path(output_dir or Path(__file__).resolve().parent / 'output').resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    minimum_sepal_length = float(minimum_sepal_length)
    if not math.isfinite(minimum_sepal_length):
        raise ValueError('Invalid numeric input: minimum_sepal_length')
    minimum_sepal_length = int(minimum_sepal_length) if minimum_sepal_length.is_integer() else minimum_sepal_length
    if minimum_sepal_length < 0.0:
        raise ValueError('Below input minimum: minimum_sepal_length')
    if minimum_sepal_length > 10.0:
        raise ValueError('Above input maximum: minimum_sepal_length')
    try:
        with warnings.catch_warnings(record=True) as workflow_warnings:
            warnings.simplefilter('always', RuntimeWarning)
            _delivery_run_checked_command(str(input_dir / 'before.bat') if (input_dir / 'before.bat').is_file() else 'before.bat', '', event_working_dir or input_dir / '', None, '', '', allowed_commands, 30)
            path = input_dir / 'data/iris.data'
            load_measurements_data = pd.read_csv(path, delimiter=',', skiprows=0, nrows=None, header=None, encoding=None)
            load_measurements_data.columns = [f'F{index}' for index in range(1, len(load_measurements_data.columns) + 1)]
            load_report_groups_data = pd.DataFrame({'species': pd.Series(['setosa', 'versicolor', 'virginica'], dtype='object'), 'report_group': pd.Series(['A', 'B', 'C'], dtype='object')})
            build_report_title_data = _delivery_report_text('Iris measurement report', 'Report')
            normalize_species_data = prepare_normalize_species(load_measurements_data)
            calculate_report_fields_data = normalize_species_data.copy()
            calculate_report_fields_data['measurement_key'] = [_add_nullable(_add_nullable(row['species'], '|'), _functions_to_string(row['RecordID'])) for row in calculate_report_fields_data.to_dict('records')]
            calculate_report_fields_data['measurement_key'] = bounded_text(calculate_report_fields_data['measurement_key'], 64, 'V_WString')
            declare_field(calculate_report_fields_data, 'measurement_key', {'type': 'V_WString', 'size': 64})
            calculate_report_fields_data['report_date'] = ['2026-11-11'] * len(calculate_report_fields_data)
            calculate_report_fields_data['report_date'] = pd.to_datetime(calculate_report_fields_data['report_date'], errors='coerce').dt.strftime('%Y-%m-%d').astype('string')
            declare_field(calculate_report_fields_data, 'report_date', {'type': 'Date', 'size': '10'})
            calculate_report_fields_data['petal_cost'] = [row['scaled_petal_length'] * 1.25 for row in calculate_report_fields_data.to_dict('records')]
            calculate_report_fields_data['petal_cost'] = pd.Series([_field_contracts_fixed_decimal(value, 12, 2) for value in calculate_report_fields_data['petal_cost']], index=calculate_report_fields_data['petal_cost'].index, name=calculate_report_fields_data['petal_cost'].name, dtype=object)
            declare_field(calculate_report_fields_data, 'petal_cost', {'type': 'FixedDecimal', 'size': '12.2'})
            normalize_species_data[['species']]
            normalize_species_data[['sepal_length', 'petal_length']]
            data_fields = [name for name in normalize_species_data.columns if name in ['sepal_length', 'petal_length']]
            rows = [{**{name: row[name] for name in ['species']}, 'Name': field, 'Value': row[field]} for row in normalize_species_data.to_dict('records') for field in data_fields]
            reshape_measurements_long_data = pd.DataFrame(rows, columns=['species', 'Name', 'Value'])
            seeds = normalize_species_data.to_dict('records')
            rows = []
            for seed in seeds:
                row = dict(seed)
                row['replicate'] = 1
                while bool(row['replicate'] is not None and row['replicate'] <= 2):
                    rows.append(dict(row))
                    if len(rows) > 100000:
                        raise RuntimeError('GenerateRows exceeded safety limit of 100000 rows')
                    row['replicate'] = _add_nullable(row['replicate'], 1)
            generate_measurement_replicates_data = pd.DataFrame(rows)
            mask = pd.Series([bool(row['sepal_length'] is not None and minimum_sepal_length is not None and (row['sepal_length'] >= minimum_sepal_length)) for row in calculate_report_fields_data.to_dict('records')], index=calculate_report_fields_data.index)
            filter_minimum_sepal_length_matched, filter_minimum_sepal_length_unmatched = (calculate_report_fields_data.loc[mask].copy(), calculate_report_fields_data.loc[~mask].copy())
            normalize_measurement_key_data = calculate_report_fields_data.copy()
            pattern = re.compile('\\|', flags=re.IGNORECASE)
            values = []
            for value in normalize_measurement_key_data['measurement_key']:
                text = '' if pd.isna(value) else str(value)
                match = pattern.search(text)
                values.append(_regex_replacement('_', match) if match else text)
            normalize_measurement_key_data['measurement_key'] = values
            reshape_measurements_wide_data = _operation_reshape_measurements_wide(reshape_measurements_long_data)
            scale_multiple_measurements_data = generate_measurement_replicates_data.copy()
            fields = [field for field in ['sepal_length', 'petal_length'] if field in generate_measurement_replicates_data.columns]
            fields = fields or list(generate_measurement_replicates_data.columns)
            for field in fields:
                output_field = field + '_doubled'
                values = []
                for row in scale_multiple_measurements_data.to_dict('records'):
                    row['_CurrentField_'] = row[field]
                    values.append(row['_CurrentField_'] * 2)
                scale_multiple_measurements_data[output_field] = values
            split_measurement_key_data = filter_minimum_sepal_length_matched.copy()
            parts_by_column = {name: [] for name in ['key_part1', 'key_part2']}
            for value in filter_minimum_sepal_length_matched['measurement_key']:
                text = '' if pd.isna(value) else str(value)
                parts = re.split('[\\|]+', text)
                if len(parts) > 2:
                    parts = parts[:1] + ['|'.join(parts[1:])]
                padded = parts[:2] + [''] * max(0, 2 - len(parts))
                for name, part in zip(['key_part1', 'key_part2'], padded):
                    parts_by_column[name].append(part)
            for name, values in parts_by_column.items():
                split_measurement_key_data[name] = values
            macro_input_2_data = filter_minimum_sepal_length_unmatched.copy()
            infer_field_widths_data = normalize_measurement_key_data.copy()
            for field in infer_field_widths_data.columns:
                infer_field_widths_data[field] = _autofield_auto_convert(infer_field_widths_data[field])
            compare_previous_measurement_data = compare_previous_measurement_stage(scale_multiple_measurements_data)
            duplicate = split_measurement_key_data.duplicated(subset=['RecordID'], keep='first')
            deduplicate_measurements_unique, deduplicate_measurements_duplicates = (split_measurement_key_data.loc[~duplicate].copy(), split_measurement_key_data.loc[duplicate].copy())
            if not isinstance(infer_field_widths_data, pd.DataFrame):
                raise TypeError('Input anchor must contain a pandas DataFrame')
            inspect_field_contracts_data = pd.DataFrame([{'Name': column, 'Type': str(infer_field_widths_data[column].dtype), 'Size': _fieldinfo_size(infer_field_widths_data[column]), 'Scale': 0, 'Source': '', 'Description': ''} for column in infer_field_widths_data.columns])
            declared = {item['name']: item for item in infer_field_widths_data.attrs.get('alteryx_schema', [])}
            for index, column in enumerate(infer_field_widths_data.columns):
                if column in declared:
                    contract = declared[column]
                    inspect_field_contracts_data.loc[index, 'Type'] = contract['type']
                    size, _, scale = str(contract.get('size', 0)).partition('.')
                    inspect_field_contracts_data.loc[index, 'Size'] = int(size)
                    inspect_field_contracts_data.loc[index, 'Scale'] = int(scale or 0)
            blockuntildone_output, blockuntildone_output2, blockuntildone_output3 = prepare_blockuntildone(deduplicate_measurements_unique)
            macro_output_2_data = blockuntildone_output.copy()
            sequence_independent_streams_output1, sequence_independent_streams_output2 = prepare_sequence_independent_streams(blockuntildone_output2, macro_input_2_data, macro_output_2_data)
            finish_outputs_in_order_output, finish_outputs_in_order_output2, finish_outputs_in_order_output3 = prepare_finish_outputs_in_order(load_report_groups_data, sequence_independent_streams_output1)
            output = finish_outputs_in_order_output
            path = output_dir / 'species_summary.csv'
            path.parent.mkdir(parents=True, exist_ok=True)
            rendered = output.astype(object)
            for column in range(len(rendered.columns)):
                rendered.iloc[:, column] = ['' if value is None or (not isinstance(value, str) and pd.isna(value)) else str(int(value)) if isinstance(value, float) and value == int(value) and (abs(value) < 1000000000000000.0) else str(value) for value in rendered.iloc[:, column]]
            rendered.to_csv(path, index=False, header=True, sep=',', lineterminator='\r\n', encoding='latin-1')
            assemble_report_data = prepare_assemble_report(build_report_title_data, finish_outputs_in_order_output2)
            _delivery_render_html(assemble_report_data, 'Report', output_dir / 'iris_report.html')
            program = 'E:\\Automation\\Alteryx2Python\\.venv\\Scripts\\python.exe'
            if not Path(program).is_absolute() and (input_dir / program).is_file():
                program = str((input_dir / program).resolve())
            run_postprocessing_command_data = _delivery_run_checked_command(program, '-c "from pathlib import Path; Path(\\"command-proof.txt\\").write_text(\\"command completed\\n\\")"', command_working_dir or input_dir / '', finish_outputs_in_order_output3, '', '', allowed_commands)
            if len(run_postprocessing_command_data.index) > 0:
                _delivery_draft_email(assemble_report_data, 'reports@example.invalid', 'reviewer@example.invalid', 'Iris measurement report', 'Report', [output_dir / name for name in ['iris_report.html']], output_dir / 'email-27.eml')
            prepare_inspect_completion(run_postprocessing_command_data)
            output = sequence_independent_streams_output2
            path = output_dir / 'rejected_measurements.csv'
            path.parent.mkdir(parents=True, exist_ok=True)
            rendered = output.astype(object)
            for column in range(len(rendered.columns)):
                rendered.iloc[:, column] = ['' if value is None or (not isinstance(value, str) and pd.isna(value)) else str(int(value)) if isinstance(value, float) and value == int(value) and (abs(value) < 1000000000000000.0) else str(value) for value in rendered.iloc[:, column]]
            rendered.to_csv(path, index=False, header=True, sep=',', lineterminator='\r\n', encoding='latin-1')
    except Exception:
        _delivery_run_checked_command(str(input_dir / 'after.bat') if (input_dir / 'after.bat').is_file() else 'after.bat', '', event_working_dir or input_dir / '', None, '', '', allowed_commands, 30)
        raise
    else:
        _delivery_run_checked_command(str(input_dir / 'after.bat') if (input_dir / 'after.bat').is_file() else 'after.bat', '', event_working_dir or input_dir / '', None, '', '', allowed_commands, 30)
    return output_dir

def prepare_normalize_species(load_measurements_data):
    declare_measurement_fields_data = pd.DataFrame({'sepal_length': load_measurements_data['F1'].astype('float64'), 'sepal_width': load_measurements_data['F2'].astype('float64'), 'petal_length': load_measurements_data['F3'].astype('float64'), 'petal_width': load_measurements_data['F4'].astype('float64'), 'species': bounded_text(load_measurements_data['F5'], 32, 'V_WString')}, index=load_measurements_data.index)
    declare_measurement_fields_data.attrs['alteryx_schema'] = [{'name': 'sepal_length', 'type': 'Double', 'size': 8}, {'name': 'sepal_width', 'type': 'Double', 'size': 8}, {'name': 'petal_length', 'type': 'Double', 'size': 8}, {'name': 'petal_width', 'type': 'Double', 'size': 8}, {'name': 'species', 'type': 'V_WString', 'size': 32}]
    number_measurements_data = declare_measurement_fields_data.copy()
    number_measurements_data['RecordID'] = pd.Series(range(1, 1 + len(number_measurements_data)), index=number_measurements_data.index, dtype='Int64')
    number_measurements_data = number_measurements_data[['RecordID'] + [name for name in number_measurements_data.columns if name != 'RecordID']]
    macro_input_data = number_measurements_data.copy()
    calculate_species_and_scaled_petal_length_data = macro_input_data.copy()
    calculate_species_and_scaled_petal_length_data['species'] = [_functions_replace(row['species'], 'Iris-', '') for row in calculate_species_and_scaled_petal_length_data.to_dict('records')]
    calculate_species_and_scaled_petal_length_data['species'] = bounded_text(calculate_species_and_scaled_petal_length_data['species'], 24, 'V_WString')
    declare_field(calculate_species_and_scaled_petal_length_data, 'species', {'type': 'V_WString', 'size': 24})
    calculate_species_and_scaled_petal_length_data['scaled_petal_length'] = [row['petal_length'] * 2 for row in calculate_species_and_scaled_petal_length_data.to_dict('records')]
    calculate_species_and_scaled_petal_length_data['scaled_petal_length'] = calculate_species_and_scaled_petal_length_data['scaled_petal_length'].astype('float64')
    declare_field(calculate_species_and_scaled_petal_length_data, 'scaled_petal_length', {'type': 'Double', 'size': 8})
    macro_output_data = calculate_species_and_scaled_petal_length_data.copy()
    normalize_species_data = macro_output_data
    return normalize_species_data

def compare_previous_measurement_stage(scale_multiple_measurements_data):
    rows = scale_multiple_measurements_data.copy().to_dict('records')
    for row in rows:
        row['petal_delta'] = 0
    positions_by_group = {}
    for index, row in enumerate(rows):
        positions_by_group.setdefault((), []).append(index)
    for index, record in enumerate(rows):
        row = dict(record)
        positions = positions_by_group[()]
        position = positions.index(index)
        relative = position + -1
        neighbor = positions[relative] if 0 <= relative < len(positions) else None
        row['Row-1:scaled_petal_length'] = None if neighbor is None else rows[neighbor].get('scaled_petal_length')
        try:
            computed = row['scaled_petal_length'] - row['Row-1:scaled_petal_length']
        except TypeError:
            computed = None
        record['petal_delta'] = computed if computed is None or pd.isna(computed) else float(computed)
    compare_previous_measurement_data = pd.DataFrame(rows)
    return compare_previous_measurement_data

def prepare_blockuntildone(deduplicate_measurements_unique):
    sort_measurements_data = deduplicate_measurements_unique.sort_values(by=['species', 'RecordID'], ascending=[True, True], kind='mergesort').reset_index(drop=True)
    calculate_running_totals_data = sort_measurements_data.copy()
    calculate_running_totals_data['RunningTotal_scaled_petal_length'] = pd.to_numeric(calculate_running_totals_data['scaled_petal_length'], errors='coerce').fillna(0).groupby([calculate_running_totals_data[field] for field in ['species']], sort=False).cumsum()
    rank_measurements_data = calculate_running_totals_data.sort_values(by=['sepal_length'], ascending=[False], kind='mergesort').reset_index(drop=True)
    rank_measurements_data['Rank'] = pd.to_numeric(rank_measurements_data['sepal_length'], errors='coerce').rank(method='first', ascending=False).astype('Float64')
    rank_measurements_data['Rank'] = rank_measurements_data['Rank'].astype('Int64')
    take_report_sample_data = rank_measurements_data.head(120).copy()
    summarize_species_data = pd.DataFrame([{'species': group.iloc[0]['species'], 'mean_sepal_length': pd.to_numeric(group['sepal_length'], errors='coerce').mean(), 'measurement_count': int(len(group['RecordID'])), 'petal_total': pd.to_numeric(group['scaled_petal_length'], errors='coerce').sum()} for _, group in take_report_sample_data.groupby(['species'], sort=False, dropna=False)])
    macro_input_3_data = summarize_species_data.copy()
    blockuntildone_output, blockuntildone_output2, blockuntildone_output3 = (macro_input_3_data.copy(), macro_input_3_data.copy(), macro_input_3_data.copy())
    return (blockuntildone_output, blockuntildone_output2, blockuntildone_output3)

def prepare_sequence_independent_streams(blockuntildone_output2, macro_input_2_data, macro_output_2_data):
    sample_data = blockuntildone_output2.head(1).copy()
    calculate___benchmark_gate_data = sample_data.copy()
    calculate___benchmark_gate_data['__benchmark_gate'] = [1] * len(calculate___benchmark_gate_data)
    calculate___benchmark_gate_data['__benchmark_gate'] = nullable_integer(calculate___benchmark_gate_data['__benchmark_gate'], 'UInt8', 0, 255)
    declare_field(calculate___benchmark_gate_data, '__benchmark_gate', {'type': 'Byte', 'size': 1})
    select___benchmark_gate_data = pd.DataFrame({'__benchmark_gate': calculate___benchmark_gate_data['__benchmark_gate'].copy()}, index=calculate___benchmark_gate_data.index)
    inherited = {field['name']: field for field in calculate___benchmark_gate_data.attrs.get('alteryx_schema', [])}
    schema = []
    for name in select___benchmark_gate_data.columns:
        source = {'__benchmark_gate': '__benchmark_gate'}.get(name, name)
        declaration = {}.get(name, inherited.get(source))
        if declaration:
            schema.append({**declaration, 'name': name})
    select___benchmark_gate_data.attrs['alteryx_schema'] = schema
    if len(macro_input_2_data) * len(select___benchmark_gate_data) > max(len(macro_input_2_data), len(select___benchmark_gate_data)):
        raise ValueError('AppendFields CartesianMode=Error rejects many-to-many append')
    columns = list(macro_input_2_data.columns) + [column if column not in macro_input_2_data.columns else 'Source_' + column for column in select___benchmark_gate_data.columns]
    rows = []
    for target in macro_input_2_data.to_dict('records'):
        for record in select___benchmark_gate_data.to_dict('records'):
            row = dict(target)
            for column, value in record.items():
                row[column if column not in row else 'Source_' + column] = value
            rows.append(row)
    appendfields_data = pd.DataFrame(rows, columns=columns)
    selected = {}
    explicit = set()
    name = '__benchmark_gate' if '__benchmark_gate' not in macro_input_2_data.columns else 'Source___benchmark_gate'
    explicit.add(name)
    selected.update({column: appendfields_data[column] for column in appendfields_data.columns if column not in explicit and column not in selected})
    appendfields_data = pd.DataFrame(selected, index=appendfields_data.index)
    macro_output_3_data = appendfields_data.copy()
    sequence_independent_streams_output1, sequence_independent_streams_output2 = (macro_output_2_data, macro_output_3_data)
    return (sequence_independent_streams_output1, sequence_independent_streams_output2)

def prepare_finish_outputs_in_order(load_report_groups_data, sequence_independent_streams_output1):
    left = sequence_independent_streams_output1.reset_index(drop=True).add_prefix('Left_')
    right = load_report_groups_data.reset_index(drop=True).add_prefix('Right_')
    left['__left_index'] = range(len(sequence_independent_streams_output1))
    right['__right_index'] = range(len(load_report_groups_data))
    merged = left.merge(right, how='inner', left_on='Left_species', right_on='Right_species', sort=True)
    joined = pd.concat([merged[['Left_' + column for column in sequence_independent_streams_output1.columns]], merged[['Right_' + column for column in load_report_groups_data.columns]]], axis=1)
    joined = pd.DataFrame({'Left_species': joined['Left_species'], 'Left_mean_sepal_length': joined['Left_mean_sepal_length'], 'Left_measurement_count': joined['Left_measurement_count'], 'Left_petal_total': joined['Left_petal_total'], 'Right_report_group': joined['Right_report_group']}, index=joined.index)
    unmatched_left = sequence_independent_streams_output1.iloc[[index for index in range(len(sequence_independent_streams_output1)) if index not in set(merged['__left_index'])]].reset_index(drop=True)
    unmatched_right = load_report_groups_data.iloc[[index for index in range(len(load_report_groups_data)) if index not in set(merged['__right_index'])]].reset_index(drop=True)
    join_report_groups_join, join_report_groups_left, join_report_groups_right = (joined.reset_index(drop=True), unmatched_left, unmatched_right)
    declare_report_fields_data = pd.DataFrame({'Left_species': bounded_text(join_report_groups_join['Left_species'], 24, 'V_WString'), 'Left_mean_sepal_length': join_report_groups_join['Left_mean_sepal_length'].astype('float64'), 'Left_measurement_count': nullable_integer(join_report_groups_join['Left_measurement_count'], 'Int32', -2147483648, 2147483647), 'Left_petal_total': join_report_groups_join['Left_petal_total'].astype('float64'), 'Right_report_group': bounded_text(join_report_groups_join['Right_report_group'], 8, 'V_WString')}, index=join_report_groups_join.index)
    declare_report_fields_data.attrs['alteryx_schema'] = [{'name': 'Left_species', 'type': 'V_WString', 'size': 24}, {'name': 'Left_mean_sepal_length', 'type': 'Double', 'size': 8}, {'name': 'Left_measurement_count', 'type': 'Int32', 'size': 4}, {'name': 'Left_petal_total', 'type': 'Double', 'size': 8}, {'name': 'Right_report_group', 'type': 'V_WString', 'size': 8}]
    finish_outputs_in_order_output, finish_outputs_in_order_output2, finish_outputs_in_order_output3 = (declare_report_fields_data.copy(), declare_report_fields_data.copy(), declare_report_fields_data.copy())
    return (finish_outputs_in_order_output, finish_outputs_in_order_output2, finish_outputs_in_order_output3)

def prepare_assemble_report(build_report_title_data, finish_outputs_in_order_output2):
    build_report_table_data = _delivery_report_table(finish_outputs_in_order_output2, [], True)
    combine_report_fragments_data = _operation_combine_report_fragments(build_report_title_data, build_report_table_data)
    assemble_report_data = _delivery_report_layout(combine_report_fragments_data, ['Report'])
    return assemble_report_data

def prepare_inspect_completion(run_postprocessing_command_data):
    control_email_delivery_data = pd.DataFrame({'Message': ['Draft after outputs finish']} if len(run_postprocessing_command_data.index) > 0 else {'Message': []})
    return None

def _delivery_report_text(message, output_field='Report'):
    return pd.DataFrame({output_field: [f'<p>{html.escape(message)}</p>']})

def bounded_text(values, width, kind, ansi=False):
    values = values.astype('string')
    if ansi:
        values = values.map(lambda value: value if pd.isna(value) else value.encode('latin-1', errors='replace').decode('latin-1')).astype('string')
    if values.str.len().gt(width).fillna(False).any():
        warnings.warn(f'{kind} values truncated to {width} characters', RuntimeWarning, stacklevel=2)
    return values.str.slice(0, width)

def _functions_replace(value, old, new):
    return ('' if value is None else str(value)).replace(str(old), str(new))

def declare_field(frame, name, declaration):
    fields = {field['name']: dict(field) for field in frame.attrs.get('alteryx_schema', [])}
    fields[name] = {'name': name, **declaration}
    frame.attrs['alteryx_schema'] = list(fields.values())

def _add_nullable(left, right):
    if left is None and isinstance(right, (int, float)):
        left = 0
    if right is None and isinstance(left, (int, float)):
        right = 0
    return left + right

def _functions_to_string(value):
    if value is None or bool(pd.isna(value)):
        return ''
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)

def _field_contracts_fixed_decimal(value, width, scale):
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

def _regex_replacement(template, match):
    result = template
    for index, value in enumerate(match.groups(), start=1):
        result = result.replace(f'${index}', '' if value is None else value)
    return result

def _autofield_auto_convert(series):
    if not pd.api.types.is_object_dtype(series) and (not pd.api.types.is_string_dtype(series)):
        return series
    non_empty = series.dropna().astype(str)
    non_empty = non_empty[non_empty != '']
    if non_empty.empty:
        return series
    numeric = pd.to_numeric(non_empty, errors='coerce')
    if numeric.notna().all():
        converted = pd.to_numeric(series.replace('', pd.NA), errors='coerce')
        if (converted.dropna() % 1 == 0).all():
            return converted.astype('Int64')
        return converted
    return series

def _fieldinfo_size(series):
    if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
        return int(series.dropna().astype(str).map(len).max() or 0)
    return 0

def nullable_integer(values, dtype, minimum, maximum):
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
            warnings.warn(f"{('Byte' if dtype == 'UInt8' else dtype)} conversion overflow/invalid input; converted to null", RuntimeWarning, stacklevel=2)
            converted.append(pd.NA)
    return pd.Series(converted, index=values.index, name=values.name, dtype=dtype)

def _delivery_report_table(frame, fields, show_header=True):
    selected = frame.loc[:, fields] if fields else frame
    return pd.DataFrame({'Report': [selected.to_html(index=False, border=0, header=show_header, escape=True)]})

def _delivery_report_layout(frame, fields):
    fields = fields or ['Report']
    fragments = [str(row[field]) for row in frame.to_dict('records') for field in fields]
    return pd.DataFrame({'Report': ['\n'.join(fragments)]})

def _delivery_render_html(frame, data_field, destination):
    body = '\n'.join((str(value) for value in frame[data_field]))
    document = '<!doctype html>\n<html><head><meta charset="utf-8"></head><body>\n' + body + '\n</body></html>\n'
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding='utf-8', newline='')

def _delivery_command_arguments(arguments):
    if not isinstance(arguments, str):
        return list(arguments)
    if os.name != 'nt':
        return shlex.split(arguments)
    import ctypes
    from ctypes import wintypes
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(wintypes.LPWSTR)
    release = ctypes.windll.kernel32.LocalFree
    release.argtypes = [ctypes.c_void_p]
    release.restype = ctypes.c_void_p
    count = ctypes.c_int()
    pointer = parse('command ' + arguments, ctypes.byref(count))
    if not pointer:
        raise OSError('Cannot parse Windows command arguments')
    try:
        return [pointer[index] for index in range(1, count.value)]
    finally:
        release(pointer)

def _delivery_run_checked_command(program, arguments, working_dir, input_frame, input_file, output_file, allowed_programs, timeout=30):
    candidate = Path(working_dir) / program
    if not Path(program).is_absolute() and candidate.is_file():
        program = str(candidate.resolve())
    executable = shutil.which(program) or program
    resolved = Path(executable).resolve()
    allowed = {Path(shutil.which(value) or value).resolve() for value in allowed_programs}
    if resolved not in allowed:
        raise PermissionError(f'Command is not explicitly allowed: {program}')
    directory = Path(working_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if input_file:
        input_frame.to_csv(directory / input_file, index=False)
    argv = _delivery_command_arguments(arguments)
    command = [str(resolved), *argv]
    if os.name == 'nt' and resolved.suffix.lower() in {'.bat', '.cmd'}:
        if any((any((char in value for char in '&|<>^%\r\n')) for value in [str(resolved), *argv])):
            raise ValueError('Batch command arguments contain unsupported shell metacharacters')
        command = subprocess.list2cmdline([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/s', '/c']) + ' "' + subprocess.list2cmdline([str(resolved), *argv]) + '"'
    subprocess.run(command, cwd=directory, check=True, timeout=timeout, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if output_file:
        return pd.read_csv(directory / output_file)
    return input_frame.copy() if input_frame is not None else pd.DataFrame()

def _delivery_draft_email(frame, sender, recipient, subject, body_field, attachments, destination):
    if len(frame.index) != 1:
        raise ValueError('Draft profile requires exactly one message record')
    message = EmailMessage(policy=SMTP)
    message['From'] = sender
    message['To'] = recipient
    message['Subject'] = subject
    message['X-Unsent'] = '1'
    message.set_content('This message contains an HTML report.')
    message.add_alternative(str(frame.iloc[0][body_field]), subtype='html')
    for attachment in attachments:
        path = Path(attachment)
        media = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        main, sub = media.split('/', 1)
        message.add_attachment(path.read_bytes(), maintype=main, subtype=sub, filename=path.name)
    for index, part in enumerate(message.walk()):
        if part.is_multipart():
            part.set_boundary('migration-' + hashlib.sha256((subject + str(index)).encode()).hexdigest()[:24])
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(message.as_bytes())

def _operation_reshape_measurements_wide(input_frame):
    input_frame[['species', 'Name', 'Value']]
    headers = list(dict.fromkeys(input_frame['Name'].dropna().astype(str)))
    grouped_rows = {}
    cells = {}
    for row in input_frame.to_dict('records'):
        key = tuple((row[field] for field in ['species']))
        grouped_rows.setdefault(key, {field: row[field] for field in ['species']})
        header = row['Name']
        if not pd.isna(header):
            cells.setdefault((key, str(header)), []).append(row['Value'])
    rows = []
    for key, row in grouped_rows.items():
        for header in headers:
            if header in ['species']:
                continue
            values = cells.get((key, header))
            row[header] = pd.to_numeric(pd.Series(values), errors='coerce').sum(min_count=1) if values else None
        rows.append(row)
    output = pd.DataFrame(rows, columns=['species'] + headers)
    return output.astype(object).where(pd.notna(output), None)

def _operation_combine_report_fragments(input_frame, input_2_frame):
    frames = [input_frame, input_2_frame]
    columns = list(dict.fromkeys((column for frame in frames for column in frame.columns)))
    aligned = [frame.reindex(columns=columns) for frame in frames]
    combined = pd.concat(aligned, ignore_index=True)
    return combined.astype(object).where(pd.notna(combined), None)
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Run the migrated Python workflow')
    parser.add_argument('--input-dir', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--event-working-dir', type=Path)
    parser.add_argument('--command-working-dir', type=Path)
    parser.add_argument('--allow-command', action='append', default=[])
    parser.add_argument('--minimum-sepal-length', type=float, default=5)
    args = parser.parse_args()
    print(run_workflow(input_dir=args.input_dir, output_dir=args.output_dir, event_working_dir=args.event_working_dir, command_working_dir=args.command_working_dir, allowed_commands=args.allow_command, minimum_sepal_length=args.minimum_sepal_length))

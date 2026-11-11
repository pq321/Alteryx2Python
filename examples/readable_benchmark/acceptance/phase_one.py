from alteryx2python.ir.models import AnchorIR, EdgeIR, NodeIR, WorkflowIR
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph

NODE_DATA = [{'config': {'File': {'attributes': {'FileFormat': '0'}, 'text': 'data/iris.data'},
             'FormatSpecificOptions': {'CodePage': {'text': '65001'},
                                       'Delimeter': {'text': ','},
                                       'HeaderRow': {'text': 'False'}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'file': 'data/iris.data',
                            'file_attributes': {'FileFormat': '0'},
                            'format_specific_options': {'CodePage': {'text': '65001'},
                                                        'Delimeter': {'text': ','},
                                                        'HeaderRow': {'text': 'False'}}},
             'raw': {'File': {'attributes': {'FileFormat': '0'}, 'text': 'data/iris.data'},
                     'FormatSpecificOptions': {'CodePage': {'text': '65001'},
                                               'Delimeter': {'text': ','},
                                               'HeaderRow': {'text': 'False'}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': [],
  'input_anchors': [],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'load_measurements'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'In/Out',
                           'display_name': 'Input Data',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxDbFileInput',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'DbFileInput'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.DbFileInput.DbFileInput',
               'raw_gui_settings': {'Position': {'attributes': {'x': '54', 'y': '160'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.DbFileInput.DbFileInput'}}},
  'node_id': '1',
  'outgoing_edges': ['1:Output->2:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '1',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.DbFileInput.DbFileInput',
  'tool_type': 'DbFileInput',
  'warnings': []},
 {'config': {'Value': {'attributes': {'name': 'factor'}, 'text': '2'},
             'normalized': {'Value': {'attributes': {'name': 'factor'}, 'text': '2'},
                            'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'macro_path': 'NormalizeMeasurements.yxmc',
                            'macro_tool_type': 'Macro_NormalizeMeasurements'},
             'raw': {'Value': {'attributes': {'name': 'factor'}, 'text': '2'}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['3:Output->4:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'Name': {'text': 'normalize_species'}},
               'meta_info': {},
               'plugin_name': 'NormalizeMeasurements.yxmc',
               'raw_gui_settings': {}},
  'node_id': '4',
  'outgoing_edges': ['4:Output->5:Input', '4:Output->30:Input', '4:Output->35:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '4',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'NormalizeMeasurements.yxmc',
  'tool_type': 'Macro_NormalizeMeasurements',
  'warnings': []},
 {'config': {'FormulaFields': {'FormulaField': [{'attributes': {'expression': '[species] + "|" + '
                                                                              'ToString([RecordID])',
                                                                'field': 'measurement_key',
                                                                'size': '64',
                                                                'type': 'V_WString'}},
                                                {'attributes': {'expression': '"2026-11-11"',
                                                                'field': 'report_date',
                                                                'size': '10',
                                                                'type': 'Date'}},
                                                {'attributes': {'expression': '[scaled_petal_length] '
                                                                              '* 1.25',
                                                                'field': 'petal_cost',
                                                                'size': '12.2',
                                                                'type': 'FixedDecimal'}}]},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'formula_fields': [{'enabled': True,
                                                'expression': '[species] + "|" + '
                                                              'ToString([RecordID])',
                                                'field': 'measurement_key',
                                                'size': '64',
                                                'type': 'V_WString'},
                                               {'enabled': True,
                                                'expression': '"2026-11-11"',
                                                'field': 'report_date',
                                                'size': '10',
                                                'type': 'Date'},
                                               {'enabled': True,
                                                'expression': '[scaled_petal_length] * 1.25',
                                                'field': 'petal_cost',
                                                'size': '12.2',
                                                'type': 'FixedDecimal'}]},
             'raw': {'FormulaFields': {'FormulaField': [{'attributes': {'expression': '[species] + '
                                                                                      '"|" + '
                                                                                      'ToString([RecordID])',
                                                                        'field': 'measurement_key',
                                                                        'size': '64',
                                                                        'type': 'V_WString'}},
                                                        {'attributes': {'expression': '"2026-11-11"',
                                                                        'field': 'report_date',
                                                                        'size': '10',
                                                                        'type': 'Date'}},
                                                        {'attributes': {'expression': '[scaled_petal_length] '
                                                                                      '* 1.25',
                                                                        'field': 'petal_cost',
                                                                        'size': '12.2',
                                                                        'type': 'FixedDecimal'}}]}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['4:Output->5:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'calculate_report_fields'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Formula',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxFormula',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'html-plugin',
                           'tool_type': 'Formula'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.Formula.Formula',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.Formula.Formula'}}},
  'node_id': '5',
  'outgoing_edges': ['5:Output->6:Input', '5:Output->32:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '5',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.Formula.Formula',
  'tool_type': 'Formula',
  'warnings': []},
 {'config': {'Expression': {'text': '[sepal_length] >= MIN_SEPAL'},
             'Mode': {'text': 'Custom'},
             'Simple': {'Operands': {}, 'Operator': {'text': '='}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'expression': '[sepal_length] >= MIN_SEPAL',
                            'mode': 'Custom'},
             'raw': {'Expression': {'text': '[sepal_length] >= MIN_SEPAL'},
                     'Mode': {'text': 'Custom'},
                     'Simple': {'Operands': {}, 'Operator': {'text': '='}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['5:Output->6:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'filter_minimum_sepal_length'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Filter',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxFilter',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'html-plugin',
                           'tool_type': 'Filter'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.Filter.Filter',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.Filter.Filter'}}},
  'node_id': '6',
  'outgoing_edges': ['6:True->7:Input', '6:False->14:Input2'],
  'output_anchors': [{'direction': 'output', 'name': 'False'},
                     {'direction': 'output', 'name': 'True'}],
  'source_tool_id': '6',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.Filter.Filter',
  'tool_type': 'Filter',
  'warnings': []},
 {'config': {'Delimeters': {'attributes': {'value': '|'}},
             'ErrorHandling': {'text': 'Last'},
             'Field': {'text': 'measurement_key'},
             'Flags': {'attributes': {'value': '0'}},
             'NumFields': {'attributes': {'value': '2'}},
             'RootName': {'text': 'key_part'},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'delimiters': '|',
                            'error_handling': 'Last',
                            'field': 'measurement_key',
                            'flags': 0,
                            'num_fields': 2,
                            'root_name': 'key_part'},
             'raw': {'Delimeters': {'attributes': {'value': '|'}},
                     'ErrorHandling': {'text': 'Last'},
                     'Field': {'text': 'measurement_key'},
                     'Flags': {'attributes': {'value': '0'}},
                     'NumFields': {'attributes': {'value': '2'}},
                     'RootName': {'text': 'key_part'}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['6:True->7:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'split_measurement_key'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Parse',
                           'display_name': 'TextToColumns',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxTextToColumns',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'html-plugin',
                           'tool_type': 'TextToColumns'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.TextToColumns.TextToColumns',
               'raw_gui_settings': {'Position': {'attributes': {'x': '600', 'y': '160'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.TextToColumns.TextToColumns'}}},
  'node_id': '7',
  'outgoing_edges': ['7:Output->8:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '7',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.TextToColumns.TextToColumns',
  'tool_type': 'TextToColumns',
  'warnings': []},
 {'config': {'UniqueFields': {'Field': {'attributes': {'field': 'RecordID'}}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'unique_fields': ['RecordID']},
             'raw': {'UniqueFields': {'Field': {'attributes': {'field': 'RecordID'}}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['7:Output->8:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'deduplicate_measurements'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Unique',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxUnique',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'html-plugin',
                           'tool_type': 'Unique'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.Unique.Unique',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.Unique.Unique'}}},
  'node_id': '8',
  'outgoing_edges': ['8:Unique->9:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Unique'}],
  'source_tool_id': '8',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.Unique.Unique',
  'tool_type': 'Unique',
  'warnings': []},
 {'config': {'SortInfo': {'Field': [{'attributes': {'field': 'species', 'order': 'Ascending'}},
                                    {'attributes': {'field': 'RecordID', 'order': 'Ascending'}}],
                          'attributes': {'locale': '0'}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'sort_fields': [{'field': 'species', 'order': 'Ascending'},
                                            {'field': 'RecordID', 'order': 'Ascending'}]},
             'raw': {'SortInfo': {'Field': [{'attributes': {'field': 'species',
                                                            'order': 'Ascending'}},
                                            {'attributes': {'field': 'RecordID',
                                                            'order': 'Ascending'}}],
                                  'attributes': {'locale': '0'}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['8:Unique->9:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'sort_measurements'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Sort',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxSort',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'Sort'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.Sort.Sort',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.Sort.Sort'}}},
  'node_id': '9',
  'outgoing_edges': ['9:Output->10:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '9',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.Sort.Sort',
  'tool_type': 'Sort',
  'warnings': []},
 {'config': {'GroupByFields': {'Field': {'attributes': {'field': 'species'}}},
             'RunningTotalFields': {'Field': {'attributes': {'field': 'scaled_petal_length'}}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'group_by_fields': ['species'],
                            'running_total_fields': ['scaled_petal_length']},
             'raw': {'GroupByFields': {'Field': {'attributes': {'field': 'species'}}},
                     'RunningTotalFields': {'Field': {'attributes': {'field': 'scaled_petal_length'}}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['9:Output->10:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'calculate_running_totals'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Transform',
                           'display_name': 'Running Total',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxRunningTotal',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'RunningTotal'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.RunningTotal.RunningTotal',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.RunningTotal.RunningTotal'}}},
  'node_id': '10',
  'outgoing_edges': ['10:Output->11:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '10',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.RunningTotal.RunningTotal',
  'tool_type': 'RunningTotal',
  'warnings': []},
 {'config': {'GroupFields': {},
             'RankingModes': {'Mode': {'attributes': {'value': 'Ordinal'}}},
             'SortInfo': {'Field': {'attributes': {'field': 'sepal_length', 'order': 'Descending'}},
                          'attributes': {'locale': '0'}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'group_fields': [],
                            'ranking_modes': ['Ordinal'],
                            'sort_fields': [{'field': 'sepal_length', 'order': 'Descending'}]},
             'raw': {'GroupFields': {},
                     'RankingModes': {'Mode': {'attributes': {'value': 'Ordinal'}}},
                     'SortInfo': {'Field': {'attributes': {'field': 'sepal_length',
                                                           'order': 'Descending'}},
                                  'attributes': {'locale': '0'}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['10:Output->11:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'rank_measurements'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Rank',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxRank',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'Rank'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.Rank.Rank',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.Rank.Rank'}}},
  'node_id': '11',
  'outgoing_edges': ['11:Output->12:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '11',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.Rank.Rank',
  'tool_type': 'Rank',
  'warnings': []},
 {'config': {'GroupFields': {'attributes': {'orderChanged': 'False'}},
             'Mode': {'text': 'First'},
             'N': {'text': '120'},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'group_fields': [],
                            'mode': 'First',
                            'n': 120},
             'raw': {'GroupFields': {'attributes': {'orderChanged': 'False'}},
                     'Mode': {'text': 'First'},
                     'N': {'text': '120'}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['11:Output->12:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'take_report_sample'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Sample',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxSample',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'html-plugin',
                           'tool_type': 'Sample'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.Sample.Sample',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.Sample.Sample'}}},
  'node_id': '12',
  'outgoing_edges': ['12:Output->13:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '12',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.Sample.Sample',
  'tool_type': 'Sample',
  'warnings': []},
 {'config': {'SummarizeFields': {'SummarizeField': [{'attributes': {'action': 'GroupBy',
                                                                    'field': 'species',
                                                                    'rename': 'species'}},
                                                    {'attributes': {'action': 'Avg',
                                                                    'field': 'sepal_length',
                                                                    'rename': 'mean_sepal_length'}},
                                                    {'attributes': {'action': 'Count',
                                                                    'field': 'RecordID',
                                                                    'rename': 'measurement_count'}},
                                                    {'attributes': {'action': 'Sum',
                                                                    'field': 'scaled_petal_length',
                                                                    'rename': 'petal_total'}}]},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'summarize_fields': [{'action': 'GroupBy',
                                                  'concat_end': '',
                                                  'concat_start': '',
                                                  'field': 'species',
                                                  'rename': 'species',
                                                  'separator': ''},
                                                 {'action': 'Avg',
                                                  'concat_end': '',
                                                  'concat_start': '',
                                                  'field': 'sepal_length',
                                                  'rename': 'mean_sepal_length',
                                                  'separator': ''},
                                                 {'action': 'Count',
                                                  'concat_end': '',
                                                  'concat_start': '',
                                                  'field': 'RecordID',
                                                  'rename': 'measurement_count',
                                                  'separator': ''},
                                                 {'action': 'Sum',
                                                  'concat_end': '',
                                                  'concat_start': '',
                                                  'field': 'scaled_petal_length',
                                                  'rename': 'petal_total',
                                                  'separator': ''}]},
             'raw': {'SummarizeFields': {'SummarizeField': [{'attributes': {'action': 'GroupBy',
                                                                            'field': 'species',
                                                                            'rename': 'species'}},
                                                            {'attributes': {'action': 'Avg',
                                                                            'field': 'sepal_length',
                                                                            'rename': 'mean_sepal_length'}},
                                                            {'attributes': {'action': 'Count',
                                                                            'field': 'RecordID',
                                                                            'rename': 'measurement_count'}},
                                                            {'attributes': {'action': 'Sum',
                                                                            'field': 'scaled_petal_length',
                                                                            'rename': 'petal_total'}}]}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['12:Output->13:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'summarize_species'},
                              'attributes': {'DisplayMode': '0'}},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.Summarize.Summarize',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.Summarize.Summarize'}}},
  'node_id': '13',
  'outgoing_edges': ['13:Output->14:Input1'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '13',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.Summarize.Summarize',
  'tool_type': 'Summarize',
  'warnings': []},
 {'config': {'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'macro_path': 'BenchmarkParallelBlock.yxmc',
                            'macro_tool_type': 'Macro_BenchmarkParallelBlock'},
             'raw': {}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['13:Output->14:Input1', '6:False->14:Input2'],
  'input_anchors': [{'direction': 'input', 'name': 'Input1'},
                    {'direction': 'input', 'name': 'Input2'}],
  'metadata': {'annotation': {'Name': {'text': 'sequence_independent_streams'}},
               'meta_info': {},
               'plugin_name': 'BenchmarkParallelBlock.yxmc',
               'raw_gui_settings': {}},
  'node_id': '14',
  'outgoing_edges': ['14:Output2->15:Input', '14:Output1->17:Left'],
  'output_anchors': [{'direction': 'output', 'name': 'Output1'},
                     {'direction': 'output', 'name': 'Output2'}],
  'source_tool_id': '14',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'BenchmarkParallelBlock.yxmc',
  'tool_type': 'Macro_BenchmarkParallelBlock',
  'warnings': []},
 {'config': {'File': {'attributes': {'FileFormat': '0', 'MaxRecords': ''},
                      'text': 'output/rejected_measurements.csv'},
             'FormatSpecificOptions': {'CodePage': {'text': '28591'},
                                       'Delimeter': {'text': ','},
                                       'ForceQuotes': {'text': 'False'},
                                       'HeaderRow': {'text': 'True'},
                                       'LineEndStyle': {'text': 'CRLF'},
                                       'WriteBOM': {'text': 'True'}},
             'MultiFile': {'attributes': {'value': 'False'}},
             'Passwords': {},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'file': 'output/rejected_measurements.csv',
                            'file_attributes': {'FileFormat': '0', 'MaxRecords': ''},
                            'format_specific_options': {'CodePage': {'text': '28591'},
                                                        'Delimeter': {'text': ','},
                                                        'ForceQuotes': {'text': 'False'},
                                                        'HeaderRow': {'text': 'True'},
                                                        'LineEndStyle': {'text': 'CRLF'},
                                                        'WriteBOM': {'text': 'True'}},
                            'output_option': ''},
             'raw': {'File': {'attributes': {'FileFormat': '0', 'MaxRecords': ''},
                              'text': 'output/rejected_measurements.csv'},
                     'FormatSpecificOptions': {'CodePage': {'text': '28591'},
                                               'Delimeter': {'text': ','},
                                               'ForceQuotes': {'text': 'False'},
                                               'HeaderRow': {'text': 'True'},
                                               'LineEndStyle': {'text': 'CRLF'},
                                               'WriteBOM': {'text': 'True'}},
                     'MultiFile': {'attributes': {'value': 'False'}},
                     'Passwords': {}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['14:Output2->15:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'write_rejected_measurements'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'In/Out',
                           'display_name': 'Output Data',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxDbFileOutput',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'DbFileOutput'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.DbFileOutput.DbFileOutput',
               'raw_gui_settings': {'Position': {'attributes': {'x': '600', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.DbFileOutput.DbFileOutput'}}},
  'node_id': '15',
  'outgoing_edges': [],
  'output_anchors': [],
  'source_tool_id': '15',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.DbFileOutput.DbFileOutput',
  'tool_type': 'DbFileOutput',
  'warnings': []},
 {'config': {'Data': {'r': [{'c': [{'text': 'setosa'}, {'text': 'A'}]},
                            {'c': [{'text': 'versicolor'}, {'text': 'B'}]},
                            {'c': [{'text': 'virginica'}, {'text': 'C'}]}]},
             'Fields': {'Field': [{'attributes': {'name': 'species'}},
                                  {'attributes': {'name': 'report_group'}}]},
             'NumRows': {'attributes': {'value': '3'}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'fields': ['species', 'report_group'],
                            'num_rows': 3,
                            'rows': [['setosa', 'A'], ['versicolor', 'B'], ['virginica', 'C']]},
             'raw': {'Data': {'r': [{'c': [{'text': 'setosa'}, {'text': 'A'}]},
                                    {'c': [{'text': 'versicolor'}, {'text': 'B'}]},
                                    {'c': [{'text': 'virginica'}, {'text': 'C'}]}]},
                     'Fields': {'Field': [{'attributes': {'name': 'species'}},
                                          {'attributes': {'name': 'report_group'}}]},
                     'NumRows': {'attributes': {'value': '3'}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': [],
  'input_anchors': [],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'load_report_groups'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'In/Out',
                           'display_name': 'Text Input',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxTextInput',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'TextInput'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.TextInput.TextInput',
               'raw_gui_settings': {'Position': {'attributes': {'x': '54', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.TextInput.TextInput'}}},
  'node_id': '16',
  'outgoing_edges': ['16:Output->17:Right'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '16',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.TextInput.TextInput',
  'tool_type': 'TextInput',
  'warnings': []},
 {'config': {'JoinInfo': [{'Field': {'attributes': {'field': 'species'}},
                           'attributes': {'connection': 'Left'}},
                          {'Field': {'attributes': {'field': 'species'}},
                           'attributes': {'connection': 'Right'}}],
             'SelectConfiguration': {'Configuration': {'SelectFields': {'SelectField': [{'attributes': {'field': 'Left_species',
                                                                                                        'rename': 'Left_species',
                                                                                                        'selected': 'True'}},
                                                                                        {'attributes': {'field': 'Left_mean_sepal_length',
                                                                                                        'rename': 'Left_mean_sepal_length',
                                                                                                        'selected': 'True'}},
                                                                                        {'attributes': {'field': 'Left_measurement_count',
                                                                                                        'rename': 'Left_measurement_count',
                                                                                                        'selected': 'True'}},
                                                                                        {'attributes': {'field': 'Left_petal_total',
                                                                                                        'rename': 'Left_petal_total',
                                                                                                        'selected': 'True'}},
                                                                                        {'attributes': {'field': 'Right_report_group',
                                                                                                        'rename': 'Right_report_group',
                                                                                                        'selected': 'True'}}]},
                                                       'attributes': {'outputConnection': 'Join'}}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'join_by_record_pos': False,
                            'joins': [{'connection': 'Left', 'field': 'species'},
                                      {'connection': 'Right', 'field': 'species'}],
                            'output_connection': 'Join',
                            'select_fields': [{'input': '',
                                               'rename': 'Left_species',
                                               'selected': True,
                                               'source': 'Left_species'},
                                              {'input': '',
                                               'rename': 'Left_mean_sepal_length',
                                               'selected': True,
                                               'source': 'Left_mean_sepal_length'},
                                              {'input': '',
                                               'rename': 'Left_measurement_count',
                                               'selected': True,
                                               'source': 'Left_measurement_count'},
                                              {'input': '',
                                               'rename': 'Left_petal_total',
                                               'selected': True,
                                               'source': 'Left_petal_total'},
                                              {'input': '',
                                               'rename': 'Right_report_group',
                                               'selected': True,
                                               'source': 'Right_report_group'}]},
             'raw': {'JoinInfo': [{'Field': {'attributes': {'field': 'species'}},
                                   'attributes': {'connection': 'Left'}},
                                  {'Field': {'attributes': {'field': 'species'}},
                                   'attributes': {'connection': 'Right'}}],
                     'SelectConfiguration': {'Configuration': {'SelectFields': {'SelectField': [{'attributes': {'field': 'Left_species',
                                                                                                                'rename': 'Left_species',
                                                                                                                'selected': 'True'}},
                                                                                                {'attributes': {'field': 'Left_mean_sepal_length',
                                                                                                                'rename': 'Left_mean_sepal_length',
                                                                                                                'selected': 'True'}},
                                                                                                {'attributes': {'field': 'Left_measurement_count',
                                                                                                                'rename': 'Left_measurement_count',
                                                                                                                'selected': 'True'}},
                                                                                                {'attributes': {'field': 'Left_petal_total',
                                                                                                                'rename': 'Left_petal_total',
                                                                                                                'selected': 'True'}},
                                                                                                {'attributes': {'field': 'Right_report_group',
                                                                                                                'rename': 'Right_report_group',
                                                                                                                'selected': 'True'}}]},
                                                               'attributes': {'outputConnection': 'Join'}}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['14:Output1->17:Left', '16:Output->17:Right'],
  'input_anchors': [{'direction': 'input', 'name': 'Left'},
                    {'direction': 'input', 'name': 'Right'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'join_report_groups'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Join',
                           'display_name': 'Join',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxJoin',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'Join'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.Join.Join',
               'raw_gui_settings': {'Position': {'attributes': {'x': '800', 'y': '160'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.Join.Join'}}},
  'node_id': '17',
  'outgoing_edges': ['17:Join->18:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Join'}],
  'source_tool_id': '17',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.Join.Join',
  'tool_type': 'Join',
  'warnings': []},
 {'config': {'SelectFields': {'SelectField': [{'attributes': {'field': 'Left_species',
                                                              'selected': 'True',
                                                              'size': '24',
                                                              'type': 'V_WString'}},
                                              {'attributes': {'field': 'Left_mean_sepal_length',
                                                              'selected': 'True',
                                                              'size': '8',
                                                              'type': 'Double'}},
                                              {'attributes': {'field': 'Left_measurement_count',
                                                              'selected': 'True',
                                                              'size': '4',
                                                              'type': 'Int32'}},
                                              {'attributes': {'field': 'Left_petal_total',
                                                              'selected': 'True',
                                                              'size': '8',
                                                              'type': 'Double'}},
                                              {'attributes': {'field': 'Right_report_group',
                                                              'selected': 'True',
                                                              'size': '8',
                                                              'type': 'V_WString'}}]},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'order_changed': None,
                            'select_fields': [{'dtype': 'V_WString',
                                               'forced': False,
                                               'rename': 'Left_species',
                                               'selected': True,
                                               'size': '24',
                                               'source': 'Left_species'},
                                              {'dtype': 'Double',
                                               'forced': False,
                                               'rename': 'Left_mean_sepal_length',
                                               'selected': True,
                                               'size': '8',
                                               'source': 'Left_mean_sepal_length'},
                                              {'dtype': 'Int32',
                                               'forced': False,
                                               'rename': 'Left_measurement_count',
                                               'selected': True,
                                               'size': '4',
                                               'source': 'Left_measurement_count'},
                                              {'dtype': 'Double',
                                               'forced': False,
                                               'rename': 'Left_petal_total',
                                               'selected': True,
                                               'size': '8',
                                               'source': 'Left_petal_total'},
                                              {'dtype': 'V_WString',
                                               'forced': False,
                                               'rename': 'Right_report_group',
                                               'selected': True,
                                               'size': '8',
                                               'source': 'Right_report_group'}]},
             'raw': {'SelectFields': {'SelectField': [{'attributes': {'field': 'Left_species',
                                                                      'selected': 'True',
                                                                      'size': '24',
                                                                      'type': 'V_WString'}},
                                                      {'attributes': {'field': 'Left_mean_sepal_length',
                                                                      'selected': 'True',
                                                                      'size': '8',
                                                                      'type': 'Double'}},
                                                      {'attributes': {'field': 'Left_measurement_count',
                                                                      'selected': 'True',
                                                                      'size': '4',
                                                                      'type': 'Int32'}},
                                                      {'attributes': {'field': 'Left_petal_total',
                                                                      'selected': 'True',
                                                                      'size': '8',
                                                                      'type': 'Double'}},
                                                      {'attributes': {'field': 'Right_report_group',
                                                                      'selected': 'True',
                                                                      'size': '8',
                                                                      'type': 'V_WString'}}]}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['17:Join->18:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'declare_report_fields'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Select',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxSelect',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'Select'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect',
               'raw_gui_settings': {'Position': {'attributes': {'x': '900', 'y': '160'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect'}}},
  'node_id': '18',
  'outgoing_edges': ['18:Output->19:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '18',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect',
  'tool_type': 'Select',
  'warnings': []},
 {'config': {'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark'},
             'raw': {}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['18:Output->19:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'finish_outputs_in_order'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Developer',
                           'display_name': 'BlockUntilDone',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxBlockUntilDone',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'html-plugin',
                           'tool_type': 'BlockUntilDone'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.BlockUntilDone.BlockUntilDone',
               'raw_gui_settings': {'Position': {'attributes': {'x': '1050', 'y': '160'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.BlockUntilDone.BlockUntilDone'}}},
  'node_id': '19',
  'outgoing_edges': ['19:Output->20:Input', '19:Output2->21:Input', '19:Output3->26:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'},
                     {'direction': 'output', 'name': 'Output2'},
                     {'direction': 'output', 'name': 'Output3'}],
  'source_tool_id': '19',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.BlockUntilDone.BlockUntilDone',
  'tool_type': 'BlockUntilDone',
  'warnings': []},
 {'config': {'File': {'attributes': {'FileFormat': '0', 'MaxRecords': ''},
                      'text': 'output/species_summary.csv'},
             'FormatSpecificOptions': {'CodePage': {'text': '28591'},
                                       'Delimeter': {'text': ','},
                                       'ForceQuotes': {'text': 'False'},
                                       'HeaderRow': {'text': 'True'},
                                       'LineEndStyle': {'text': 'CRLF'},
                                       'WriteBOM': {'text': 'True'}},
             'MultiFile': {'attributes': {'value': 'False'}},
             'Passwords': {},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'file': 'output/species_summary.csv',
                            'file_attributes': {'FileFormat': '0', 'MaxRecords': ''},
                            'format_specific_options': {'CodePage': {'text': '28591'},
                                                        'Delimeter': {'text': ','},
                                                        'ForceQuotes': {'text': 'False'},
                                                        'HeaderRow': {'text': 'True'},
                                                        'LineEndStyle': {'text': 'CRLF'},
                                                        'WriteBOM': {'text': 'True'}},
                            'output_option': ''},
             'raw': {'File': {'attributes': {'FileFormat': '0', 'MaxRecords': ''},
                              'text': 'output/species_summary.csv'},
                     'FormatSpecificOptions': {'CodePage': {'text': '28591'},
                                               'Delimeter': {'text': ','},
                                               'ForceQuotes': {'text': 'False'},
                                               'HeaderRow': {'text': 'True'},
                                               'LineEndStyle': {'text': 'CRLF'},
                                               'WriteBOM': {'text': 'True'}},
                     'MultiFile': {'attributes': {'value': 'False'}},
                     'Passwords': {}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['19:Output->20:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'write_species_summary'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'In/Out',
                           'display_name': 'Output Data',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxDbFileOutput',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'DbFileOutput'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.DbFileOutput.DbFileOutput',
               'raw_gui_settings': {'Position': {'attributes': {'x': '600', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.DbFileOutput.DbFileOutput'}}},
  'node_id': '20',
  'outgoing_edges': [],
  'output_anchors': [],
  'source_tool_id': '20',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.DbFileOutput.DbFileOutput',
  'tool_type': 'DbFileOutput',
  'warnings': []},
 {'config': {'ShowHeader': {'attributes': {'value': 'True'}},
             'TableMode': {'text': 'Basic'},
             'normalized': {'bar_graph_field': '',
                            'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'grouping_fields': [],
                            'pivot_mode': '',
                            'pivot_table_fields': [],
                            'show_bar_graph': None,
                            'show_header': True,
                            'table_fields': [],
                            'table_mode': 'Basic',
                            'width': ''},
             'raw': {'ShowHeader': {'attributes': {'value': 'True'}},
                     'TableMode': {'text': 'Basic'}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['19:Output2->21:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'build_report_table'},
                              'attributes': {'DisplayMode': '0'}},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.PortfolioComposerTable.PortfolioComposerTable',
               'raw_gui_settings': {'Position': {'attributes': {'x': '1200', 'y': '250'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.PortfolioComposerTable.PortfolioComposerTable'}}},
  'node_id': '21',
  'outgoing_edges': ['21:Output->23:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '21',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.PortfolioComposerTable.PortfolioComposerTable',
  'tool_type': 'PortfolioComposerTable',
  'warnings': []},
 {'config': {'Message': {'text': 'Iris measurement report'},
             'Output': {'text': 'Report'},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'header_field': '',
                            'header_mode': None,
                            'message': 'Iris measurement report',
                            'output_field': 'Report',
                            'raw_mode': None,
                            'rich_text': '',
                            'rich_text_mode': None},
             'raw': {'Message': {'text': 'Iris measurement report'}, 'Output': {'text': 'Report'}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': [],
  'input_anchors': [],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'build_report_title'},
                              'attributes': {'DisplayMode': '0'}},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.PortfolioComposerText.PortfolioComposerText',
               'raw_gui_settings': {'Position': {'attributes': {'x': '1000', 'y': '350'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.PortfolioComposerText.PortfolioComposerText'}}},
  'node_id': '22',
  'outgoing_edges': ['22:Output->23:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '22',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.PortfolioComposerText.PortfolioComposerText',
  'tool_type': 'PortfolioComposerText',
  'warnings': []},
 {'config': {'InPerm': {'Input': [{'attributes': {'SubId': '1'}}, {'attributes': {'SubId': '2'}}]},
             'Mode': {'text': 'ByName'},
             'OutputMode': {'text': 'Combine'},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'by_name_error_mode': '',
                            'by_name_output_mode': '',
                            'mode': 'ByName',
                            'output_order': [],
                            'set_output_order': False},
             'raw': {'InPerm': {'Input': [{'attributes': {'SubId': '1'}},
                                          {'attributes': {'SubId': '2'}}]},
                     'Mode': {'text': 'ByName'},
                     'OutputMode': {'text': 'Combine'}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['22:Output->23:Input', '21:Output->23:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'combine_report_fragments'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Join',
                           'display_name': 'Union',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxUnion',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'Union'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.Union.Union',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.Union.Union'}}},
  'node_id': '23',
  'outgoing_edges': ['23:Output->24:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '23',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.Union.Union',
  'tool_type': 'Union',
  'warnings': []},
 {'config': {'LayoutFields': {'Field': {'attributes': {'name': 'Report', 'selected': 'True'}}},
             'Orientation': {'text': 'Vertical'},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'grouping_fields': [],
                            'grouping_mode': '',
                            'height': '',
                            'layout_fields': ['Report'],
                            'orientation': 'Vertical',
                            'section_name_for_all_records': '',
                            'section_name_for_group': '',
                            'separator': '',
                            'width': ''},
             'raw': {'LayoutFields': {'Field': {'attributes': {'name': 'Report',
                                                               'selected': 'True'}}},
                     'Orientation': {'text': 'Vertical'}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['23:Output->24:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'assemble_report'},
                              'attributes': {'DisplayMode': '0'}},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.PortfolioComposerLayout.PortfolioComposerLayout',
               'raw_gui_settings': {'Position': {'attributes': {'x': '1400', 'y': '300'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.PortfolioComposerLayout.PortfolioComposerLayout'}}},
  'node_id': '24',
  'outgoing_edges': ['24:Output->25:Input', '24:Output->27:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '24',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.PortfolioComposerLayout.PortfolioComposerLayout',
  'tool_type': 'PortfolioComposerLayout',
  'warnings': []},
 {'config': {'DataField': {'text': 'Report'},
             'OutputFile': {'text': 'iris_report.html'},
             'TempFileType': {'text': 'html'},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'batch_mode': None,
                            'data_field': 'Report',
                            'filename_modifier': '',
                            'footer_field': '',
                            'group_field': '',
                            'header_field': '',
                            'output_file': 'iris_report.html',
                            'portrait_mode': None,
                            'show_footer': None,
                            'show_header': None,
                            'temp_file_type': 'html'},
             'raw': {'DataField': {'text': 'Report'},
                     'OutputFile': {'text': 'iris_report.html'},
                     'TempFileType': {'text': 'html'}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['24:Output->25:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'write_html_report'},
                              'attributes': {'DisplayMode': '0'}},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.PortfolioComposerRender.PortfolioComposerRender',
               'raw_gui_settings': {'Position': {'attributes': {'x': '1550', 'y': '300'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.PortfolioComposerRender.PortfolioComposerRender'}}},
  'node_id': '25',
  'outgoing_edges': [],
  'output_anchors': [],
  'source_tool_id': '25',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.PortfolioComposerRender.PortfolioComposerRender',
  'tool_type': 'PortfolioComposerRender',
  'warnings': []},
 {'config': {'Arguments': {'text': '-c "from pathlib import Path; '
                                   'Path(\\"command-proof.txt\\").write_text(\\"command '
                                   'completed\\n\\")"'},
             'ProgramName': {'text': 'E:\\Automation\\Alteryx2Python\\.venv\\Scripts\\python.exe'},
             'WorkingDir': {},
             'normalized': {'arguments': '-c "from pathlib import Path; '
                                         'Path(\\"command-proof.txt\\").write_text(\\"command '
                                         'completed\\n\\")"',
                            'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'input_file': '',
                            'output_file': '',
                            'program_name': 'E:\\Automation\\Alteryx2Python\\.venv\\Scripts\\python.exe',
                            'run_minimized': False,
                            'run_silent': False,
                            'working_dir': ''},
             'raw': {'Arguments': {'text': '-c "from pathlib import Path; '
                                           'Path(\\"command-proof.txt\\").write_text(\\"command '
                                           'completed\\n\\")"'},
                     'ProgramName': {'text': 'E:\\Automation\\Alteryx2Python\\.venv\\Scripts\\python.exe'},
                     'WorkingDir': {}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['19:Output3->26:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'run_postprocessing_command'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'In/Out',
                           'display_name': 'Run Command',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxRunCommand',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'RunCommand'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.RunCommand.RunCommand',
               'raw_gui_settings': {'Position': {'attributes': {'x': '1250', 'y': '450'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.RunCommand.RunCommand'}}},
  'node_id': '26',
  'outgoing_edges': ['26:Output->28:Control'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '26',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.RunCommand.RunCommand',
  'tool_type': 'RunCommand',
  'warnings': []},
 {'config': {'Caption': {'text': 'Draft after outputs finish'},
             'Disabled': {'attributes': {'value': 'False'}},
             'child_node_ids': ['27'],
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'caption': 'Draft after outputs finish',
                            'disabled': False,
                            'folded': False,
                            'style': {}},
             'raw': {'Caption': {'text': 'Draft after outputs finish'},
                     'Disabled': {'attributes': {'value': 'False'}},
                     'child_node_ids': ['27']}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['26:Output->28:Control'],
  'input_anchors': [{'direction': 'input', 'name': 'Control'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'control_email_delivery'},
                              'attributes': {'DisplayMode': '0'}},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.ControlContainer.ControlContainer',
               'raw_gui_settings': {'Position': {'attributes': {'x': '1600', 'y': '450'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.ControlContainer.ControlContainer'}}},
  'node_id': '28',
  'outgoing_edges': ['28:Log->29:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Log'}],
  'source_tool_id': '28',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.ControlContainer.ControlContainer',
  'tool_type': 'ControlContainer',
  'warnings': []},
 {'config': {'Attachments': {'Attachment': {'text': 'iris_report.html'}},
             'Body': {'text': 'Report'},
             'From': {'text': 'reports@example.invalid'},
             'Subject': {'text': 'Iris measurement report'},
             'To': {'text': 'reviewer@example.invalid'},
             'container_id': '28',
             'normalized': {'attachments': ['iris_report.html'],
                            'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'body': 'Report',
                            'from': 'reports@example.invalid',
                            'smtp_server': '',
                            'subject': 'Iris measurement report',
                            'to': 'reviewer@example.invalid',
                            'unsupported_options': []},
             'raw': {'Attachments': {'Attachment': {'text': 'iris_report.html'}},
                     'Body': {'text': 'Report'},
                     'From': {'text': 'reports@example.invalid'},
                     'Subject': {'text': 'Iris measurement report'},
                     'To': {'text': 'reviewer@example.invalid'},
                     'container_id': '28'}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['24:Output->27:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'draft_report_email'},
                              'attributes': {'DisplayMode': '0'}},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.Email.Email',
               'raw_gui_settings': {'Position': {'attributes': {'x': '1700', 'y': '450'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.Email.Email'}}},
  'node_id': '27',
  'outgoing_edges': [],
  'output_anchors': [],
  'source_tool_id': '27',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.Email.Email',
  'tool_type': 'Email',
  'warnings': []},
 {'config': {'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark'},
             'raw': {}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['28:Log->29:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'inspect_completion'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'In/Out',
                           'display_name': 'Browse',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxBrowseV2',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'BrowseV2'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.BrowseV2.BrowseV2',
               'raw_gui_settings': {'Position': {'attributes': {'x': '1850', 'y': '450'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.BrowseV2.BrowseV2'}}},
  'node_id': '29',
  'outgoing_edges': [],
  'output_anchors': [],
  'source_tool_id': '29',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.BrowseV2.BrowseV2',
  'tool_type': 'BrowseV2',
  'warnings': []},
 {'config': {'DataFields': {'Field': [{'attributes': {'field': 'sepal_length', 'selected': 'True'}},
                                      {'attributes': {'field': 'petal_length',
                                                      'selected': 'True'}}]},
             'ErrorWarn': {'text': 'Ignore'},
             'KeyFields': {'Field': {'attributes': {'field': 'species'}}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'data_fields': [{'field': 'sepal_length', 'selected': True},
                                            {'field': 'petal_length', 'selected': True}],
                            'error_warn': 'Ignore',
                            'key_fields': ['species']},
             'raw': {'DataFields': {'Field': [{'attributes': {'field': 'sepal_length',
                                                              'selected': 'True'}},
                                              {'attributes': {'field': 'petal_length',
                                                              'selected': 'True'}}]},
                     'ErrorWarn': {'text': 'Ignore'},
                     'KeyFields': {'Field': {'attributes': {'field': 'species'}}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['4:Output->30:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'reshape_measurements_long'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Transform',
                           'display_name': 'Transpose',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxTranspose',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'html-plugin',
                           'tool_type': 'Transpose'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.Transpose.Transpose',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.Transpose.Transpose'}}},
  'node_id': '30',
  'outgoing_edges': ['30:Output->31:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '30',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.Transpose.Transpose',
  'tool_type': 'Transpose',
  'warnings': []},
 {'config': {'DataField': {'attributes': {'field': 'Value'}},
             'GroupFields': {'Field': {'attributes': {'field': 'species'}}},
             'HeaderField': {'attributes': {'field': 'Name'}},
             'Methods': {'Method': {'attributes': {'method': 'Sum'}}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'data_field': 'Value',
                            'group_fields': ['species'],
                            'header_field': 'Name',
                            'method': 'Sum'},
             'raw': {'DataField': {'attributes': {'field': 'Value'}},
                     'GroupFields': {'Field': {'attributes': {'field': 'species'}}},
                     'HeaderField': {'attributes': {'field': 'Name'}},
                     'Methods': {'Method': {'attributes': {'method': 'Sum'}}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['30:Output->31:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'reshape_measurements_wide'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Transform',
                           'display_name': 'CrossTab',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxCrossTab',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'html-plugin',
                           'tool_type': 'CrossTab'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.CrossTab.CrossTab',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.CrossTab.CrossTab'}}},
  'node_id': '31',
  'outgoing_edges': [],
  'output_anchors': [],
  'source_tool_id': '31',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.CrossTab.CrossTab',
  'tool_type': 'CrossTab',
  'warnings': []},
 {'config': {'Field': {'text': 'measurement_key'},
             'Method': {'text': 'Replace'},
             'RegExExpression': {'attributes': {'value': '\\|'}},
             'Replace': {'attributes': {'expression': '_'}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'case_insensitive': True,
                            'copy_unmatched': True,
                            'field': 'measurement_key',
                            'match_field': 'measurement_key_Matched',
                            'method': 'Replace',
                            'parse_complex_fields': [],
                            'parse_simple': {'num_fields': 1,
                                             'root_name': 'measurement_key',
                                             'split_to_rows': False},
                            'regex_expression': '\\|',
                            'replace_expression': '_'},
             'raw': {'Field': {'text': 'measurement_key'},
                     'Method': {'text': 'Replace'},
                     'RegExExpression': {'attributes': {'value': '\\|'}},
                     'Replace': {'attributes': {'expression': '_'}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['5:Output->32:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'normalize_measurement_key'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Parse',
                           'display_name': 'RegEx',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxRegEx',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'html-plugin',
                           'tool_type': 'RegEx'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.RegEx.RegEx',
               'raw_gui_settings': {'Position': {'attributes': {'x': '500', 'y': '700'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.RegEx.RegEx'}}},
  'node_id': '32',
  'outgoing_edges': ['32:Output->33:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '32',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.RegEx.RegEx',
  'tool_type': 'RegEx',
  'warnings': []},
 {'config': {'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'fields': []},
             'raw': {}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['32:Output->33:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'infer_field_widths'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Auto Field',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxAutoField',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'AutoField'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.AutoField.AutoField',
               'raw_gui_settings': {'Position': {'attributes': {'x': '600', 'y': '700'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.AutoField.AutoField'}}},
  'node_id': '33',
  'outgoing_edges': ['33:Output->34:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '33',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.AutoField.AutoField',
  'tool_type': 'AutoField',
  'warnings': []},
 {'config': {'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark'},
             'raw': {}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['33:Output->34:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'inspect_field_contracts'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Developer',
                           'display_name': 'Field Info',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxFieldInfo',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'FieldInfo'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.FieldInfo.FieldInfo',
               'raw_gui_settings': {'Position': {'attributes': {'x': '750', 'y': '700'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.FieldInfo.FieldInfo'}}},
  'node_id': '34',
  'outgoing_edges': [],
  'output_anchors': [],
  'source_tool_id': '34',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.FieldInfo.FieldInfo',
  'tool_type': 'FieldInfo',
  'warnings': []},
 {'config': {'CreateField_Name': {'text': 'replicate'},
             'CreateField_Size': {'text': '4'},
             'CreateField_Type': {'text': 'Int32'},
             'Expression_Cond': {'text': '[replicate] <= 2'},
             'Expression_Init': {'text': '1'},
             'Expression_Loop': {'text': '[replicate] + 1'},
             'UpdateField': {'attributes': {'value': 'False'}},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'create_field_name': 'replicate',
                            'create_field_size': 4,
                            'create_field_type': 'Int32',
                            'expression_cond': '[replicate] <= 2',
                            'expression_init': '1',
                            'expression_loop': '[replicate] + 1',
                            'update_field': False,
                            'update_field_name': ''},
             'raw': {'CreateField_Name': {'text': 'replicate'},
                     'CreateField_Size': {'text': '4'},
                     'CreateField_Type': {'text': 'Int32'},
                     'Expression_Cond': {'text': '[replicate] <= 2'},
                     'Expression_Init': {'text': '1'},
                     'Expression_Loop': {'text': '[replicate] + 1'},
                     'UpdateField': {'attributes': {'value': 'False'}}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['4:Output->35:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'generate_measurement_replicates'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Generate Rows',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxGenerateRows',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'GenerateRows'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.GenerateRows.GenerateRows',
               'raw_gui_settings': {'Position': {'attributes': {'x': '800', 'y': '700'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.GenerateRows.GenerateRows'}}},
  'node_id': '35',
  'outgoing_edges': ['35:Output->36:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '35',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.GenerateRows.GenerateRows',
  'tool_type': 'GenerateRows',
  'warnings': []},
 {'config': {'CopyOutput': {'attributes': {'value': 'True'}},
             'Expression': {'text': '[_CurrentField_] * 2'},
             'Fields': {'Field': [{'attributes': {'name': 'sepal_length'}},
                                  {'attributes': {'name': 'petal_length'}}]},
             'NewFieldAddOn': {'text': '_doubled'},
             'NewFieldAddOnPos': {'text': 'Suffix'},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'change_field_type': False,
                            'copy_output': True,
                            'expression': '[_CurrentField_] * 2',
                            'field_type': '',
                            'fields': ['sepal_length', 'petal_length'],
                            'new_field_add_on': '_doubled',
                            'new_field_add_on_pos': 'Suffix',
                            'output_field_type': {}},
             'raw': {'CopyOutput': {'attributes': {'value': 'True'}},
                     'Expression': {'text': '[_CurrentField_] * 2'},
                     'Fields': {'Field': [{'attributes': {'name': 'sepal_length'}},
                                          {'attributes': {'name': 'petal_length'}}]},
                     'NewFieldAddOn': {'text': '_doubled'},
                     'NewFieldAddOnPos': {'text': 'Suffix'}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['35:Output->36:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'scale_multiple_measurements'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Multi-Field Formula',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxMultiFieldFormula',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'MultiFieldFormula'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.MultiFieldFormula.MultiFieldFormula',
               'raw_gui_settings': {'Position': {'attributes': {'x': '950', 'y': '700'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.MultiFieldFormula.MultiFieldFormula'}}},
  'node_id': '36',
  'outgoing_edges': ['36:Output->37:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '36',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.MultiFieldFormula.MultiFieldFormula',
  'tool_type': 'MultiFieldFormula',
  'warnings': []},
 {'config': {'CreateField_Name': {'text': 'petal_delta'},
             'CreateField_Size': {'text': '254'},
             'CreateField_Type': {'text': 'Double'},
             'Expression': {'text': '[scaled_petal_length] - [Row-1:scaled_petal_length]'},
             'GroupByFields': {},
             'NumRows': {'attributes': {'value': '1'}},
             'OtherRows': {'text': 'Empty'},
             'UpdateField': {'attributes': {'value': 'False'}},
             'UpdateField_Name': {},
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'create_field_name': 'petal_delta',
                            'create_field_size': '254',
                            'create_field_type': 'Double',
                            'expression': '[scaled_petal_length] - [Row-1:scaled_petal_length]',
                            'group_by_fields': [],
                            'num_rows': 1,
                            'other_rows': 'Empty',
                            'update_field': False,
                            'update_field_name': ''},
             'raw': {'CreateField_Name': {'text': 'petal_delta'},
                     'CreateField_Size': {'text': '254'},
                     'CreateField_Type': {'text': 'Double'},
                     'Expression': {'text': '[scaled_petal_length] - [Row-1:scaled_petal_length]'},
                     'GroupByFields': {},
                     'NumRows': {'attributes': {'value': '1'}},
                     'OtherRows': {'text': 'Empty'},
                     'UpdateField': {'attributes': {'value': 'False'}},
                     'UpdateField_Name': {}}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['36:Output->37:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'compare_previous_measurement'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Multi-Row Formula',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxMultiRowFormula',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'MultiRowFormula'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.MultiRowFormula.MultiRowFormula',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.MultiRowFormula.MultiRowFormula'}}},
  'node_id': '37',
  'outgoing_edges': [],
  'output_anchors': [],
  'source_tool_id': '37',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.MultiRowFormula.MultiRowFormula',
  'tool_type': 'MultiRowFormula',
  'warnings': []},
 {'config': {'Caption': {'text': 'Measurement preparation'},
             'child_node_ids': ['2', '3'],
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'caption': 'Measurement preparation',
                            'disabled': False,
                            'folded': False,
                            'style': {}},
             'raw': {'Caption': {'text': 'Measurement preparation'}, 'child_node_ids': ['2', '3']}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': [],
  'input_anchors': [],
  'metadata': {'catalog': {'category': 'Documentation',
                           'display_name': 'Tool Container',
                           'engine_dll': None,
                           'engine_entry': None,
                           'engine_macro': None,
                           'gui_only': True,
                           'source': 'managed-assembly',
                           'tool_type': 'ToolContainer'},
               'meta_info': {},
               'plugin_name': 'AlteryxGuiToolkit.ToolContainer.ToolContainer',
               'raw_gui_settings': {'attributes': {'Plugin': 'AlteryxGuiToolkit.ToolContainer.ToolContainer'}}},
  'node_id': '1000',
  'outgoing_edges': [],
  'output_anchors': [],
  'source_tool_id': '1000',
  'supported_status': 'L1_CONTAINER_ONLY',
  'tool_name': 'AlteryxGuiToolkit.ToolContainer.ToolContainer',
  'tool_type': 'ToolContainer',
  'warnings': []},
 {'config': {'SelectFields': {'SelectField': [{'attributes': {'field': 'F1',
                                                              'rename': 'sepal_length',
                                                              'selected': 'True',
                                                              'size': '8',
                                                              'type': 'Double'}},
                                              {'attributes': {'field': 'F2',
                                                              'rename': 'sepal_width',
                                                              'selected': 'True',
                                                              'size': '8',
                                                              'type': 'Double'}},
                                              {'attributes': {'field': 'F3',
                                                              'rename': 'petal_length',
                                                              'selected': 'True',
                                                              'size': '8',
                                                              'type': 'Double'}},
                                              {'attributes': {'field': 'F4',
                                                              'rename': 'petal_width',
                                                              'selected': 'True',
                                                              'size': '8',
                                                              'type': 'Double'}},
                                              {'attributes': {'field': 'F5',
                                                              'rename': 'species',
                                                              'selected': 'True',
                                                              'size': '32',
                                                              'type': 'V_WString'}}]},
             'container_id': '1000',
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'order_changed': None,
                            'select_fields': [{'dtype': 'Double',
                                               'forced': False,
                                               'rename': 'sepal_length',
                                               'selected': True,
                                               'size': '8',
                                               'source': 'F1'},
                                              {'dtype': 'Double',
                                               'forced': False,
                                               'rename': 'sepal_width',
                                               'selected': True,
                                               'size': '8',
                                               'source': 'F2'},
                                              {'dtype': 'Double',
                                               'forced': False,
                                               'rename': 'petal_length',
                                               'selected': True,
                                               'size': '8',
                                               'source': 'F3'},
                                              {'dtype': 'Double',
                                               'forced': False,
                                               'rename': 'petal_width',
                                               'selected': True,
                                               'size': '8',
                                               'source': 'F4'},
                                              {'dtype': 'V_WString',
                                               'forced': False,
                                               'rename': 'species',
                                               'selected': True,
                                               'size': '32',
                                               'source': 'F5'}]},
             'raw': {'SelectFields': {'SelectField': [{'attributes': {'field': 'F1',
                                                                      'rename': 'sepal_length',
                                                                      'selected': 'True',
                                                                      'size': '8',
                                                                      'type': 'Double'}},
                                                      {'attributes': {'field': 'F2',
                                                                      'rename': 'sepal_width',
                                                                      'selected': 'True',
                                                                      'size': '8',
                                                                      'type': 'Double'}},
                                                      {'attributes': {'field': 'F3',
                                                                      'rename': 'petal_length',
                                                                      'selected': 'True',
                                                                      'size': '8',
                                                                      'type': 'Double'}},
                                                      {'attributes': {'field': 'F4',
                                                                      'rename': 'petal_width',
                                                                      'selected': 'True',
                                                                      'size': '8',
                                                                      'type': 'Double'}},
                                                      {'attributes': {'field': 'F5',
                                                                      'rename': 'species',
                                                                      'selected': 'True',
                                                                      'size': '32',
                                                                      'type': 'V_WString'}}]},
                     'container_id': '1000'}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['1:Output->2:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'declare_measurement_fields'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'Select',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxSelect',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'managed-assembly',
                           'tool_type': 'Select'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect',
               'raw_gui_settings': {'Position': {'attributes': {'x': '180', 'y': '160'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect'}}},
  'node_id': '2',
  'outgoing_edges': ['2:Output->3:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '2',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect',
  'tool_type': 'Select',
  'warnings': []},
 {'config': {'FieldName': {'text': 'RecordID'},
             'FieldSize': {'text': '6'},
             'FieldType': {'text': 'Int64'},
             'Position': {'text': '0'},
             'StartValue': {'text': '1'},
             'container_id': '1000',
             'normalized': {'base_dir': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark',
                            'field_name': 'RecordID',
                            'field_size': 6,
                            'field_type': 'Int64',
                            'group_fields': [],
                            'position': 0,
                            'start_value': 1},
             'raw': {'FieldName': {'text': 'RecordID'},
                     'FieldSize': {'text': '6'},
                     'FieldType': {'text': 'Int64'},
                     'Position': {'text': '0'},
                     'StartValue': {'text': '1'},
                     'container_id': '1000'}},
  'errors': [],
  'execution_semantics_version': '0.1.0',
  'expected_input_schema': {},
  'expected_output_schema': {},
  'incoming_edges': ['2:Output->3:Input'],
  'input_anchors': [{'direction': 'input', 'name': 'Input'}],
  'metadata': {'annotation': {'DefaultAnnotationText': {},
                              'Left': {'attributes': {'value': 'False'}},
                              'Name': {'text': 'number_measurements'},
                              'attributes': {'DisplayMode': '0'}},
               'catalog': {'category': 'Preparation',
                           'display_name': 'RecordID',
                           'engine_dll': 'AlteryxBasePluginsEngine.dll',
                           'engine_entry': 'AlteryxRecordID',
                           'engine_macro': None,
                           'gui_only': False,
                           'source': 'html-plugin',
                           'tool_type': 'RecordID'},
               'meta_info': {},
               'plugin_name': 'AlteryxBasePluginsGui.RecordID.RecordID',
               'raw_gui_settings': {'Position': {'attributes': {'x': '250', 'y': '186'}},
                                    'attributes': {'Plugin': 'AlteryxBasePluginsGui.RecordID.RecordID'}}},
  'node_id': '3',
  'outgoing_edges': ['3:Output->4:Input'],
  'output_anchors': [{'direction': 'output', 'name': 'Output'}],
  'source_tool_id': '3',
  'supported_status': 'L1_PARSED_ONLY',
  'tool_name': 'AlteryxBasePluginsGui.RecordID.RecordID',
  'tool_type': 'RecordID',
  'warnings': []}]

EDGE_DATA = [{'edge_id': '1:Output->2:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '2'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '1'}}}},
  'source_anchor': 'Output',
  'source_node_id': '1',
  'target_anchor': 'Input',
  'target_node_id': '2'},
 {'edge_id': '2:Output->3:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '3'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '2'}}}},
  'source_anchor': 'Output',
  'source_node_id': '2',
  'target_anchor': 'Input',
  'target_node_id': '3'},
 {'edge_id': '3:Output->4:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '4'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '3'}}}},
  'source_anchor': 'Output',
  'source_node_id': '3',
  'target_anchor': 'Input',
  'target_node_id': '4'},
 {'edge_id': '4:Output->5:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '5'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '4'}}}},
  'source_anchor': 'Output',
  'source_node_id': '4',
  'target_anchor': 'Input',
  'target_node_id': '5'},
 {'edge_id': '5:Output->6:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '6'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '5'}}}},
  'source_anchor': 'Output',
  'source_node_id': '5',
  'target_anchor': 'Input',
  'target_node_id': '6'},
 {'edge_id': '6:True->7:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '7'}},
                       'Origin': {'attributes': {'Connection': 'True', 'ToolID': '6'}}}},
  'source_anchor': 'True',
  'source_node_id': '6',
  'target_anchor': 'Input',
  'target_node_id': '7'},
 {'edge_id': '7:Output->8:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '8'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '7'}}}},
  'source_anchor': 'Output',
  'source_node_id': '7',
  'target_anchor': 'Input',
  'target_node_id': '8'},
 {'edge_id': '8:Unique->9:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '9'}},
                       'Origin': {'attributes': {'Connection': 'Unique', 'ToolID': '8'}}}},
  'source_anchor': 'Unique',
  'source_node_id': '8',
  'target_anchor': 'Input',
  'target_node_id': '9'},
 {'edge_id': '9:Output->10:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '10'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '9'}}}},
  'source_anchor': 'Output',
  'source_node_id': '9',
  'target_anchor': 'Input',
  'target_node_id': '10'},
 {'edge_id': '10:Output->11:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '11'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '10'}}}},
  'source_anchor': 'Output',
  'source_node_id': '10',
  'target_anchor': 'Input',
  'target_node_id': '11'},
 {'edge_id': '11:Output->12:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '12'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '11'}}}},
  'source_anchor': 'Output',
  'source_node_id': '11',
  'target_anchor': 'Input',
  'target_node_id': '12'},
 {'edge_id': '12:Output->13:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '13'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '12'}}}},
  'source_anchor': 'Output',
  'source_node_id': '12',
  'target_anchor': 'Input',
  'target_node_id': '13'},
 {'edge_id': '13:Output->14:Input1',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input1', 'ToolID': '14'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '13'}}}},
  'source_anchor': 'Output',
  'source_node_id': '13',
  'target_anchor': 'Input1',
  'target_node_id': '14'},
 {'edge_id': '6:False->14:Input2',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input2', 'ToolID': '14'}},
                       'Origin': {'attributes': {'Connection': 'False', 'ToolID': '6'}}}},
  'source_anchor': 'False',
  'source_node_id': '6',
  'target_anchor': 'Input2',
  'target_node_id': '14'},
 {'edge_id': '14:Output2->15:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '15'}},
                       'Origin': {'attributes': {'Connection': 'Output2', 'ToolID': '14'}}}},
  'source_anchor': 'Output2',
  'source_node_id': '14',
  'target_anchor': 'Input',
  'target_node_id': '15'},
 {'edge_id': '14:Output1->17:Left',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Left', 'ToolID': '17'}},
                       'Origin': {'attributes': {'Connection': 'Output1', 'ToolID': '14'}}}},
  'source_anchor': 'Output1',
  'source_node_id': '14',
  'target_anchor': 'Left',
  'target_node_id': '17'},
 {'edge_id': '16:Output->17:Right',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Right', 'ToolID': '17'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '16'}}}},
  'source_anchor': 'Output',
  'source_node_id': '16',
  'target_anchor': 'Right',
  'target_node_id': '17'},
 {'edge_id': '17:Join->18:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '18'}},
                       'Origin': {'attributes': {'Connection': 'Join', 'ToolID': '17'}}}},
  'source_anchor': 'Join',
  'source_node_id': '17',
  'target_anchor': 'Input',
  'target_node_id': '18'},
 {'edge_id': '18:Output->19:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '19'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '18'}}}},
  'source_anchor': 'Output',
  'source_node_id': '18',
  'target_anchor': 'Input',
  'target_node_id': '19'},
 {'edge_id': '19:Output->20:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '20'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '19'}}}},
  'source_anchor': 'Output',
  'source_node_id': '19',
  'target_anchor': 'Input',
  'target_node_id': '20'},
 {'edge_id': '19:Output2->21:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '21'}},
                       'Origin': {'attributes': {'Connection': 'Output2', 'ToolID': '19'}}}},
  'source_anchor': 'Output2',
  'source_node_id': '19',
  'target_anchor': 'Input',
  'target_node_id': '21'},
 {'edge_id': '22:Output->23:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '23'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '22'}}}},
  'source_anchor': 'Output',
  'source_node_id': '22',
  'target_anchor': 'Input',
  'target_node_id': '23'},
 {'edge_id': '21:Output->23:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '23'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '21'}}}},
  'source_anchor': 'Output',
  'source_node_id': '21',
  'target_anchor': 'Input',
  'target_node_id': '23'},
 {'edge_id': '23:Output->24:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '24'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '23'}}}},
  'source_anchor': 'Output',
  'source_node_id': '23',
  'target_anchor': 'Input',
  'target_node_id': '24'},
 {'edge_id': '24:Output->25:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '25'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '24'}}}},
  'source_anchor': 'Output',
  'source_node_id': '24',
  'target_anchor': 'Input',
  'target_node_id': '25'},
 {'edge_id': '19:Output3->26:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '26'}},
                       'Origin': {'attributes': {'Connection': 'Output3', 'ToolID': '19'}}}},
  'source_anchor': 'Output3',
  'source_node_id': '19',
  'target_anchor': 'Input',
  'target_node_id': '26'},
 {'edge_id': '24:Output->27:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '27'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '24'}}}},
  'source_anchor': 'Output',
  'source_node_id': '24',
  'target_anchor': 'Input',
  'target_node_id': '27'},
 {'edge_id': '26:Output->28:Control',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Control', 'ToolID': '28'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '26'}}}},
  'source_anchor': 'Output',
  'source_node_id': '26',
  'target_anchor': 'Control',
  'target_node_id': '28'},
 {'edge_id': '28:Log->29:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '29'}},
                       'Origin': {'attributes': {'Connection': 'Log', 'ToolID': '28'}}}},
  'source_anchor': 'Log',
  'source_node_id': '28',
  'target_anchor': 'Input',
  'target_node_id': '29'},
 {'edge_id': '4:Output->30:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '30'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '4'}}}},
  'source_anchor': 'Output',
  'source_node_id': '4',
  'target_anchor': 'Input',
  'target_node_id': '30'},
 {'edge_id': '30:Output->31:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '31'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '30'}}}},
  'source_anchor': 'Output',
  'source_node_id': '30',
  'target_anchor': 'Input',
  'target_node_id': '31'},
 {'edge_id': '5:Output->32:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '32'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '5'}}}},
  'source_anchor': 'Output',
  'source_node_id': '5',
  'target_anchor': 'Input',
  'target_node_id': '32'},
 {'edge_id': '32:Output->33:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '33'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '32'}}}},
  'source_anchor': 'Output',
  'source_node_id': '32',
  'target_anchor': 'Input',
  'target_node_id': '33'},
 {'edge_id': '33:Output->34:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '34'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '33'}}}},
  'source_anchor': 'Output',
  'source_node_id': '33',
  'target_anchor': 'Input',
  'target_node_id': '34'},
 {'edge_id': '4:Output->35:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '35'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '4'}}}},
  'source_anchor': 'Output',
  'source_node_id': '4',
  'target_anchor': 'Input',
  'target_node_id': '35'},
 {'edge_id': '35:Output->36:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '36'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '35'}}}},
  'source_anchor': 'Output',
  'source_node_id': '35',
  'target_anchor': 'Input',
  'target_node_id': '36'},
 {'edge_id': '36:Output->37:Input',
  'metadata': {'raw': {'Destination': {'attributes': {'Connection': 'Input', 'ToolID': '37'}},
                       'Origin': {'attributes': {'Connection': 'Output', 'ToolID': '36'}}}},
  'source_anchor': 'Output',
  'source_node_id': '36',
  'target_anchor': 'Input',
  'target_node_id': '37'}]
WORKFLOW_DATA = {'classification': 'CLASS_D_PARTIAL_MIGRATION_ONLY',
 'errors': [],
 'external_dependencies': ['data/iris.data',
                           'output/rejected_measurements.csv',
                           'output/species_summary.csv'],
 'inputs': [],
 'macros': [],
 'metadata': {'embedded_macros': {'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark\\BenchmarkParallelBlock.yxmc': '<AlteryxDocument '
                                                                                                                               'yxmdVer="2022.1">\n'
                                                                                                                               '  '
                                                                                                                               '<Nodes>\n'
                                                                                                                               '    '
                                                                                                                               '<Node '
                                                                                                                               'ToolID="1">\n'
                                                                                                                               '      '
                                                                                                                               '<GuiSettings '
                                                                                                                               'Plugin="AlteryxBasePluginsGui.MacroInput.MacroInput">\n'
                                                                                                                               '        '
                                                                                                                               '<Position '
                                                                                                                               'x="54" '
                                                                                                                               'y="54" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '</GuiSettings>\n'
                                                                                                                               '      '
                                                                                                                               '<Properties>\n'
                                                                                                                               '        '
                                                                                                                               '<Configuration>\n'
                                                                                                                               '          '
                                                                                                                               '<Name>Input1</Name>\n'
                                                                                                                               '        '
                                                                                                                               '</Configuration>\n'
                                                                                                                               '        '
                                                                                                                               '<Annotation '
                                                                                                                               'DisplayMode="0">\n'
                                                                                                                               '          '
                                                                                                                               '<Name '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<DefaultAnnotationText '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<Left '
                                                                                                                               'value="False" '
                                                                                                                               '/>\n'
                                                                                                                               '        '
                                                                                                                               '</Annotation>\n'
                                                                                                                               '      '
                                                                                                                               '</Properties>\n'
                                                                                                                               '      '
                                                                                                                               '<EngineSettings '
                                                                                                                               'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                               'EngineDllEntryPoint="AlteryxMacroInput" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Node>\n'
                                                                                                                               '    '
                                                                                                                               '<Node '
                                                                                                                               'ToolID="2">\n'
                                                                                                                               '      '
                                                                                                                               '<GuiSettings '
                                                                                                                               'Plugin="AlteryxBasePluginsGui.MacroInput.MacroInput">\n'
                                                                                                                               '        '
                                                                                                                               '<Position '
                                                                                                                               'x="54" '
                                                                                                                               'y="250" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '</GuiSettings>\n'
                                                                                                                               '      '
                                                                                                                               '<Properties>\n'
                                                                                                                               '        '
                                                                                                                               '<Configuration>\n'
                                                                                                                               '          '
                                                                                                                               '<Name>Input2</Name>\n'
                                                                                                                               '        '
                                                                                                                               '</Configuration>\n'
                                                                                                                               '        '
                                                                                                                               '<Annotation '
                                                                                                                               'DisplayMode="0">\n'
                                                                                                                               '          '
                                                                                                                               '<Name '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<DefaultAnnotationText '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<Left '
                                                                                                                               'value="False" '
                                                                                                                               '/>\n'
                                                                                                                               '        '
                                                                                                                               '</Annotation>\n'
                                                                                                                               '      '
                                                                                                                               '</Properties>\n'
                                                                                                                               '      '
                                                                                                                               '<EngineSettings '
                                                                                                                               'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                               'EngineDllEntryPoint="AlteryxMacroInput" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Node>\n'
                                                                                                                               '    '
                                                                                                                               '<Node '
                                                                                                                               'ToolID="3">\n'
                                                                                                                               '      '
                                                                                                                               '<GuiSettings '
                                                                                                                               'Plugin="AlteryxBasePluginsGui.BlockUntilDone.BlockUntilDone">\n'
                                                                                                                               '        '
                                                                                                                               '<Position '
                                                                                                                               'x="200" '
                                                                                                                               'y="54" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '</GuiSettings>\n'
                                                                                                                               '      '
                                                                                                                               '<Properties>\n'
                                                                                                                               '        '
                                                                                                                               '<Configuration '
                                                                                                                               '/>\n'
                                                                                                                               '        '
                                                                                                                               '<Annotation '
                                                                                                                               'DisplayMode="0">\n'
                                                                                                                               '          '
                                                                                                                               '<Name '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<DefaultAnnotationText '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<Left '
                                                                                                                               'value="False" '
                                                                                                                               '/>\n'
                                                                                                                               '        '
                                                                                                                               '</Annotation>\n'
                                                                                                                               '      '
                                                                                                                               '</Properties>\n'
                                                                                                                               '      '
                                                                                                                               '<EngineSettings '
                                                                                                                               'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                               'EngineDllEntryPoint="AlteryxBlockUntilDone" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Node>\n'
                                                                                                                               '    '
                                                                                                                               '<Node '
                                                                                                                               'ToolID="4">\n'
                                                                                                                               '      '
                                                                                                                               '<GuiSettings '
                                                                                                                               'Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput">\n'
                                                                                                                               '        '
                                                                                                                               '<Position '
                                                                                                                               'x="400" '
                                                                                                                               'y="54" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '</GuiSettings>\n'
                                                                                                                               '      '
                                                                                                                               '<Properties>\n'
                                                                                                                               '        '
                                                                                                                               '<Configuration>\n'
                                                                                                                               '          '
                                                                                                                               '<Name>Output1</Name>\n'
                                                                                                                               '        '
                                                                                                                               '</Configuration>\n'
                                                                                                                               '        '
                                                                                                                               '<Annotation '
                                                                                                                               'DisplayMode="0">\n'
                                                                                                                               '          '
                                                                                                                               '<Name '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<DefaultAnnotationText '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<Left '
                                                                                                                               'value="False" '
                                                                                                                               '/>\n'
                                                                                                                               '        '
                                                                                                                               '</Annotation>\n'
                                                                                                                               '      '
                                                                                                                               '</Properties>\n'
                                                                                                                               '      '
                                                                                                                               '<EngineSettings '
                                                                                                                               'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                               'EngineDllEntryPoint="AlteryxMacroOutput" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Node>\n'
                                                                                                                               '    '
                                                                                                                               '<Node '
                                                                                                                               'ToolID="5">\n'
                                                                                                                               '      '
                                                                                                                               '<GuiSettings '
                                                                                                                               'Plugin="AlteryxBasePluginsGui.Sample.Sample">\n'
                                                                                                                               '        '
                                                                                                                               '<Position '
                                                                                                                               'x="250" '
                                                                                                                               'y="186" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '</GuiSettings>\n'
                                                                                                                               '      '
                                                                                                                               '<Properties>\n'
                                                                                                                               '        '
                                                                                                                               '<Configuration>\n'
                                                                                                                               '          '
                                                                                                                               '<Mode>First</Mode>\n'
                                                                                                                               '          '
                                                                                                                               '<N>1</N>\n'
                                                                                                                               '          '
                                                                                                                               '<GroupFields '
                                                                                                                               'orderChanged="False" '
                                                                                                                               '/>\n'
                                                                                                                               '        '
                                                                                                                               '</Configuration>\n'
                                                                                                                               '        '
                                                                                                                               '<Annotation '
                                                                                                                               'DisplayMode="0">\n'
                                                                                                                               '          '
                                                                                                                               '<Name '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<DefaultAnnotationText '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<Left '
                                                                                                                               'value="False" '
                                                                                                                               '/>\n'
                                                                                                                               '        '
                                                                                                                               '</Annotation>\n'
                                                                                                                               '      '
                                                                                                                               '</Properties>\n'
                                                                                                                               '      '
                                                                                                                               '<EngineSettings '
                                                                                                                               'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                               'EngineDllEntryPoint="AlteryxSample" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Node>\n'
                                                                                                                               '    '
                                                                                                                               '<Node '
                                                                                                                               'ToolID="6">\n'
                                                                                                                               '      '
                                                                                                                               '<GuiSettings '
                                                                                                                               'Plugin="AlteryxBasePluginsGui.Formula.Formula">\n'
                                                                                                                               '        '
                                                                                                                               '<Position '
                                                                                                                               'x="250" '
                                                                                                                               'y="186" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '</GuiSettings>\n'
                                                                                                                               '      '
                                                                                                                               '<Properties>\n'
                                                                                                                               '        '
                                                                                                                               '<Configuration>\n'
                                                                                                                               '          '
                                                                                                                               '<FormulaFields>\n'
                                                                                                                               '            '
                                                                                                                               '<FormulaField '
                                                                                                                               'field="__benchmark_gate" '
                                                                                                                               'size="1" '
                                                                                                                               'type="Byte" '
                                                                                                                               'expression="1" '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '</FormulaFields>\n'
                                                                                                                               '        '
                                                                                                                               '</Configuration>\n'
                                                                                                                               '        '
                                                                                                                               '<Annotation '
                                                                                                                               'DisplayMode="0">\n'
                                                                                                                               '          '
                                                                                                                               '<Name '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<DefaultAnnotationText '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<Left '
                                                                                                                               'value="False" '
                                                                                                                               '/>\n'
                                                                                                                               '        '
                                                                                                                               '</Annotation>\n'
                                                                                                                               '      '
                                                                                                                               '</Properties>\n'
                                                                                                                               '      '
                                                                                                                               '<EngineSettings '
                                                                                                                               'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                               'EngineDllEntryPoint="AlteryxFormula" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Node>\n'
                                                                                                                               '    '
                                                                                                                               '<Node '
                                                                                                                               'ToolID="7">\n'
                                                                                                                               '      '
                                                                                                                               '<GuiSettings '
                                                                                                                               'Plugin="AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect">\n'
                                                                                                                               '        '
                                                                                                                               '<Position '
                                                                                                                               'x="250" '
                                                                                                                               'y="186" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '</GuiSettings>\n'
                                                                                                                               '      '
                                                                                                                               '<Properties>\n'
                                                                                                                               '        '
                                                                                                                               '<Configuration>\n'
                                                                                                                               '          '
                                                                                                                               '<OrderChanged '
                                                                                                                               'value="False" '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<CommaDecimal '
                                                                                                                               'value="False" '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<SelectFields>\n'
                                                                                                                               '            '
                                                                                                                               '<SelectField '
                                                                                                                               'field="__benchmark_gate" '
                                                                                                                               'selected="True" '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '</SelectFields>\n'
                                                                                                                               '        '
                                                                                                                               '</Configuration>\n'
                                                                                                                               '        '
                                                                                                                               '<Annotation '
                                                                                                                               'DisplayMode="0">\n'
                                                                                                                               '          '
                                                                                                                               '<Name '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<DefaultAnnotationText '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<Left '
                                                                                                                               'value="False" '
                                                                                                                               '/>\n'
                                                                                                                               '        '
                                                                                                                               '</Annotation>\n'
                                                                                                                               '      '
                                                                                                                               '</Properties>\n'
                                                                                                                               '      '
                                                                                                                               '<EngineSettings '
                                                                                                                               'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                               'EngineDllEntryPoint="AlteryxSelect" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Node>\n'
                                                                                                                               '    '
                                                                                                                               '<Node '
                                                                                                                               'ToolID="8">\n'
                                                                                                                               '      '
                                                                                                                               '<GuiSettings '
                                                                                                                               'Plugin="AlteryxBasePluginsGui.AppendFields.AppendFields">\n'
                                                                                                                               '        '
                                                                                                                               '<Position '
                                                                                                                               'x="500" '
                                                                                                                               'y="250" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '</GuiSettings>\n'
                                                                                                                               '      '
                                                                                                                               '<Properties>\n'
                                                                                                                               '        '
                                                                                                                               '<Configuration>\n'
                                                                                                                               '          '
                                                                                                                               '<CartesianMode>Error</CartesianMode>\n'
                                                                                                                               '          '
                                                                                                                               '<SelectConfiguration>\n'
                                                                                                                               '            '
                                                                                                                               '<Configuration>\n'
                                                                                                                               '              '
                                                                                                                               '<SelectFields>\n'
                                                                                                                               '                '
                                                                                                                               '<SelectField '
                                                                                                                               'field="Source___benchmark_gate" '
                                                                                                                               'selected="False" '
                                                                                                                               '/>\n'
                                                                                                                               '                '
                                                                                                                               '<SelectField '
                                                                                                                               'field="*Unknown" '
                                                                                                                               'selected="True" '
                                                                                                                               '/>\n'
                                                                                                                               '              '
                                                                                                                               '</SelectFields>\n'
                                                                                                                               '            '
                                                                                                                               '</Configuration>\n'
                                                                                                                               '          '
                                                                                                                               '</SelectConfiguration>\n'
                                                                                                                               '        '
                                                                                                                               '</Configuration>\n'
                                                                                                                               '        '
                                                                                                                               '<Annotation '
                                                                                                                               'DisplayMode="0">\n'
                                                                                                                               '          '
                                                                                                                               '<Name '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<DefaultAnnotationText '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<Left '
                                                                                                                               'value="False" '
                                                                                                                               '/>\n'
                                                                                                                               '        '
                                                                                                                               '</Annotation>\n'
                                                                                                                               '      '
                                                                                                                               '</Properties>\n'
                                                                                                                               '      '
                                                                                                                               '<EngineSettings '
                                                                                                                               'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                               'EngineDllEntryPoint="AlteryxAppendFields" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Node>\n'
                                                                                                                               '    '
                                                                                                                               '<Node '
                                                                                                                               'ToolID="9">\n'
                                                                                                                               '      '
                                                                                                                               '<GuiSettings '
                                                                                                                               'Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput">\n'
                                                                                                                               '        '
                                                                                                                               '<Position '
                                                                                                                               'x="650" '
                                                                                                                               'y="250" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '</GuiSettings>\n'
                                                                                                                               '      '
                                                                                                                               '<Properties>\n'
                                                                                                                               '        '
                                                                                                                               '<Configuration>\n'
                                                                                                                               '          '
                                                                                                                               '<Name>Output2</Name>\n'
                                                                                                                               '        '
                                                                                                                               '</Configuration>\n'
                                                                                                                               '        '
                                                                                                                               '<Annotation '
                                                                                                                               'DisplayMode="0">\n'
                                                                                                                               '          '
                                                                                                                               '<Name '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<DefaultAnnotationText '
                                                                                                                               '/>\n'
                                                                                                                               '          '
                                                                                                                               '<Left '
                                                                                                                               'value="False" '
                                                                                                                               '/>\n'
                                                                                                                               '        '
                                                                                                                               '</Annotation>\n'
                                                                                                                               '      '
                                                                                                                               '</Properties>\n'
                                                                                                                               '      '
                                                                                                                               '<EngineSettings '
                                                                                                                               'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                               'EngineDllEntryPoint="AlteryxMacroOutput" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Node>\n'
                                                                                                                               '  '
                                                                                                                               '</Nodes>\n'
                                                                                                                               '  '
                                                                                                                               '<Connections>\n'
                                                                                                                               '    '
                                                                                                                               '<Connection>\n'
                                                                                                                               '      '
                                                                                                                               '<Origin '
                                                                                                                               'ToolID="1" '
                                                                                                                               'Connection="Output" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '<Destination '
                                                                                                                               'ToolID="3" '
                                                                                                                               'Connection="Input" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Connection>\n'
                                                                                                                               '    '
                                                                                                                               '<Connection>\n'
                                                                                                                               '      '
                                                                                                                               '<Origin '
                                                                                                                               'ToolID="3" '
                                                                                                                               'Connection="Output" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '<Destination '
                                                                                                                               'ToolID="4" '
                                                                                                                               'Connection="Input" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Connection>\n'
                                                                                                                               '    '
                                                                                                                               '<Connection>\n'
                                                                                                                               '      '
                                                                                                                               '<Origin '
                                                                                                                               'ToolID="3" '
                                                                                                                               'Connection="Output2" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '<Destination '
                                                                                                                               'ToolID="5" '
                                                                                                                               'Connection="Input" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Connection>\n'
                                                                                                                               '    '
                                                                                                                               '<Connection>\n'
                                                                                                                               '      '
                                                                                                                               '<Origin '
                                                                                                                               'ToolID="5" '
                                                                                                                               'Connection="Output" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '<Destination '
                                                                                                                               'ToolID="6" '
                                                                                                                               'Connection="Input" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Connection>\n'
                                                                                                                               '    '
                                                                                                                               '<Connection>\n'
                                                                                                                               '      '
                                                                                                                               '<Origin '
                                                                                                                               'ToolID="6" '
                                                                                                                               'Connection="Output" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '<Destination '
                                                                                                                               'ToolID="7" '
                                                                                                                               'Connection="Input" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Connection>\n'
                                                                                                                               '    '
                                                                                                                               '<Connection>\n'
                                                                                                                               '      '
                                                                                                                               '<Origin '
                                                                                                                               'ToolID="7" '
                                                                                                                               'Connection="Output" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '<Destination '
                                                                                                                               'ToolID="8" '
                                                                                                                               'Connection="Source" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Connection>\n'
                                                                                                                               '    '
                                                                                                                               '<Connection>\n'
                                                                                                                               '      '
                                                                                                                               '<Origin '
                                                                                                                               'ToolID="2" '
                                                                                                                               'Connection="Output" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '<Destination '
                                                                                                                               'ToolID="8" '
                                                                                                                               'Connection="Targets" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Connection>\n'
                                                                                                                               '    '
                                                                                                                               '<Connection>\n'
                                                                                                                               '      '
                                                                                                                               '<Origin '
                                                                                                                               'ToolID="8" '
                                                                                                                               'Connection="Output" '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '<Destination '
                                                                                                                               'ToolID="9" '
                                                                                                                               'Connection="Input" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '</Connection>\n'
                                                                                                                               '  '
                                                                                                                               '</Connections>\n'
                                                                                                                               '  '
                                                                                                                               '<Properties>\n'
                                                                                                                               '    '
                                                                                                                               '<Memory '
                                                                                                                               'default="True" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '<GlobalRecordLimit '
                                                                                                                               'value="0" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '<TempFiles '
                                                                                                                               'fileCollation="True" '
                                                                                                                               '/>\n'
                                                                                                                               '    '
                                                                                                                               '<RuntimeProperties>\n'
                                                                                                                               '      '
                                                                                                                               '<Actions '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '<Questions '
                                                                                                                               '/>\n'
                                                                                                                               '      '
                                                                                                                               '<ModuleType>Macro</ModuleType>\n'
                                                                                                                               '    '
                                                                                                                               '</RuntimeProperties>\n'
                                                                                                                               '    '
                                                                                                                               '<MetaInfo>\n'
                                                                                                                               '      '
                                                                                                                               '<Name>Benchmark '
                                                                                                                               'Parallel '
                                                                                                                               'Block '
                                                                                                                               'Until '
                                                                                                                               'Done</Name>\n'
                                                                                                                               '      '
                                                                                                                               '<MigrationContract>ordered-outputs-v1</MigrationContract>\n'
                                                                                                                               '    '
                                                                                                                               '</MetaInfo>\n'
                                                                                                                               '  '
                                                                                                                               '</Properties>\n'
                                                                                                                               '</AlteryxDocument>',
                                  'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark\\NormalizeMeasurements.yxmc': '<AlteryxDocument '
                                                                                                                              'yxmdVer="2022.1">\n'
                                                                                                                              '  '
                                                                                                                              '<Nodes>\n'
                                                                                                                              '    '
                                                                                                                              '<Node '
                                                                                                                              'ToolID="1">\n'
                                                                                                                              '      '
                                                                                                                              '<GuiSettings '
                                                                                                                              'Plugin="AlteryxBasePluginsGui.MacroInput.MacroInput">\n'
                                                                                                                              '        '
                                                                                                                              '<Position '
                                                                                                                              'x="54" '
                                                                                                                              'y="100" '
                                                                                                                              '/>\n'
                                                                                                                              '      '
                                                                                                                              '</GuiSettings>\n'
                                                                                                                              '      '
                                                                                                                              '<Properties>\n'
                                                                                                                              '        '
                                                                                                                              '<Configuration>\n'
                                                                                                                              '          '
                                                                                                                              '<Name>Input</Name>\n'
                                                                                                                              '          '
                                                                                                                              '<Abbrev>I</Abbrev>\n'
                                                                                                                              '        '
                                                                                                                              '</Configuration>\n'
                                                                                                                              '        '
                                                                                                                              '<Annotation '
                                                                                                                              'DisplayMode="0">\n'
                                                                                                                              '          '
                                                                                                                              '<Name '
                                                                                                                              '/>\n'
                                                                                                                              '          '
                                                                                                                              '<DefaultAnnotationText '
                                                                                                                              '/>\n'
                                                                                                                              '          '
                                                                                                                              '<Left '
                                                                                                                              'value="False" '
                                                                                                                              '/>\n'
                                                                                                                              '        '
                                                                                                                              '</Annotation>\n'
                                                                                                                              '      '
                                                                                                                              '</Properties>\n'
                                                                                                                              '      '
                                                                                                                              '<EngineSettings '
                                                                                                                              'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                              'EngineDllEntryPoint="AlteryxMacroInput" '
                                                                                                                              '/>\n'
                                                                                                                              '    '
                                                                                                                              '</Node>\n'
                                                                                                                              '    '
                                                                                                                              '<Node '
                                                                                                                              'ToolID="2">\n'
                                                                                                                              '      '
                                                                                                                              '<GuiSettings '
                                                                                                                              'Plugin="AlteryxBasePluginsGui.Formula.Formula">\n'
                                                                                                                              '        '
                                                                                                                              '<Position '
                                                                                                                              'x="250" '
                                                                                                                              'y="186" '
                                                                                                                              '/>\n'
                                                                                                                              '      '
                                                                                                                              '</GuiSettings>\n'
                                                                                                                              '      '
                                                                                                                              '<Properties>\n'
                                                                                                                              '        '
                                                                                                                              '<Configuration>\n'
                                                                                                                              '          '
                                                                                                                              '<FormulaFields>\n'
                                                                                                                              '            '
                                                                                                                              '<FormulaField '
                                                                                                                              'field="species" '
                                                                                                                              'size="24" '
                                                                                                                              'type="V_WString" '
                                                                                                                              'expression="Replace([species], '
                                                                                                                              '&quot;Iris-&quot;, '
                                                                                                                              '&quot;&quot;)" '
                                                                                                                              '/>\n'
                                                                                                                              '            '
                                                                                                                              '<FormulaField '
                                                                                                                              'field="scaled_petal_length" '
                                                                                                                              'size="8" '
                                                                                                                              'type="Double" '
                                                                                                                              'expression="[petal_length] '
                                                                                                                              '* '
                                                                                                                              'FACTOR" '
                                                                                                                              '/>\n'
                                                                                                                              '          '
                                                                                                                              '</FormulaFields>\n'
                                                                                                                              '        '
                                                                                                                              '</Configuration>\n'
                                                                                                                              '        '
                                                                                                                              '<Annotation '
                                                                                                                              'DisplayMode="0">\n'
                                                                                                                              '          '
                                                                                                                              '<Name '
                                                                                                                              '/>\n'
                                                                                                                              '          '
                                                                                                                              '<DefaultAnnotationText '
                                                                                                                              '/>\n'
                                                                                                                              '          '
                                                                                                                              '<Left '
                                                                                                                              'value="False" '
                                                                                                                              '/>\n'
                                                                                                                              '        '
                                                                                                                              '</Annotation>\n'
                                                                                                                              '      '
                                                                                                                              '</Properties>\n'
                                                                                                                              '      '
                                                                                                                              '<EngineSettings '
                                                                                                                              'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                              'EngineDllEntryPoint="AlteryxFormula" '
                                                                                                                              '/>\n'
                                                                                                                              '    '
                                                                                                                              '</Node>\n'
                                                                                                                              '    '
                                                                                                                              '<Node '
                                                                                                                              'ToolID="3">\n'
                                                                                                                              '      '
                                                                                                                              '<GuiSettings '
                                                                                                                              'Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput">\n'
                                                                                                                              '        '
                                                                                                                              '<Position '
                                                                                                                              'x="500" '
                                                                                                                              'y="100" '
                                                                                                                              '/>\n'
                                                                                                                              '      '
                                                                                                                              '</GuiSettings>\n'
                                                                                                                              '      '
                                                                                                                              '<Properties>\n'
                                                                                                                              '        '
                                                                                                                              '<Configuration>\n'
                                                                                                                              '          '
                                                                                                                              '<Name>Output</Name>\n'
                                                                                                                              '          '
                                                                                                                              '<Abbrev>O</Abbrev>\n'
                                                                                                                              '        '
                                                                                                                              '</Configuration>\n'
                                                                                                                              '        '
                                                                                                                              '<Annotation '
                                                                                                                              'DisplayMode="0">\n'
                                                                                                                              '          '
                                                                                                                              '<Name '
                                                                                                                              '/>\n'
                                                                                                                              '          '
                                                                                                                              '<DefaultAnnotationText '
                                                                                                                              '/>\n'
                                                                                                                              '          '
                                                                                                                              '<Left '
                                                                                                                              'value="False" '
                                                                                                                              '/>\n'
                                                                                                                              '        '
                                                                                                                              '</Annotation>\n'
                                                                                                                              '      '
                                                                                                                              '</Properties>\n'
                                                                                                                              '      '
                                                                                                                              '<EngineSettings '
                                                                                                                              'EngineDll="AlteryxBasePluginsEngine.dll" '
                                                                                                                              'EngineDllEntryPoint="AlteryxMacroOutput" '
                                                                                                                              '/>\n'
                                                                                                                              '    '
                                                                                                                              '</Node>\n'
                                                                                                                              '  '
                                                                                                                              '</Nodes>\n'
                                                                                                                              '  '
                                                                                                                              '<Connections>\n'
                                                                                                                              '    '
                                                                                                                              '<Connection>\n'
                                                                                                                              '      '
                                                                                                                              '<Origin '
                                                                                                                              'ToolID="1" '
                                                                                                                              'Connection="Output" '
                                                                                                                              '/>\n'
                                                                                                                              '      '
                                                                                                                              '<Destination '
                                                                                                                              'ToolID="2" '
                                                                                                                              'Connection="Input" '
                                                                                                                              '/>\n'
                                                                                                                              '    '
                                                                                                                              '</Connection>\n'
                                                                                                                              '    '
                                                                                                                              '<Connection>\n'
                                                                                                                              '      '
                                                                                                                              '<Origin '
                                                                                                                              'ToolID="2" '
                                                                                                                              'Connection="Output" '
                                                                                                                              '/>\n'
                                                                                                                              '      '
                                                                                                                              '<Destination '
                                                                                                                              'ToolID="3" '
                                                                                                                              'Connection="Input" '
                                                                                                                              '/>\n'
                                                                                                                              '    '
                                                                                                                              '</Connection>\n'
                                                                                                                              '  '
                                                                                                                              '</Connections>\n'
                                                                                                                              '  '
                                                                                                                              '<Properties>\n'
                                                                                                                              '    '
                                                                                                                              '<Memory '
                                                                                                                              'default="True" '
                                                                                                                              '/>\n'
                                                                                                                              '    '
                                                                                                                              '<GlobalRecordLimit '
                                                                                                                              'value="0" '
                                                                                                                              '/>\n'
                                                                                                                              '    '
                                                                                                                              '<TempFiles '
                                                                                                                              'fileCollation="True" '
                                                                                                                              '/>\n'
                                                                                                                              '    '
                                                                                                                              '<RuntimeProperties>\n'
                                                                                                                              '      '
                                                                                                                              '<ModuleType>Macro</ModuleType>\n'
                                                                                                                              '      '
                                                                                                                              '<Questions>\n'
                                                                                                                              '        '
                                                                                                                              '<Question>\n'
                                                                                                                              '          '
                                                                                                                              '<Type>NumericUpDown</Type>\n'
                                                                                                                              '          '
                                                                                                                              '<Name>factor</Name>\n'
                                                                                                                              '          '
                                                                                                                              '<Default>1</Default>\n'
                                                                                                                              '        '
                                                                                                                              '</Question>\n'
                                                                                                                              '      '
                                                                                                                              '</Questions>\n'
                                                                                                                              '      '
                                                                                                                              '<Actions>\n'
                                                                                                                              '        '
                                                                                                                              '<NoCondition>\n'
                                                                                                                              '          '
                                                                                                                              '<True>\n'
                                                                                                                              '            '
                                                                                                                              '<Action>\n'
                                                                                                                              '              '
                                                                                                                              '<Type>UpdateValue</Type>\n'
                                                                                                                              '              '
                                                                                                                              '<Variable>factor</Variable>\n'
                                                                                                                              '              '
                                                                                                                              '<Replace '
                                                                                                                              'value="True" '
                                                                                                                              '/>\n'
                                                                                                                              '              '
                                                                                                                              '<ReplaceText>FACTOR</ReplaceText>\n'
                                                                                                                              '              '
                                                                                                                              '<Destination>2/FormulaFields/FormulaField[2]/@expression</Destination>\n'
                                                                                                                              '            '
                                                                                                                              '</Action>\n'
                                                                                                                              '          '
                                                                                                                              '</True>\n'
                                                                                                                              '        '
                                                                                                                              '</NoCondition>\n'
                                                                                                                              '      '
                                                                                                                              '</Actions>\n'
                                                                                                                              '    '
                                                                                                                              '</RuntimeProperties>\n'
                                                                                                                              '  '
                                                                                                                              '</Properties>\n'
                                                                                                                              '</AlteryxDocument>'},
              'unresolved_macros': []},
 'migration_spec_version': '0.1.0',
 'outputs': [],
 'parser_version': '0.1.0',
 'source_file': 'E:\\Automation\\Alteryx2Python\\examples\\readable_benchmark\\comprehensive.yxwz',
 'source_hash': '5199f821a8b5aa370228b6d656aa1128ff44665ef801b75b8ee4784a362055cb',
 'source_xml': '<AlteryxDocument yxmdVer="2022.1">\n'
               '  <Nodes>\n'
               '    <Node ToolID="1">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileInput.DbFileInput">\n'
               '        <Position x="54" y="160" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <File FileFormat="0">data/iris.data</File>\n'
               '          <FormatSpecificOptions>\n'
               '            <HeaderRow>False</HeaderRow>\n'
               '            <Delimeter>,</Delimeter>\n'
               '            <CodePage>65001</CodePage>\n'
               '          </FormatSpecificOptions>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>load_measurements</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxDbFileInput" />\n'
               '    </Node>\n'
               '    <Node ToolID="4">\n'
               '      <GuiSettings />\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <Value name="factor">2</Value>\n'
               '        </Configuration>\n'
               '        <Annotation>\n'
               '          <Name>normalize_species</Name>\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings Macro="NormalizeMeasurements.yxmc" />\n'
               '    </Node>\n'
               '    <Node ToolID="5">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <FormulaFields>\n'
               '            <FormulaField field="measurement_key" size="64" type="V_WString" '
               'expression="[species] + &quot;|&quot; + ToString([RecordID])" />\n'
               '            <FormulaField field="report_date" size="10" type="Date" '
               'expression="&quot;2026-11-11&quot;" />\n'
               '            <FormulaField field="petal_cost" size="12.2" type="FixedDecimal" '
               'expression="[scaled_petal_length] * 1.25" />\n'
               '          </FormulaFields>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>calculate_report_fields</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxFormula" />\n'
               '    </Node>\n'
               '    <Node ToolID="6">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.Filter.Filter">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <Mode>Custom</Mode>\n'
               '          <Simple>\n'
               '            <Operator>=</Operator>\n'
               '            <Operands />\n'
               '          </Simple>\n'
               '          <Expression>[sepal_length] &gt;= MIN_SEPAL</Expression>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>filter_minimum_sepal_length</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxFilter" />\n'
               '    </Node>\n'
               '    <Node ToolID="7">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.TextToColumns.TextToColumns">\n'
               '        <Position x="600" y="160" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <Field>measurement_key</Field>\n'
               '          <Delimeters value="|" />\n'
               '          <NumFields value="2" />\n'
               '          <RootName>key_part</RootName>\n'
               '          <Flags value="0" />\n'
               '          <ErrorHandling>Last</ErrorHandling>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>split_measurement_key</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxTextToColumns" />\n'
               '    </Node>\n'
               '    <Node ToolID="8">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.Unique.Unique">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <UniqueFields>\n'
               '            <Field field="RecordID" />\n'
               '          </UniqueFields>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>deduplicate_measurements</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxUnique" />\n'
               '    </Node>\n'
               '    <Node ToolID="9">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.Sort.Sort">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <SortInfo locale="0">\n'
               '            <Field field="species" order="Ascending" />\n'
               '            <Field field="RecordID" order="Ascending" />\n'
               '          </SortInfo>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>sort_measurements</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxSort" />\n'
               '    </Node>\n'
               '    <Node ToolID="10">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.RunningTotal.RunningTotal">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <GroupByFields>\n'
               '            <Field field="species" />\n'
               '          </GroupByFields>\n'
               '          <RunningTotalFields>\n'
               '            <Field field="scaled_petal_length" />\n'
               '          </RunningTotalFields>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>calculate_running_totals</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxRunningTotal" />\n'
               '    </Node>\n'
               '    <Node ToolID="11">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.Rank.Rank">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <RankingModes>\n'
               '            <Mode value="Ordinal" />\n'
               '          </RankingModes>\n'
               '          <SortInfo locale="0">\n'
               '            <Field field="sepal_length" order="Descending" />\n'
               '          </SortInfo>\n'
               '          <GroupFields />\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>rank_measurements</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxRank" />\n'
               '    </Node>\n'
               '    <Node ToolID="12">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.Sample.Sample">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <Mode>First</Mode>\n'
               '          <N>120</N>\n'
               '          <GroupFields orderChanged="False" />\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>take_report_sample</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxSample" />\n'
               '    </Node>\n'
               '    <Node ToolID="13">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.Summarize.Summarize">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <SummarizeFields>\n'
               '            <SummarizeField field="species" action="GroupBy" rename="species" />\n'
               '            <SummarizeField field="sepal_length" action="Avg" '
               'rename="mean_sepal_length" />\n'
               '            <SummarizeField field="RecordID" action="Count" '
               'rename="measurement_count" />\n'
               '            <SummarizeField field="scaled_petal_length" action="Sum" '
               'rename="petal_total" />\n'
               '          </SummarizeFields>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>summarize_species</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxSpatialPluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxSummarize" />\n'
               '    </Node>\n'
               '    <Node ToolID="14">\n'
               '      <GuiSettings />\n'
               '      <Properties>\n'
               '        <Configuration />\n'
               '        <Annotation>\n'
               '          <Name>sequence_independent_streams</Name>\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings Macro="BenchmarkParallelBlock.yxmc" />\n'
               '    </Node>\n'
               '    <Node ToolID="15">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput">\n'
               '        <Position x="600" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <File MaxRecords="" '
               'FileFormat="0">output/rejected_measurements.csv</File>\n'
               '          <Passwords />\n'
               '          <FormatSpecificOptions>\n'
               '            <LineEndStyle>CRLF</LineEndStyle>\n'
               '            <Delimeter>,</Delimeter>\n'
               '            <ForceQuotes>False</ForceQuotes>\n'
               '            <HeaderRow>True</HeaderRow>\n'
               '            <CodePage>28591</CodePage>\n'
               '            <WriteBOM>True</WriteBOM>\n'
               '          </FormatSpecificOptions>\n'
               '          <MultiFile value="False" />\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>write_rejected_measurements</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxDbFileOutput" />\n'
               '    </Node>\n'
               '    <Node ToolID="16">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput">\n'
               '        <Position x="54" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <NumRows value="3" />\n'
               '          <Fields>\n'
               '            <Field name="species" />\n'
               '            <Field name="report_group" />\n'
               '          </Fields>\n'
               '          <Data>\n'
               '            <r>\n'
               '              <c>setosa</c>\n'
               '              <c>A</c>\n'
               '            </r>\n'
               '            <r>\n'
               '              <c>versicolor</c>\n'
               '              <c>B</c>\n'
               '            </r>\n'
               '            <r>\n'
               '              <c>virginica</c>\n'
               '              <c>C</c>\n'
               '            </r>\n'
               '          </Data>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>load_report_groups</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxTextInput" />\n'
               '    </Node>\n'
               '    <Node ToolID="17">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.Join.Join">\n'
               '        <Position x="800" y="160" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <JoinInfo connection="Left">\n'
               '            <Field field="species" />\n'
               '          </JoinInfo>\n'
               '          <JoinInfo connection="Right">\n'
               '            <Field field="species" />\n'
               '          </JoinInfo>\n'
               '          <SelectConfiguration>\n'
               '            <Configuration outputConnection="Join">\n'
               '              <SelectFields>\n'
               '                <SelectField field="Left_species" rename="Left_species" '
               'selected="True" />\n'
               '                <SelectField field="Left_mean_sepal_length" '
               'rename="Left_mean_sepal_length" selected="True" />\n'
               '                <SelectField field="Left_measurement_count" '
               'rename="Left_measurement_count" selected="True" />\n'
               '                <SelectField field="Left_petal_total" rename="Left_petal_total" '
               'selected="True" />\n'
               '                <SelectField field="Right_report_group" '
               'rename="Right_report_group" selected="True" />\n'
               '              </SelectFields>\n'
               '            </Configuration>\n'
               '          </SelectConfiguration>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>join_report_groups</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxJoin" />\n'
               '    </Node>\n'
               '    <Node ToolID="18">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect">\n'
               '        <Position x="900" y="160" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <SelectFields>\n'
               '            <SelectField field="Left_species" selected="True" type="V_WString" '
               'size="24" />\n'
               '            <SelectField field="Left_mean_sepal_length" selected="True" '
               'type="Double" size="8" />\n'
               '            <SelectField field="Left_measurement_count" selected="True" '
               'type="Int32" size="4" />\n'
               '            <SelectField field="Left_petal_total" selected="True" type="Double" '
               'size="8" />\n'
               '            <SelectField field="Right_report_group" selected="True" '
               'type="V_WString" size="8" />\n'
               '          </SelectFields>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>declare_report_fields</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxSelect" />\n'
               '    </Node>\n'
               '    <Node ToolID="19">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.BlockUntilDone.BlockUntilDone">\n'
               '        <Position x="1050" y="160" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration />\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>finish_outputs_in_order</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxBlockUntilDone" />\n'
               '    </Node>\n'
               '    <Node ToolID="20">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.DbFileOutput.DbFileOutput">\n'
               '        <Position x="600" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <File MaxRecords="" FileFormat="0">output/species_summary.csv</File>\n'
               '          <Passwords />\n'
               '          <FormatSpecificOptions>\n'
               '            <LineEndStyle>CRLF</LineEndStyle>\n'
               '            <Delimeter>,</Delimeter>\n'
               '            <ForceQuotes>False</ForceQuotes>\n'
               '            <HeaderRow>True</HeaderRow>\n'
               '            <CodePage>28591</CodePage>\n'
               '            <WriteBOM>True</WriteBOM>\n'
               '          </FormatSpecificOptions>\n'
               '          <MultiFile value="False" />\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>write_species_summary</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxDbFileOutput" />\n'
               '    </Node>\n'
               '    <Node ToolID="21">\n'
               '      <GuiSettings '
               'Plugin="AlteryxBasePluginsGui.PortfolioComposerTable.PortfolioComposerTable">\n'
               '        <Position x="1200" y="250" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <TableMode>Basic</TableMode>\n'
               '          <ShowHeader value="True" />\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>build_report_table</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="PortfolioPluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxPortfolioComposerTablePlugin" />\n'
               '    </Node>\n'
               '    <Node ToolID="22">\n'
               '      <GuiSettings '
               'Plugin="AlteryxBasePluginsGui.PortfolioComposerText.PortfolioComposerText">\n'
               '        <Position x="1000" y="350" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <Output>Report</Output>\n'
               '          <Message>Iris measurement report</Message>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>build_report_title</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="PortfolioPluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxPortfolioComposerTextPlugin" />\n'
               '    </Node>\n'
               '    <Node ToolID="23">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.Union.Union">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <Mode>ByName</Mode>\n'
               '          <OutputMode>Combine</OutputMode>\n'
               '          <InPerm>\n'
               '            <Input SubId="1" />\n'
               '            <Input SubId="2" />\n'
               '          </InPerm>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>combine_report_fragments</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxUnion" />\n'
               '    </Node>\n'
               '    <Node ToolID="24">\n'
               '      <GuiSettings '
               'Plugin="AlteryxBasePluginsGui.PortfolioComposerLayout.PortfolioComposerLayout">\n'
               '        <Position x="1400" y="300" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <Orientation>Vertical</Orientation>\n'
               '          <LayoutFields>\n'
               '            <Field name="Report" selected="True" />\n'
               '          </LayoutFields>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>assemble_report</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="PortfolioPluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxPortfolioComposerLayoutPlugin" />\n'
               '    </Node>\n'
               '    <Node ToolID="25">\n'
               '      <GuiSettings '
               'Plugin="AlteryxBasePluginsGui.PortfolioComposerRender.PortfolioComposerRender">\n'
               '        <Position x="1550" y="300" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <TempFileType>html</TempFileType>\n'
               '          <OutputFile>iris_report.html</OutputFile>\n'
               '          <DataField>Report</DataField>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>write_html_report</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="PortfolioPluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxPortfolioComposerRenderPlugin" />\n'
               '    </Node>\n'
               '    <Node ToolID="26">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.RunCommand.RunCommand">\n'
               '        <Position x="1250" y="450" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          '
               '<ProgramName>E:\\Automation\\Alteryx2Python\\.venv\\Scripts\\python.exe</ProgramName>\n'
               '          <Arguments>-c "from pathlib import Path; '
               'Path(\\"command-proof.txt\\").write_text(\\"command completed\\n\\")"</Arguments>\n'
               '          <WorkingDir />\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>run_postprocessing_command</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxRunCommand" />\n'
               '    </Node>\n'
               '    <Node ToolID="28">\n'
               '      <GuiSettings '
               'Plugin="AlteryxBasePluginsGui.ControlContainer.ControlContainer">\n'
               '        <Position x="1600" y="450" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <Caption>Draft after outputs finish</Caption>\n'
               '          <Disabled value="False" />\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>control_email_delivery</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxCtrlContainer" />\n'
               '      <ChildNodes>\n'
               '        <Node ToolID="27">\n'
               '          <GuiSettings Plugin="AlteryxBasePluginsGui.Email.Email">\n'
               '            <Position x="1700" y="450" />\n'
               '          </GuiSettings>\n'
               '          <Properties>\n'
               '            <Configuration>\n'
               '              <From>reports@example.invalid</From>\n'
               '              <To>reviewer@example.invalid</To>\n'
               '              <Subject>Iris measurement report</Subject>\n'
               '              <Body>Report</Body>\n'
               '              <Attachments>\n'
               '                <Attachment>iris_report.html</Attachment>\n'
               '              </Attachments>\n'
               '            </Configuration>\n'
               '            <Annotation DisplayMode="0">\n'
               '              <Name>draft_report_email</Name>\n'
               '              <DefaultAnnotationText />\n'
               '              <Left value="False" />\n'
               '            </Annotation>\n'
               '          </Properties>\n'
               '          <EngineSettings EngineDll="PortfolioPluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxComposerEmail" />\n'
               '        </Node>\n'
               '      </ChildNodes>\n'
               '    </Node>\n'
               '    <Node ToolID="29">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.BrowseV2.BrowseV2">\n'
               '        <Position x="1850" y="450" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration />\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>inspect_completion</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxBrowseV2" />\n'
               '    </Node>\n'
               '    <Node ToolID="30">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.Transpose.Transpose">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <ErrorWarn>Ignore</ErrorWarn>\n'
               '          <KeyFields>\n'
               '            <Field field="species" />\n'
               '          </KeyFields>\n'
               '          <DataFields>\n'
               '            <Field field="sepal_length" selected="True" />\n'
               '            <Field field="petal_length" selected="True" />\n'
               '          </DataFields>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>reshape_measurements_long</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxTranspose" />\n'
               '    </Node>\n'
               '    <Node ToolID="31">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.CrossTab.CrossTab">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <GroupFields>\n'
               '            <Field field="species" />\n'
               '          </GroupFields>\n'
               '          <HeaderField field="Name" />\n'
               '          <DataField field="Value" />\n'
               '          <Methods>\n'
               '            <Method method="Sum" />\n'
               '          </Methods>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>reshape_measurements_wide</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxCrossTab" />\n'
               '    </Node>\n'
               '    <Node ToolID="32">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.RegEx.RegEx">\n'
               '        <Position x="500" y="700" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <Field>measurement_key</Field>\n'
               '          <RegExExpression value="\\|" />\n'
               '          <Method>Replace</Method>\n'
               '          <Replace expression="_" />\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>normalize_measurement_key</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxRegEx" />\n'
               '    </Node>\n'
               '    <Node ToolID="33">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.AutoField.AutoField">\n'
               '        <Position x="600" y="700" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration />\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>infer_field_widths</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxAutoField" />\n'
               '    </Node>\n'
               '    <Node ToolID="34">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.FieldInfo.FieldInfo">\n'
               '        <Position x="750" y="700" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration />\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>inspect_field_contracts</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxFieldInfo" />\n'
               '    </Node>\n'
               '    <Node ToolID="35">\n'
               '      <GuiSettings Plugin="AlteryxBasePluginsGui.GenerateRows.GenerateRows">\n'
               '        <Position x="800" y="700" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <UpdateField value="False" />\n'
               '          <CreateField_Name>replicate</CreateField_Name>\n'
               '          <CreateField_Type>Int32</CreateField_Type>\n'
               '          <CreateField_Size>4</CreateField_Size>\n'
               '          <Expression_Init>1</Expression_Init>\n'
               '          <Expression_Cond>[replicate] &lt;= 2</Expression_Cond>\n'
               '          <Expression_Loop>[replicate] + 1</Expression_Loop>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>generate_measurement_replicates</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxGenerateRows" />\n'
               '    </Node>\n'
               '    <Node ToolID="36">\n'
               '      <GuiSettings '
               'Plugin="AlteryxBasePluginsGui.MultiFieldFormula.MultiFieldFormula">\n'
               '        <Position x="950" y="700" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <Fields>\n'
               '            <Field name="sepal_length" />\n'
               '            <Field name="petal_length" />\n'
               '          </Fields>\n'
               '          <CopyOutput value="True" />\n'
               '          <NewFieldAddOn>_doubled</NewFieldAddOn>\n'
               '          <NewFieldAddOnPos>Suffix</NewFieldAddOnPos>\n'
               '          <Expression>[_CurrentField_] * 2</Expression>\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>scale_multiple_measurements</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxMultiFieldFormula" />\n'
               '    </Node>\n'
               '    <Node ToolID="37">\n'
               '      <GuiSettings '
               'Plugin="AlteryxBasePluginsGui.MultiRowFormula.MultiRowFormula">\n'
               '        <Position x="250" y="186" />\n'
               '      </GuiSettings>\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <UpdateField value="False" />\n'
               '          <UpdateField_Name />\n'
               '          <CreateField_Name>petal_delta</CreateField_Name>\n'
               '          <CreateField_Type>Double</CreateField_Type>\n'
               '          <CreateField_Size>254</CreateField_Size>\n'
               '          <OtherRows>Empty</OtherRows>\n'
               '          <NumRows value="1" />\n'
               '          <Expression>[scaled_petal_length] - '
               '[Row-1:scaled_petal_length]</Expression>\n'
               '          <GroupByFields />\n'
               '        </Configuration>\n'
               '        <Annotation DisplayMode="0">\n'
               '          <Name>compare_previous_measurement</Name>\n'
               '          <DefaultAnnotationText />\n'
               '          <Left value="False" />\n'
               '        </Annotation>\n'
               '      </Properties>\n'
               '      <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxMultiRowFormula" />\n'
               '    </Node>\n'
               '    <Node ToolID="1000">\n'
               '      <GuiSettings Plugin="AlteryxGuiToolkit.ToolContainer.ToolContainer" />\n'
               '      <Properties>\n'
               '        <Configuration>\n'
               '          <Caption>Measurement preparation</Caption>\n'
               '        </Configuration>\n'
               '      </Properties>\n'
               '      <ChildNodes>\n'
               '        <Node ToolID="2">\n'
               '          <GuiSettings '
               'Plugin="AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect">\n'
               '            <Position x="180" y="160" />\n'
               '          </GuiSettings>\n'
               '          <Properties>\n'
               '            <Configuration>\n'
               '              <SelectFields>\n'
               '                <SelectField field="F1" rename="sepal_length" selected="True" '
               'type="Double" size="8" />\n'
               '                <SelectField field="F2" rename="sepal_width" selected="True" '
               'type="Double" size="8" />\n'
               '                <SelectField field="F3" rename="petal_length" selected="True" '
               'type="Double" size="8" />\n'
               '                <SelectField field="F4" rename="petal_width" selected="True" '
               'type="Double" size="8" />\n'
               '                <SelectField field="F5" rename="species" selected="True" '
               'type="V_WString" size="32" />\n'
               '              </SelectFields>\n'
               '            </Configuration>\n'
               '            <Annotation DisplayMode="0">\n'
               '              <Name>declare_measurement_fields</Name>\n'
               '              <DefaultAnnotationText />\n'
               '              <Left value="False" />\n'
               '            </Annotation>\n'
               '          </Properties>\n'
               '          <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxSelect" />\n'
               '        </Node>\n'
               '        <Node ToolID="3">\n'
               '          <GuiSettings Plugin="AlteryxBasePluginsGui.RecordID.RecordID">\n'
               '            <Position x="250" y="186" />\n'
               '          </GuiSettings>\n'
               '          <Properties>\n'
               '            <Configuration>\n'
               '              <FieldName>RecordID</FieldName>\n'
               '              <StartValue>1</StartValue>\n'
               '              <FieldType>Int64</FieldType>\n'
               '              <FieldSize>6</FieldSize>\n'
               '              <Position>0</Position>\n'
               '            </Configuration>\n'
               '            <Annotation DisplayMode="0">\n'
               '              <Name>number_measurements</Name>\n'
               '              <DefaultAnnotationText />\n'
               '              <Left value="False" />\n'
               '            </Annotation>\n'
               '          </Properties>\n'
               '          <EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" '
               'EngineDllEntryPoint="AlteryxRecordID" />\n'
               '        </Node>\n'
               '      </ChildNodes>\n'
               '    </Node>\n'
               '  </Nodes>\n'
               '  <Connections>\n'
               '    <Connection>\n'
               '      <Origin ToolID="1" Connection="Output" />\n'
               '      <Destination ToolID="2" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="2" Connection="Output" />\n'
               '      <Destination ToolID="3" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="3" Connection="Output" />\n'
               '      <Destination ToolID="4" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="4" Connection="Output" />\n'
               '      <Destination ToolID="5" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="5" Connection="Output" />\n'
               '      <Destination ToolID="6" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="6" Connection="True" />\n'
               '      <Destination ToolID="7" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="7" Connection="Output" />\n'
               '      <Destination ToolID="8" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="8" Connection="Unique" />\n'
               '      <Destination ToolID="9" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="9" Connection="Output" />\n'
               '      <Destination ToolID="10" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="10" Connection="Output" />\n'
               '      <Destination ToolID="11" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="11" Connection="Output" />\n'
               '      <Destination ToolID="12" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="12" Connection="Output" />\n'
               '      <Destination ToolID="13" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="13" Connection="Output" />\n'
               '      <Destination ToolID="14" Connection="Input1" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="6" Connection="False" />\n'
               '      <Destination ToolID="14" Connection="Input2" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="14" Connection="Output2" />\n'
               '      <Destination ToolID="15" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="14" Connection="Output1" />\n'
               '      <Destination ToolID="17" Connection="Left" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="16" Connection="Output" />\n'
               '      <Destination ToolID="17" Connection="Right" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="17" Connection="Join" />\n'
               '      <Destination ToolID="18" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="18" Connection="Output" />\n'
               '      <Destination ToolID="19" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="19" Connection="Output" />\n'
               '      <Destination ToolID="20" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="19" Connection="Output2" />\n'
               '      <Destination ToolID="21" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="22" Connection="Output" />\n'
               '      <Destination ToolID="23" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="21" Connection="Output" />\n'
               '      <Destination ToolID="23" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="23" Connection="Output" />\n'
               '      <Destination ToolID="24" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="24" Connection="Output" />\n'
               '      <Destination ToolID="25" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="19" Connection="Output3" />\n'
               '      <Destination ToolID="26" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="24" Connection="Output" />\n'
               '      <Destination ToolID="27" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="26" Connection="Output" />\n'
               '      <Destination ToolID="28" Connection="Control" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="28" Connection="Log" />\n'
               '      <Destination ToolID="29" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="4" Connection="Output" />\n'
               '      <Destination ToolID="30" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="30" Connection="Output" />\n'
               '      <Destination ToolID="31" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="5" Connection="Output" />\n'
               '      <Destination ToolID="32" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="32" Connection="Output" />\n'
               '      <Destination ToolID="33" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="33" Connection="Output" />\n'
               '      <Destination ToolID="34" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="4" Connection="Output" />\n'
               '      <Destination ToolID="35" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="35" Connection="Output" />\n'
               '      <Destination ToolID="36" Connection="Input" />\n'
               '    </Connection>\n'
               '    <Connection>\n'
               '      <Origin ToolID="36" Connection="Output" />\n'
               '      <Destination ToolID="37" Connection="Input" />\n'
               '    </Connection>\n'
               '  </Connections>\n'
               '  <Properties>\n'
               '    <Memory default="True" />\n'
               '    <GlobalRecordLimit value="0" />\n'
               '    <TempFiles fileCollation="True" />\n'
               '    <RuntimeProperties>\n'
               '      <ModuleType>Wizard</ModuleType>\n'
               '      <Questions>\n'
               '        <Question>\n'
               '          <Type>NumericUpDown</Type>\n'
               '          <Name>minimum_sepal_length</Name>\n'
               '          <Default>5</Default>\n'
               '          <Minimum>0</Minimum>\n'
               '          <Maximum>10</Maximum>\n'
               '        </Question>\n'
               '      </Questions>\n'
               '      <Actions>\n'
               '        <NoCondition>\n'
               '          <True>\n'
               '            <Action>\n'
               '              <Type>UpdateValue</Type>\n'
               '              <Variable>minimum_sepal_length</Variable>\n'
               '              <Replace value="True" />\n'
               '              <ReplaceText>MIN_SEPAL</ReplaceText>\n'
               '              <Destination>6/Expression</Destination>\n'
               '            </Action>\n'
               '          </True>\n'
               '        </NoCondition>\n'
               '      </Actions>\n'
               '    </RuntimeProperties>\n'
               '    <Events>\n'
               '      <Enabled value="True" />\n'
               '      <Event>\n'
               '        <When>Before</When>\n'
               '        <SendMail value="False" />\n'
               '        <cmd_Program>before.bat</cmd_Program>\n'
               '        <cmd_CommandLine />\n'
               '        <cmd_WorkingDir />\n'
               '        <cmd_Timeout value="30" />\n'
               '      </Event>\n'
               '      <Event>\n'
               '        <When>After</When>\n'
               '        <SendMail value="False" />\n'
               '        <cmd_Program>after.bat</cmd_Program>\n'
               '        <cmd_CommandLine />\n'
               '        <cmd_WorkingDir />\n'
               '        <cmd_Timeout value="30" />\n'
               '      </Event>\n'
               '    </Events>\n'
               '  </Properties>\n'
               '</AlteryxDocument>',
 'warnings': [],
 'workflow_id': 'comprehensive',
 'workflow_name': 'comprehensive'}

def build_workflow():
    nodes = [NodeIR(**{**node,
        'input_anchors': [AnchorIR(**anchor) for anchor in node['input_anchors']],
        'output_anchors': [AnchorIR(**anchor) for anchor in node['output_anchors']]}) for node in NODE_DATA]
    edges = [EdgeIR(**edge) for edge in EDGE_DATA]
    return WorkflowIR(
        **WORKFLOW_DATA,
        nodes=nodes,
        edges=edges,
    )


def run_workflow(runtime_config=None, initial_inputs=None, target_node_ids=None):
    context = WorkflowContext(runtime_config=runtime_config)
    result = run_workflow_graph(
        build_workflow(),
        context,
        initial_inputs=initial_inputs,
        target_node_ids=target_node_ids,
    )
    return result, context.execution_report()


if __name__ == "__main__":
    import argparse, json, sys
    from pathlib import Path
    parser = argparse.ArgumentParser(description='Run the converted workflow')
    parser.add_argument('--answers', type=Path)
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    runtime = {'answers': json.loads(args.answers.read_text(encoding='utf-8-sig'))} if args.answers else None
    if args.output_dir:
        from alteryx2python.parity.manual import export_review_results
        args.output_dir.mkdir(parents=True, exist_ok=False)
        capture = export_review_results(build_workflow(), args.output_dir, runtime_config=runtime)
        print(json.dumps({'status': capture['status'], 'failure': capture['failure'], 'output_dir': str(args.output_dir)}, ensure_ascii=False))
        sys.exit(0 if capture['status'] == 'success' else 2)
    result, trace = run_workflow(runtime_config=runtime)
    print(json.dumps({'status': 'success', 'execution_order': result.execution_order, 'outputs': {node_id: {anchor: frame.to_dict('records') for anchor, frame in node.outputs.items()} for node_id, node in result.node_results.items()}}, default=str, ensure_ascii=False))
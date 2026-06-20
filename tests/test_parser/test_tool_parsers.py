from alteryx2python.parser.tool_parsers import (
    parse_dbfileinput_config,
    parse_dbfileoutput_config,
    parse_filter_config,
    parse_formula_config,
    parse_join_config,
    parse_jsonparse_config,
    parse_recordid_config,
    parse_select_config,
    parse_sort_config,
    parse_textinput_config,
    parse_transpose_config,
    parse_union_config,
)


def test_select_parser_normalizes_select_field_entries():
    result = parse_select_config(
        {
            "SelectFields": {
                "SelectField": [
                    {"attributes": {"field": "account", "rename": "account_copy", "selected": "True"}},
                    {"attributes": {"field": "amount", "type": "Int64", "forced": "True"}},
                ]
            }
        }
    )

    assert result.normalized_config["select_fields"][0]["source"] == "account"
    assert result.normalized_config["select_fields"][0]["rename"] == "account_copy"
    assert result.normalized_config["select_fields"][1]["dtype"] == "Int64"


def test_dbfileinput_parser_normalizes_file_and_options():
    result = parse_dbfileinput_config(
        {
            "File": {"text": "input.csv", "attributes": {"FileFormat": "0"}},
            "FormatSpecificOptions": {"HeaderRow": {"attributes": {"value": "True"}}},
        }
    )

    assert result.normalized_config["file"] == "input.csv"
    assert result.normalized_config["file_attributes"]["FileFormat"] == "0"


def test_dbfileoutput_parser_normalizes_file_and_options():
    result = parse_dbfileoutput_config(
        {
            "File": {"text": "out.csv", "attributes": {"FileFormat": "0", "MaxRecords": "5"}},
            "FormatSpecificOptions": {"OutputOption": {"text": "Overwrite"}},
        }
    )

    assert result.normalized_config["file"] == "out.csv"
    assert result.normalized_config["file_attributes"]["MaxRecords"] == "5"
    assert result.normalized_config["output_option"] == "Overwrite"


def test_formula_parser_normalizes_formula_fields():
    result = parse_formula_config(
        {
            "FormulaFields": {
                "FormulaField": {
                    "attributes": {
                        "field": "FieldKey",
                        "expression": 'REGEX_Replace([JSON_Name], "[^A-Za-z0-9_]", "_")',
                        "type": "V_WString",
                        "size": "1073741823",
                        "enabled": "true",
                    }
                }
            }
        }
    )

    assert result.normalized_config["formula_fields"][0]["field"] == "FieldKey"
    assert "REGEX_Replace" in result.normalized_config["formula_fields"][0]["expression"]


def test_filter_parser_normalizes_expression_and_mode():
    result = parse_filter_config({"Expression": "StartsWith([FieldKey], \"result_\")", "Mode": "Custom"})

    assert result.normalized_config == {"expression": 'StartsWith([FieldKey], "result_")', "mode": "Custom"}


def test_jsonparse_parser_normalizes_core_flags():
    result = parse_jsonparse_config(
        {
            "JSON_Field": {"text": "DownloadData"},
            "IncludeInOutput": {"attributes": {"value": "False"}},
            "SingleField": {"attributes": {"value": "True"}},
        }
    )

    assert result.normalized_config == {"json_field": "DownloadData", "include_in_output": False, "single_field": True}


def test_textinput_parser_normalizes_fields_rows_and_empty_cells():
    result = parse_textinput_config(
        {
            "NumRows": {"attributes": {"value": "2"}},
            "Fields": {
                "Field": [
                    {"attributes": {"name": "CustomerID"}},
                    {"attributes": {"name": "LastName"}},
                ]
            },
            "Data": {
                "r": [
                    {"c": [{"text": "49"}, {"text": "Edison"}]},
                    {"c": [{"text": "456"}, {}]},
                ]
            },
        }
    )

    assert result.normalized_config == {
        "fields": ["CustomerID", "LastName"],
        "rows": [["49", "Edison"], ["456", ""]],
        "num_rows": 2,
    }
    assert result.warnings == []


def test_sort_parser_normalizes_sort_fields():
    result = parse_sort_config(
        {
            "SortInfo": {
                "attributes": {"locale": "0"},
                "Field": {"attributes": {"field": "CustomerID", "order": "Ascending"}},
            }
        }
    )

    assert result.normalized_config == {"sort_fields": [{"field": "CustomerID", "order": "Ascending"}]}


def test_recordid_parser_normalizes_core_settings():
    result = parse_recordid_config(
        {
            "FieldName": {"text": "RecordID"},
            "StartValue": {"text": "1"},
            "FieldType": {"text": "Int32"},
            "FieldSize": {"text": "6"},
            "Position": {"text": "0"},
        }
    )

    assert result.normalized_config["field_name"] == "RecordID"
    assert result.normalized_config["start_value"] == 1


def test_join_parser_normalizes_join_settings():
    result = parse_join_config(
        {
            "attributes": {"joinByRecordPos": "False"},
            "JoinInfo": [
                {"attributes": {"connection": "Left"}, "Field": {"attributes": {"field": "Name"}}},
                {"attributes": {"connection": "Right"}, "Field": {"attributes": {"field": "SourceField"}}},
            ],
            "SelectConfiguration": {
                "Configuration": {
                    "attributes": {"outputConnection": "Join"},
                    "SelectFields": {
                        "SelectField": [
                            {"attributes": {"field": "Left_RecordID", "input": "Left_"}},
                            {"attributes": {"field": "Right_TargetField", "input": "Right_"}},
                        ]
                    },
                }
            },
        }
    )

    assert result.normalized_config["joins"][0]["connection"] == "Left"
    assert result.normalized_config["select_fields"][0]["source"] == "Left_RecordID"
    assert result.normalized_config["select_fields"][0]["rename"] == "RecordID"
    assert result.normalized_config["output_connection"] == "Join"


def test_union_parser_normalizes_union_settings():
    result = parse_union_config(
        {
            "Mode": {"text": "ByName"},
            "ByName_ErrorMode": {"text": "Warning"},
            "ByName_OutputMode": {"text": "All"},
            "SetOutputOrder": {"attributes": {"value": "False"}},
        }
    )

    assert result.normalized_config["mode"] == "ByName"
    assert result.normalized_config["by_name_error_mode"] == "Warning"


def test_transpose_parser_normalizes_key_and_data_fields():
    result = parse_transpose_config(
        {
            "ErrorWarn": {"text": "Warn"},
            "KeyFields": {"Field": {"attributes": {"field": "RecordID"}}},
            "DataFields": {"Field": [{"attributes": {"field": "Trade ref", "selected": "True"}}]},
        }
    )

    assert result.normalized_config["key_fields"] == ["RecordID"]
    assert result.normalized_config["data_fields"][0]["field"] == "Trade ref"

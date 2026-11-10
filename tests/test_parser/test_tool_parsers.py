from alteryx2python.parser.tool_parsers import (
    parse_action_config,
    parse_alteryx_report_chart_config,
    parse_apioutput_config,
    parse_arrange_config,
    parse_appendfields_config,
    parse_autofield_config,
    parse_basicdataprofile_config,
    parse_blobconvert_config,
    parse_blobinput_config,
    parse_bloboutput_config,
    parse_buffer_config,
    parse_condition_config,
    parse_createpoints_config,
    parse_datacleansepro_config,
    parse_datacleansing_config,
    parse_datetime_config,
    parse_datetimenow_config,
    parse_dbfileinput_config,
    parse_dbfileoutput_config,
    parse_detour_config,
    parse_detourend_config,
    parse_distance_config,
    parse_directory_config,
    parse_download_config,
    parse_dynamicinput_config,
    parse_dynamicreplace_config,
    parse_dynamicselect_config,
    parse_error_config,
    parse_expectequal_config,
    parse_filter_config,
    parse_fieldinfo_config,
    parse_findnearest_config,
    parse_findreplace_config,
    parse_formula_config,
    parse_fuzzymatch_config,
    parse_generaterows_config,
    parse_generalize_config,
    parse_interface_layout_config,
    parse_interface_value_config,
    parse_join_config,
    parse_joinmultiple_config,
    parse_jsonparse_config,
    parse_jupytercode_config,
    parse_makecolumns_config,
    parse_makegrid_config,
    parse_makegroup_config,
    parse_macroinput_config,
    parse_mapinput_config,
    parse_multifieldformula_config,
    parse_multirowformula_config,
    parse_overlay_config,
    parse_pearsoncorrelation_config,
    parse_pdfinput_config,
    parse_pdftotext_config,
    parse_polybuild_config,
    parse_polysplit_config,
    parse_plotly_charting_config,
    parse_recordid_config,
    parse_rank_config,
    parse_regex_config,
    parse_report_image_config,
    parse_report_layout_config,
    parse_report_footer_config,
    parse_report_header_config,
    parse_report_legend_builder_config,
    parse_report_legend_splitter_config,
    parse_report_map_config,
    parse_report_render_config,
    parse_report_table_config,
    parse_report_text_config,
    parse_runningtotal_config,
    parse_runcommand_config,
    parse_sample_config,
    parse_select_config,
    parse_spatialinfo_config,
    parse_spatialmatch_config,
    parse_smooth_config,
    parse_spatialprocess_config,
    parse_sort_config,
    parse_summarize_config,
    parse_test_config,
    parse_textinput_config,
    parse_texttocolumns_config,
    parse_throttle_config,
    parse_tile_config,
    parse_tradearea_config,
    parse_transpose_config,
    parse_union_config,
    parse_unique_config,
    parse_visual_layout_config,
    parse_xmlparse_config,
)
from alteryx2python.parser.xml_parser import XmlWorkflowParser


def test_select_parser_normalizes_select_field_entries():
    result = parse_select_config(
        {
            "SelectFields": {
                "SelectField": [
                    {"attributes": {"field": "account", "rename": "account_copy", "selected": "True"}},
                    {"attributes": {"field": "amount", "type": "Int64", "forced": "True"}},
                ]
            },
            "OrderChanged": {"attributes": {"value": "True"}},
        }
    )

    assert result.normalized_config["select_fields"][0]["source"] == "account"
    assert result.normalized_config["select_fields"][0]["rename"] == "account_copy"
    assert result.normalized_config["select_fields"][1]["dtype"] == "Int64"
    assert result.normalized_config["order_changed"] is True


def test_buffer_parser_normalizes_spatial_field_and_size_config():
    result = parse_buffer_config(
        {
            "SpatialObjectField": {"text": "SpatialObject_TradeArea"},
            "IncludeSourceInOutput": {"attributes": {"value": "False"}},
            "GeneralizeToOnePercent": {"attributes": {"value": "True"}},
            "BufferSizeSource": {"text": "SpecificValue"},
            "BufferSizeSpecificValue": {"text": "-1"},
            "Units": {"text": "Miles"},
        }
    )

    assert result.normalized_config == {
        "spatial_field": "SpatialObject_TradeArea",
        "include_source": False,
        "generalize_to_one_percent": True,
        "buffer_size_source": "SpecificValue",
        "buffer_size": "-1",
        "buffer_size_field": "",
        "units": "Miles",
    }


def test_spatialinfo_parser_normalizes_selected_items():
    result = parse_spatialinfo_config(
        {
            "SpatialObj": {"attributes": {"field": "SpatialObj"}},
            "SelectedItems": {
                "Item": [
                    {"attributes": {"name": "AreaMi"}},
                    {"attributes": {"name": "CentroidXY"}},
                ]
            },
        }
    )

    assert result.normalized_config == {
        "spatial_field": "SpatialObj",
        "selected_items": ["AreaMi", "CentroidXY"],
    }


def test_generalize_parser_normalizes_sample_config():
    result = parse_generalize_config(
        {
            "SpatialObjectField": {"text": "SpatialObj"},
            "IncludeSourceInOutput": {"attributes": {"value": "False"}},
            "Threshold": {"text": "0.1"},
            "Units": {"text": "Miles"},
            "Layerwise": {"attributes": {"value": "True"}},
        }
    )

    assert result.normalized_config == {
        "spatial_field": "SpatialObj",
        "include_source": False,
        "threshold": "0.1",
        "units": "Miles",
        "layerwise": True,
        "output_field": "SpatialObj_Generalize",
    }


def test_smooth_parser_normalizes_sample_config():
    result = parse_smooth_config(
        {
            "SpatialObjectField": {"text": "SpatialObj_Generalize"},
            "IncludeSourceInOutput": {"attributes": {"value": "False"}},
            "Passes": {"text": "2"},
            "MaximumRadius": {"text": "1"},
            "Units": {"text": "Miles"},
            "PostGeneralize": {"attributes": {"value": "True"}},
            "PostGenerlizePercent": {"text": "1"},
            "Layerwise": {"attributes": {"value": "True"}},
        }
    )

    assert result.normalized_config == {
        "spatial_field": "SpatialObj_Generalize",
        "include_source": False,
        "passes": "2",
        "maximum_radius": "1",
        "units": "Miles",
        "post_generalize": True,
        "post_generalize_percent": "1",
        "layerwise": True,
        "output_field": "SpatialObj_Smooth",
    }


def test_spatialprocess_parser_normalizes_fields_and_action():
    result = parse_spatialprocess_config(
        {
            "SpatialObjFields": {"attributes": {"field1": "StoreSpObj", "field2": "AdArea"}},
            "Action": {"attributes": {"action": "Cut1_From2", "noEmpty": "False"}},
        }
    )

    assert result.normalized_config == {
        "field1": "StoreSpObj",
        "field2": "AdArea",
        "action": "Cut1_From2",
        "no_empty": False,
        "output_field": "SpatialObj_Process",
    }


def test_tradearea_parser_normalizes_radius_config():
    result = parse_tradearea_config(
        {
            "SpatialObj": {"attributes": {"field": "Store Point", "includeOut": "False"}},
            "Units": {"attributes": {"units": "Miles", "noOverlap": "True"}},
            "Radius_FromField": {"attributes": {"value": "False"}},
            "Radii": {"text": "2-5, 7-10"},
        }
    )

    assert result.normalized_config == {
        "spatial_field": "Store Point",
        "include_source": False,
        "units": "Miles",
        "no_overlap": True,
        "radius_from_field": False,
        "radii": "2-5, 7-10",
        "drive_time_dataset": "",
    }


def test_distance_parser_normalizes_spatial_fields_and_outputs():
    result = parse_distance_config(
        {
            "SpatialObjSource": {"text": "Customer Point"},
            "SpatialObjDest": {"text": "Store Point"},
            "OutputDistance": {"attributes": {"value": "True"}},
            "ReturnNearest": {"attributes": {"value": "False"}},
            "DistToInsideEdge": {"attributes": {"value": "True"}},
            "OutputDriveTimeAndDistance": {"attributes": {"value": "False"}},
            "DriveTimeDataSet": {"text": "Latest:TeleAtlas_US"},
            "AllowReverseRoute": {"attributes": {"value": "True"}},
            "OutputCardinalDirection": {"attributes": {"value": "True"}},
            "OutputDirectionDegrees": {"attributes": {"value": "False"}},
            "IsMetric": {"attributes": {"value": "False"}},
            "OutputUnits": {"text": "Miles"},
        }
    )

    assert result.normalized_config == {
        "source_spatial_field": "Customer Point",
        "destination_spatial_field": "Store Point",
        "output_distance": True,
        "return_nearest": False,
        "distance_to_inside_edge": True,
        "output_drive_time_and_distance": False,
        "drive_time_dataset": "Latest:TeleAtlas_US",
        "allow_reverse_route": True,
        "output_cardinal_direction": True,
        "output_direction_degrees": False,
        "is_metric": False,
        "output_units": "Miles",
    }


def test_spatialmatch_parser_normalizes_fields_method_and_selects():
    result = parse_spatialmatch_config(
        {
            "Target": {"attributes": {"SpatialObj": "SpatialObject_TradeArea"}},
            "Universe": {"attributes": {"SpatialObj": "SpatialObj"}},
            "Method": {"attributes": {"method": "Intersects"}},
            "IntersectPoly": {"attributes": {"value": "True"}},
            "SelectConfiguration": {
                "Configuration": {
                    "SelectFields": {
                        "SelectField": [
                            {"attributes": {"field": "Target_SpatialObject_TradeArea", "selected": "True", "rename": "StoreSpObj"}},
                            {"attributes": {"field": "Universe_SpatialObj", "selected": "True", "rename": "AdArea"}},
                            {"attributes": {"field": "*Unknown", "selected": "True"}},
                        ]
                    }
                }
            },
        }
    )

    assert result.normalized_config["target_spatial_field"] == "SpatialObject_TradeArea"
    assert result.normalized_config["universe_spatial_field"] == "SpatialObj"
    assert result.normalized_config["method"] == "Intersects"
    assert result.normalized_config["intersect_poly"] is True
    assert result.normalized_config["select_fields"][0]["rename"] == "StoreSpObj"


def test_findnearest_parser_normalizes_spatial_fields_limits_and_selects():
    result = parse_findnearest_config(
        {
            "Target": {"attributes": {"SpatialObj": "Store Point"}},
            "Universe": {
                "attributes": {"SpatialObj": "SpatialObj"},
                "File": {"text": "..\\..\\data\\SampleData\\CompetitorLoc.yxdb"},
            },
            "HowMany": {"attributes": {"value": "2"}},
            "MaxDistance": {"attributes": {"value": "20"}},
            "MaxDistanceUnits": {"text": "Miles"},
            "Ignore0": {"attributes": {"value": "True"}},
            "DriveTimeDataSet": {"text": "Latest:TeleAtlas_US"},
            "SelectConfiguration": {
                "Configuration": {
                    "SelectFields": {
                        "SelectField": [
                            {"attributes": {"field": "Universe_Name", "selected": "True", "rename": "StoreName"}},
                            {"attributes": {"field": "DistanceMiles", "selected": "True"}},
                        ]
                    }
                }
            },
        }
    )

    assert result.normalized_config["target_spatial_field"] == "Store Point"
    assert result.normalized_config["universe_spatial_field"] == "SpatialObj"
    assert result.normalized_config["how_many"] == 2
    assert result.normalized_config["max_distance"] == 20.0
    assert result.normalized_config["max_distance_units"] == "Miles"
    assert result.normalized_config["ignore_zero_distance"] is True
    assert result.normalized_config["drive_time_dataset"] == "Latest:TeleAtlas_US"
    assert result.normalized_config["universe_file"].endswith("CompetitorLoc.yxdb")
    assert result.normalized_config["select_fields"][0]["rename"] == "StoreName"


def test_polybuild_parser_normalizes_spatial_group_and_sequence_fields():
    result = parse_polybuild_config(
        {
            "SpatialObj": {"attributes": {"field": "Split_SpatialObj"}},
            "GroupField": {"attributes": {"field": "Store Num"}},
            "BuildType": {"text": "SequencePolygon"},
            "SequenceField": {"attributes": {"field": "Split_SequenceNum"}},
        }
    )

    assert result.normalized_config == {
        "spatial_field": "Split_SpatialObj",
        "group_field": "Store Num",
        "build_type": "SequencePolygon",
        "sequence_field": "Split_SequenceNum",
    }


def test_datacleansing_parser_normalizes_cleanse_macro_values():
    result = parse_datacleansing_config(
        {
            "Value": [
                {"attributes": {"name": "Check Box (135)"}, "text": "True"},
                {"attributes": {"name": "Check Box (136)"}, "text": "False"},
                {"attributes": {"name": "List Box (11)"}, "text": '"col1","rename_col2","col3"'},
                {"attributes": {"name": "Check Box (84)"}, "text": "True"},
                {"attributes": {"name": "Check Box (117)"}, "text": "False"},
                {"attributes": {"name": "Check Box (15)"}, "text": "True"},
                {"attributes": {"name": "Check Box (109)"}, "text": "False"},
                {"attributes": {"name": "Check Box (122)"}, "text": "False"},
                {"attributes": {"name": "Check Box (53)"}, "text": "False"},
                {"attributes": {"name": "Check Box (58)"}, "text": "False"},
                {"attributes": {"name": "Check Box (70)"}, "text": "False"},
                {"attributes": {"name": "Check Box (77)"}, "text": "True"},
                {"attributes": {"name": "Drop Down (81)"}, "text": "upper"},
            ]
        }
    )

    assert result.normalized_config == {
        "selected_fields": ["col1", "rename_col2", "col3"],
        "remove_null_rows": True,
        "remove_null_columns": False,
        "replace_string_nulls": True,
        "replace_numeric_nulls": False,
        "remove_leading_trailing_whitespace": True,
        "remove_tabs_line_breaks_duplicate_whitespace": False,
        "remove_all_whitespace": False,
        "remove_letters": False,
        "remove_numbers": False,
        "remove_punctuation": False,
        "modify_case": True,
        "case_mode": "upper",
    }


def test_datacleansepro_parser_normalizes_native_values():
    result = parse_datacleansepro_config(
        {
            "RemoveNullRows": {"attributes": {"value": "False"}},
            "RemoveNullColumns": {"attributes": {"value": "True"}},
            "RemoveTabsLineBreaksAndDuplicates": {"attributes": {"value": "True"}},
            "RemoveLeadingAndTrailingWhitespace": {"attributes": {"value": "True"}},
            "RemoveAllWhitespaces": {"attributes": {"value": "False"}},
            "Fields": {
                "Field": [
                    {"attributes": {"value": "Gender", "selected": "True"}},
                    {"attributes": {"value": "Score", "selected": "False"}},
                ]
            },
            "RemoveLetters": {"attributes": {"value": "False"}},
            "RemoveNumbers": {"attributes": {"value": "False"}},
            "RemovePunctuation": {"attributes": {"value": "True"}},
            "Checkbox_ReplaceStringColumns": {"attributes": {"value": "True"}},
            "Checkbox_ReplaceNumericColumns": {"attributes": {"value": "True"}},
            "ReplaceWithBlanks": {"attributes": {"value": "True"}},
            "ReplaceWithZero": {"attributes": {"value": "False"}},
            "CheckBox_ModifyCase": {"attributes": {"value": "True"}},
            "ModifyCase": {"attributes": {"value": "title"}},
        }
    )

    assert result.normalized_config == {
        "selected_fields": ["Gender"],
        "remove_null_rows": False,
        "remove_null_columns": True,
        "replace_string_nulls": True,
        "replace_numeric_nulls": False,
        "remove_leading_trailing_whitespace": True,
        "remove_tabs_line_breaks_duplicate_whitespace": True,
        "remove_all_whitespace": False,
        "remove_letters": False,
        "remove_numbers": False,
        "remove_punctuation": True,
        "modify_case": True,
        "case_mode": "title",
    }


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


def test_macroinput_parser_uses_embedded_textinput_config():
    result = parse_macroinput_config(
        {
            "TextInput": {
                "Configuration": {
                    "NumRows": {"attributes": {"value": "1"}},
                    "Fields": {"Field": [{"attributes": {"name": "Account ID"}}]},
                    "Data": {"r": [{"c": [{"text": "2081220001"}]}]},
                }
            }
        }
    )

    assert result.normalized_config == {
        "fields": ["Account ID"],
        "rows": [["2081220001"]],
        "num_rows": 1,
        "source": "embedded_textinput",
    }


def test_dynamicselect_parser_normalizes_modes():
    result = parse_dynamicselect_config(
        {
            "Mode": {"text": "FieldTypes"},
            "FieldTypes": {"text": "String,V_String"},
        }
    )

    assert result.normalized_config == {
        "mode": "FieldTypes",
        "field_types": ["String", "V_String"],
        "expression": "",
    }


def test_blobconvert_parser_normalizes_to_and_from_modes():
    from_result = parse_blobconvert_config(
        {
            "ToBlob": {"attributes": {"value": "False"}},
            "from_Field": {"text": "Blob"},
            "from_Mode": {"text": "Base64"},
        }
    )
    to_result = parse_blobconvert_config(
        {
            "ToBlob": {"attributes": {"value": "True"}},
            "to_Field": {"text": "Field1"},
            "to_Mode": {"text": "Text"},
            "to_textCodePage": {"text": "UTF16"},
        }
    )

    assert from_result.normalized_config == {
        "to_blob": False,
        "field": "Blob",
        "mode": "Base64",
        "text_code_page": "",
    }
    assert to_result.normalized_config == {
        "to_blob": True,
        "field": "Field1",
        "mode": "Text",
        "text_code_page": "UTF16",
    }


def test_download_parser_normalizes_sample_connector_config():
    result = parse_download_config(
        {
            "URLField": {"text": "URL"},
            "OutputMode": {"text": "String"},
            "CodePage": {"text": "65001"},
            "EncodeURLs": {"attributes": {"value": "True"}},
            "Headers": {
                "NameValues": {
                    "Item": {"attributes": {"name": "Content-Type", "value": "application/json"}}
                }
            },
            "Payload": {
                "HTTPAction": {"text": "POST"},
                "QueryStringBodyMode": {"text": "Field"},
                "Field": {"text": "JSON"},
            },
            "numConnections": {"text": "5"},
            "Timeout": {"text": "600"},
        }
    )

    assert result.normalized_config == {
        "url_field": "URL",
        "output_mode": "String",
        "code_page": "65001",
        "encode_urls": True,
        "headers": [{"name": "Content-Type", "value": "application/json"}],
        "payload": {"http_action": "POST", "body_mode": "Field", "field": "JSON"},
        "timeout": 600,
        "num_connections": 5,
    }


def test_download_parser_defaults_empty_timeout_and_connection_nodes():
    result = parse_download_config(
        {
            "URLField": {"text": "URL"},
            "Payload": {"HTTPAction": {"text": "GET"}},
            "Timeout": {},
            "numConnections": {},
        }
    )

    assert result.normalized_config["timeout"] == 30
    assert result.normalized_config["num_connections"] == 1


def test_error_parser_splits_annotation_expression_and_message():
    result = parse_error_config(
        {
            "annotation": {
                "Name": {"text": "Friendly message"},
                "DefaultAnnotationText": {"text": "[#1] AND IsEmpty([#2])\nSelect an input file"},
            }
        }
    )

    assert result.normalized_config == {
        "expression": "[#1] AND IsEmpty([#2])",
        "message": "Select an input file",
        "name": "Friendly message",
        "enforce": False,
    }


def test_error_parser_uses_annotation_name_when_body_has_only_expression():
    result = parse_error_config(
        {
            "annotation": {
                "Name": {"text": "You cannot get temps for today or in the future"},
                "DefaultAnnotationText": {"text": "[Date]>=DateTimeToday()"},
            }
        }
    )

    assert result.normalized_config["expression"] == "[Date]>=DateTimeToday()"
    assert result.normalized_config["message"] == "You cannot get temps for today or in the future"


def test_interface_value_parser_uses_annotation_as_default_question_value():
    result = parse_interface_value_config(
        {
            "annotation": {
                "Name": {"text": "Region choice"},
                "DefaultAnnotationText": {"text": "Select a region"},
            }
        }
    )

    assert result.normalized_config == {
        "name": "Region choice",
        "prompt": "Select a region",
        "default_value": "Select a region",
    }


def test_interface_layout_parser_preserves_annotation_text():
    result = parse_interface_layout_config(
        {
            "annotation": {
                "Name": {"text": "Page 1"},
                "DefaultAnnotationText": {"text": "Intro"},
            }
        }
    )

    assert result.normalized_config == {"name": "Page 1", "prompt": "Intro"}


def test_condition_parser_uses_annotation_expression():
    result = parse_condition_config(
        {
            "annotation": {
                "Name": {"text": "Use branch"},
                "DefaultAnnotationText": {"text": '![#1]'},
            }
        }
    )

    assert result.normalized_config == {"name": "Use branch", "expression": "![#1]"}


def test_action_parser_uses_annotation_metadata():
    result = parse_action_config(
        {
            "annotation": {
                "Name": {"text": "Update file path"},
                "DefaultAnnotationText": {"text": "Replace target input path"},
            }
        }
    )

    assert result.normalized_config == {
        "name": "Update file path",
        "description": "Replace target input path",
    }


def test_report_text_parser_normalizes_rich_text_metadata():
    result = parse_report_text_config(
        {
            "Output": {"text": "Title"},
            "HeaderMode": {"attributes": {"value": "False"}},
            "RawMode": {"attributes": {"value": "False"}},
            "RichTextMode": {"attributes": {"value": "True"}},
            "RichTextString": {"text": "{\\rtf1 Sales by Store}"},
        }
    )

    assert result.normalized_config["output_field"] == "Title"
    assert result.normalized_config["rich_text_mode"] is True
    assert result.normalized_config["rich_text"] == "{\\rtf1 Sales by Store}"


def test_report_table_parser_normalizes_selected_fields():
    result = parse_report_table_config(
        {
            "TableMode": {"text": "Basic"},
            "ShowHeader": {"attributes": {"value": "True"}},
            "TableFields": {
                "Field": [
                    {"attributes": {"name": "City", "selected": "True"}},
                    {"attributes": {"name": "Lon", "selected": "False"}},
                ]
            },
            "GroupingFields": {"Field": {"attributes": {"name": "Region"}}},
        }
    )

    assert result.normalized_config["table_mode"] == "Basic"
    assert result.normalized_config["show_header"] is True
    assert result.normalized_config["table_fields"] == ["City"]
    assert result.normalized_config["grouping_fields"] == ["Region"]


def test_report_image_parser_preserves_mode_without_embedded_bytes():
    result = parse_report_image_config(
        {
            "ImageMode": {"text": "Static"},
            "EncodedImage": {"text": "base64"},
            "ImageStyle": {"attributes": {"ImageWidth": "200"}},
        }
    )

    assert result.normalized_config["image_mode"] == "Static"
    assert result.normalized_config["has_encoded_image"] is True
    assert result.normalized_config["image_style"] == {"ImageWidth": "200"}


def test_report_layout_parser_normalizes_layout_fields():
    result = parse_report_layout_config(
        {
            "Orientation": {"text": "Vertical"},
            "LayoutFields": {"Field": {"attributes": {"name": "Report"}}},
            "Separator": {"text": "None"},
        }
    )

    assert result.normalized_config["orientation"] == "Vertical"
    assert result.normalized_config["layout_fields"] == ["Report"]
    assert result.normalized_config["separator"] == "None"


def test_report_render_parser_normalizes_output_options():
    result = parse_report_render_config(
        {
            "TempFileType": {"text": "pdf"},
            "OutputFile": {"text": "%Temp%/Output.pdf"},
            "BatchMode": {"attributes": {"value": "False"}},
            "ShowHeader": {"attributes": {"value": "True"}},
        }
    )

    assert result.normalized_config["temp_file_type"] == "pdf"
    assert result.normalized_config["output_file"] == "%Temp%/Output.pdf"
    assert result.normalized_config["batch_mode"] is False
    assert result.normalized_config["show_header"] is True


def test_report_map_parser_counts_layers():
    result = parse_report_map_config(
        {
            "ReferenceMap": {"text": "TomTom"},
            "Layers": {"Layer": [{"attributes": {"name": "A"}}, {"attributes": {"name": "B"}}]},
        }
    )

    assert result.normalized_config["reference_map"] == "TomTom"
    assert result.normalized_config["layer_count"] == 2


def test_report_header_parser_normalizes_values():
    result = parse_report_header_config(
        {
            "Value": [
                {"attributes": {"name": "HeaderText"}, "text": "Alteryx Report"},
                {"attributes": {"name": "IncludeDate"}, "text": "True"},
                {"attributes": {"name": "DateFormat"}, "text": "yyyy-MM-dd"},
                {"attributes": {"name": "IncludeImage"}, "text": "False"},
                {"attributes": {"name": "AlteryxLogo"}, "text": "True"},
                {"attributes": {"name": "OwnLogo"}, "text": "False"},
            ]
        }
    )

    assert result.normalized_config["header_text"] == "Alteryx Report"
    assert result.normalized_config["include_date"] is True
    assert result.normalized_config["include_image"] is False


def test_report_footer_parser_normalizes_values():
    result = parse_report_footer_config(
        {
            "Value": [
                {"attributes": {"name": "CopyrightText"}, "text": "Copyright"},
                {"attributes": {"name": "InfoText"}, "text": "Info"},
                {"attributes": {"name": "PageNumbers"}, "text": "False"},
            ]
        }
    )

    assert result.normalized_config == {
        "copyright_text": "Copyright",
        "info_text": "Info",
        "page_numbers": False,
    }


def test_report_legend_macro_parsers_normalize_values():
    splitter = parse_report_legend_splitter_config(
        {"Value": {"attributes": {"name": "Legend Field"}, "text": "Legend"}}
    )
    builder = parse_report_legend_builder_config(
        {
            "Value": [
                {"attributes": {"name": "Text Field"}, "text": "Text"},
                {"attributes": {"name": "Image Field"}, "text": "Image"},
                {"attributes": {"name": "Text Style Field"}, "text": "TextStyle"},
                {"attributes": {"name": "Image Style Field"}, "text": "ImageStyle"},
            ]
        }
    )

    assert splitter.normalized_config == {"legend_field": "Legend"}
    assert builder.normalized_config["image_style_field"] == "ImageStyle"


def test_plotly_charting_parser_normalizes_traces():
    result = parse_plotly_charting_config(
        {
            "ChartingFields": {
                "Traces": {
                    "type": {"text": "scatter"},
                    "mode": {"text": "markers"},
                    "name": {"text": "Sales"},
                    "xsrc": {"text": "City"},
                    "ysrc": {"text": "Total Sales"},
                }
            }
        }
    )

    assert result.normalized_config["trace_count"] == 1
    assert result.normalized_config["traces"] == [
        {"type": "scatter", "mode": "markers", "name": "Sales", "x": "City", "y": "Total Sales"}
    ]


def test_mapinput_parser_normalizes_embedded_rows():
    result = parse_mapinput_config(
        {
            "Mode": {"text": "Draw"},
            "ReferenceFile": {"text": "..\\data\\CustomerFile1.yxdb"},
            "Fields": {"Field": [{"attributes": {"name": "Label"}}, {"attributes": {"name": "SpatialObj"}}]},
            "Data": {
                "r": {
                    "c": [
                        {"text": "Office"},
                        {"text": '{"type":"point","coordinates":[-105.107510,39.915645]}'},
                    ]
                }
            },
        }
    )

    assert result.normalized_config["mode"] == "Draw"
    assert result.normalized_config["fields"] == ["Label", "SpatialObj"]
    assert result.normalized_config["rows"][0]["Label"] == "Office"


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


def test_xmlparse_parser_normalizes_core_flags():
    result = parse_xmlparse_config(
        {
            "XMLField": {"text": "customer_xml"},
            "XMLElement": {"text": "transaction"},
            "ChildValues": {"attributes": {"value": "True"}},
            "OuterXML": {"attributes": {"value": "False"}},
            "ParseRoot": {"attributes": {"value": "False"}},
            "IgnoreErrors": {"attributes": {"value": "True"}},
        }
    )

    assert result.normalized_config == {
        "xml_field": "customer_xml",
        "xml_element": "transaction",
        "child_values": True,
        "outer_xml": False,
        "parse_root": False,
        "ignore_errors": True,
    }


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
        "rows": [["49", "Edison"], ["456", None]],
        "num_rows": 2,
    }
    assert result.warnings == []


def test_xml_parser_preserves_textinput_cell_whitespace(tmp_path):
    workflow = tmp_path / "workflow.yxmd"
    workflow.write_text(
        """<?xml version="1.0"?>
<AlteryxDocument>
  <Nodes>
    <Node ToolID="1">
      <GuiSettings Plugin="AlteryxBasePluginsGui.TextInput.TextInput" />
      <Properties>
        <Configuration>
          <NumRows value="1" />
          <Fields><Field name="Line" /></Fields>
          <Data><r><c><![CDATA[  padded text  ]]></c></r></Data>
        </Configuration>
      </Properties>
    </Node>
  </Nodes>
  <Connections />
</AlteryxDocument>
""",
        encoding="utf-8",
    )

    graph = XmlWorkflowParser().parse(workflow)
    textinput = next(node for node in graph.nodes if node.node_id == "1")

    assert textinput.config["normalized"]["rows"] == [["  padded text  "]]


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
            "OutputOrder": {"Connection": [{"text": "#1"}, {"text": "#2"}]},
        }
    )

    assert result.normalized_config["mode"] == "ByName"
    assert result.normalized_config["by_name_error_mode"] == "Warning"
    assert result.normalized_config["output_order"] == ["#1", "#2"]


def test_sample_parser_normalizes_legacy_value_config():
    result = parse_sample_config(
        {
            "Value": [
                {"attributes": {"name": "Number"}, "text": "True"},
                {"attributes": {"name": "NNumber"}, "text": "1"},
                {"attributes": {"name": "Percent"}, "text": "False"},
                {"attributes": {"name": "NPercent"}, "text": "10"},
            ]
        }
    )

    assert result.normalized_config == {"mode": "First", "n": 1, "group_fields": []}


def test_summarize_parser_decodes_concat_separator_and_empty_bounds():
    result = parse_summarize_config(
        {
            "SummarizeFields": {
                "SummarizeField": {
                    "attributes": {"field": "Field1", "action": "Concat", "rename": "Concat_Field1"},
                    "Concat_Start": {},
                    "Separator": {"text": "\\r\\n"},
                    "Concat_End": {},
                }
            }
        }
    )

    field = result.normalized_config["summarize_fields"][0]
    assert field["concat_start"] == ""
    assert field["separator"] == "\r\n"
    assert field["concat_end"] == ""


def test_findreplace_parser_normalizes_replace_and_append_settings():
    result = parse_findreplace_config(
        {
            "FieldFind": {"text": "acct_holder"},
            "FieldSearch": {"text": "word"},
            "ReplaceFoundField": {"text": "replacement"},
            "FindMode": {"text": "FindAny"},
            "NoCase": {"attributes": {"value": "True"}},
            "MatchWholeWord": {"attributes": {"value": "False"}},
            "ReplaceMode": {"text": "Append"},
            "ReplaceMultipleFound": {"attributes": {"value": "True"}},
            "ReplaceAppendFields": {"Field": {"attributes": {"field": "gov_flag"}}},
        }
    )

    assert result.normalized_config["field_find"] == "acct_holder"
    assert result.normalized_config["no_case"] is True
    assert result.normalized_config["append_fields"] == ["gov_flag"]


def test_unique_parser_normalizes_unique_fields():
    result = parse_unique_config(
        {
            "UniqueFields": {
                "Field": [
                    {"attributes": {"field": "FirstName"}},
                    {"attributes": {"field": "LastName"}},
                ]
            }
        }
    )

    assert result.normalized_config == {"unique_fields": ["FirstName", "LastName"]}


def test_sample_parser_normalizes_mode_n_and_groups():
    result = parse_sample_config(
        {
            "Mode": {"text": "First"},
            "N": {"text": "2"},
            "GroupFields": {"Field": {"attributes": {"name": "City"}}},
        }
    )

    assert result.normalized_config == {"mode": "First", "n": 2, "group_fields": ["City"]}


def test_texttocolumns_parser_normalizes_split_settings():
    result = parse_texttocolumns_config(
        {
            "Field": {"text": "Address"},
            "ErrorHandling": {"text": "Last"},
            "RootName": {"text": "Address"},
            "Delimeters": {"attributes": {"value": ","}},
            "NumFields": {"attributes": {"value": "3"}},
            "Flags": {"attributes": {"value": "0"}},
        }
    )

    assert result.normalized_config["field"] == "Address"
    assert result.normalized_config["num_fields"] == 3


def test_multifieldformula_parser_normalizes_current_field_expression():
    result = parse_multifieldformula_config(
        {
            "FieldType": {"text": "Text"},
            "Fields": {
                "Field": [
                    {"attributes": {"name": "NAME"}},
                    {"attributes": {"name": "Total ", "selected": "False"}},
                ]
            },
            "NewFieldAddOn": {"text": "New_"},
            "NewFieldAddOnPos": {"text": "Prefix"},
            "CopyOutput": {"attributes": {"value": "True"}},
            "Expression": {"text": "Uppercase([_CurrentField_])"},
            "ChangeFieldType": {"attributes": {"value": "False"}},
        }
    )

    assert result.normalized_config["fields"] == ["NAME"]
    assert result.normalized_config["copy_output"] is True
    assert result.normalized_config["expression"] == "Uppercase([_CurrentField_])"


def test_multirowformula_parser_normalizes_window_and_groups():
    result = parse_multirowformula_config(
        {
            "UpdateField": {"attributes": {"value": "False"}},
            "UpdateField_Name": {"text": "Year"},
            "CreateField_Name": {"text": "RecordID"},
            "CreateField_Type": {"text": "Int32"},
            "CreateField_Size": {"text": "4"},
            "OtherRows": {"text": "Empty"},
            "NumRows": {"attributes": {"value": "1"}},
            "Expression": {"text": "[Row-1:RecordID]+1"},
            "GroupByFields": {"Field": {"attributes": {"field": "Product"}}},
        }
    )

    assert result.normalized_config == {
        "update_field": False,
        "update_field_name": "Year",
        "create_field_name": "RecordID",
        "create_field_type": "Int32",
        "create_field_size": "4",
        "other_rows": "Empty",
        "num_rows": 1,
        "expression": "[Row-1:RecordID]+1",
        "group_by_fields": ["Product"],
    }


def test_pearsoncorrelation_parser_normalizes_selected_fields_and_covariance():
    result = parse_pearsoncorrelation_config(
        {
            "Fields": {
                "Field": [
                    {"attributes": {"name": "Age"}},
                    {"attributes": {"name": "Salary", "selected": "False"}},
                    {"attributes": {"name": "*Unknown"}},
                ]
            },
            "Covariance": {"attributes": {"value": "True"}},
        }
    )

    assert result.normalized_config == {
        "fields": ["Age", "*Unknown"],
        "covariance": True,
    }


def test_createpoints_parser_normalizes_coordinate_fields_and_mode():
    result = parse_createpoints_config(
        {
            "Fields": {"attributes": {"fieldX": "Lon", "fieldY": "Lat"}},
            "Mode": {"text": "Double"},
        }
    )

    assert result.normalized_config == {
        "x_field": "Lon",
        "y_field": "Lat",
        "mode": "Double",
        "output_field": "Centroid",
    }


def test_appendfields_parser_normalizes_cartesian_mode():
    result = parse_appendfields_config({"CartesianMode": {"text": "Allow"}})

    assert result.normalized_config == {"cartesian_mode": "Allow"}


def test_autofield_parser_normalizes_selected_fields():
    result = parse_autofield_config(
        {
            "Fields": {
                "Field": [
                    {"attributes": {"field": "State", "selected": "True"}},
                    {"attributes": {"field": "City", "selected": "False"}},
                    {"attributes": {"field": "*Unknown", "selected": "True"}},
                ]
            }
        }
    )

    assert result.normalized_config == {"fields": ["State", "*Unknown"]}


def test_runningtotal_parser_normalizes_groups_and_total_fields():
    result = parse_runningtotal_config(
        {
            "GroupByFields": {"Field": {"attributes": {"field": "City"}}},
            "RunningTotalFields": {
                "Field": [
                    {"attributes": {"field": "Visits"}},
                    {"attributes": {"field": "Spend"}},
                ]
            },
        }
    )

    assert result.normalized_config == {
        "group_by_fields": ["City"],
        "running_total_fields": ["Visits", "Spend"],
    }


def test_summarize_parser_normalizes_actions():
    result = parse_summarize_config(
        {
            "SummarizeFields": {
                "SummarizeField": [
                    {"attributes": {"field": "City", "action": "GroupBy", "rename": "City"}},
                    {"attributes": {"field": "Spend", "action": "Sum", "rename": "Sum_Spend"}},
                ]
            }
        }
    )

    assert result.normalized_config["summarize_fields"][1]["action"] == "Sum"


def test_test_parser_normalizes_multiple_tests():
    result = parse_test_config(
        {
            "Tests": {
                "Test": [
                    {
                        "Name": {"text": "Expression Test"},
                        "Connection": {"text": "#1"},
                        "Type": {"text": "ExpAll"},
                        "Value": {"text": "[LOCNUM] > 1"},
                    },
                    {
                        "Name": {"text": "Record Count Test"},
                        "Connection": {"text": "#1"},
                        "Type": {"text": "RecCountValue"},
                        "Value": {"text": "236080"},
                    },
                ]
            },
            "DontReportSubsequent": {"attributes": {"value": "True"}},
        }
    )

    assert result.normalized_config == {
        "tests": [
            {"name": "Expression Test", "connection": "#1", "type": "ExpAll", "value": "[LOCNUM] > 1"},
            {"name": "Record Count Test", "connection": "#1", "type": "RecCountValue", "value": "236080"},
        ],
        "dont_report_subsequent": True,
    }


def test_fieldinfo_parser_has_empty_config():
    assert parse_fieldinfo_config({}).normalized_config == {}


def test_datetime_parser_normalizes_direction_and_fields():
    result = parse_datetime_config(
        {
            "IsFrom": {"attributes": {"value": "True"}},
            "InputFieldName": {"text": "Join Date"},
            "Language": {"text": "English"},
            "Format": {"text": "Month dd, yyyy"},
            "OutputFieldName": {"text": "Join Date_New"},
        }
    )

    assert result.normalized_config["is_from"] is True
    assert result.normalized_config["output_field_name"] == "Join Date_New"


def test_datetimenow_parser_normalizes_values():
    result = parse_datetimenow_config(
        {
            "Value": [
                {"attributes": {"name": "Language"}, "text": "English"},
                {"attributes": {"name": "OutputFormat"}, "text": "yyyy-MM-dd"},
            ]
        }
    )

    assert result.normalized_config == {"language": "English", "output_format": "yyyy-MM-dd"}


def test_directory_parser_normalizes_file_spec_and_subdirs():
    result = parse_directory_config(
        {
            "Directory": {"text": "../../../data/SampleData"},
            "FileSpec": {"text": "*.yxdb"},
            "IncludeSubDirs": {"attributes": {"value": "True"}},
        }
    )

    assert result.normalized_config == {
        "directory": "../../../data/SampleData",
        "file_spec": "*.yxdb",
        "include_subdirs": True,
    }


def test_generaterows_parser_normalizes_expressions():
    result = parse_generaterows_config(
        {
            "UpdateField": {"attributes": {"value": "False"}},
            "CreateField_Name": {"text": "RowCount"},
            "CreateField_Type": {"text": "Int32"},
            "CreateField_Size": {"text": "4"},
            "Expression_Init": {"text": "1"},
            "Expression_Cond": {"text": "RowCount <= 10"},
            "Expression_Loop": {"text": "RowCount + 1"},
        }
    )

    assert result.normalized_config["create_field_name"] == "RowCount"
    assert result.normalized_config["expression_cond"] == "RowCount <= 10"


def test_joinmultiple_parser_normalizes_connections_and_selects():
    result = parse_joinmultiple_config(
        {
            "JoinByRecPos": {"attributes": {"value": "False"}},
            "JoinFields": {
                "JoinInfo": [
                    {"attributes": {"connection": "#1"}, "Field": {"attributes": {"field": "Name"}}},
                    {"attributes": {"connection": "#2"}, "Field": {"attributes": {"field": "Name"}}},
                ]
            },
            "OutputJoinOnly": {"attributes": {"value": "True"}},
            "SelectConfiguration": {
                "Configuration": {
                    "SelectFields": {
                        "SelectField": {"attributes": {"field": "Input_#2_Name", "rename": "Right_Name"}}
                    }
                }
            },
        }
    )

    assert result.normalized_config["joins"] == [
        {"connection": "#1", "fields": ["Name"]},
        {"connection": "#2", "fields": ["Name"]},
    ]
    assert result.normalized_config["output_join_only"] is True
    assert result.normalized_config["select_fields"][0]["rename"] == "Right_Name"


def test_makecolumns_parser_normalizes_groups():
    result = parse_makecolumns_config(
        {
            "NumColumns": {"text": "3"},
            "IsHorizontal": {"attributes": {"value": "False"}},
            "GroupFields": {"Field": {"attributes": {"name": "Code"}}},
        }
    )

    assert result.normalized_config == {"num_columns": 3, "is_horizontal": False, "group_fields": ["Code"]}


def test_rank_parser_normalizes_modes_sort_and_groups():
    result = parse_rank_config(
        {
            "RankingModes": {"Mode": {"attributes": {"value": "Dense"}}},
            "SortInfo": {"Field": {"attributes": {"field": "Units Sold", "order": "Descending"}}},
            "GroupFields": {"Field": {"attributes": {"name": "Group"}}},
        }
    )

    assert result.normalized_config == {
        "ranking_modes": ["Dense"],
        "sort_fields": [{"field": "Units Sold", "order": "Descending"}],
        "group_fields": ["Group"],
    }


def test_tile_parser_normalizes_manual_cutoffs():
    result = parse_tile_config(
        {
            "Method": {"text": "Manual"},
            "GroupFields": {"Field": {"attributes": {"name": "ZIP"}}},
            "Manual": {"Field": {"text": "AVERAGE SALE"}, "Cutoffs": {"text": "10\n50\n100"}},
        }
    )

    assert result.normalized_config == {
        "method": "Manual",
        "group_fields": ["ZIP"],
        "field": "AVERAGE SALE",
        "cutoffs": [10.0, 50.0, 100.0],
    }


def test_regex_parser_normalizes_methods_and_fields():
    result = parse_regex_config(
        {
            "Field": {"text": "Name"},
            "RegExExpression": {"attributes": {"value": r"([a-z]+)\s([a-z]+)"}},
            "CaseInsensitve": {"attributes": {"value": "True"}},
            "Method": {"text": "ParseComplex"},
            "ParseComplex": {
                "Field": [
                    {"attributes": {"field": "First Name"}},
                    {"attributes": {"field": "Last Name"}},
                ]
            },
            "Match": {"Field": {"text": "Name_Matched"}},
        }
    )

    assert result.normalized_config["method"] == "ParseComplex"
    assert result.normalized_config["parse_complex_fields"] == ["First Name", "Last Name"]


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


def test_detour_parser_normalizes_selected_side():
    result = parse_detour_config({"DetourRight": {"attributes": {"value": "True"}}})

    assert result.normalized_config == {"detour_right": True}


def test_detourend_parser_has_empty_runtime_config():
    result = parse_detourend_config({})

    assert result.normalized_config == {}


def test_throttle_parser_normalizes_record_rate():
    result = parse_throttle_config({"RecordsPerMinute": {"text": "60"}})

    assert result.normalized_config == {"records_per_minute": "60"}


def test_runcommand_parser_normalizes_external_command_config():
    result = parse_runcommand_config(
        {
            "ProgramName": {"text": "%temp%\\RunCommand.bat"},
            "Arguments": {"text": "/q"},
            "WorkingDir": {"text": "%temp%"},
            "RunMinimized": {"attributes": {"value": "True"}},
            "RunSilent": {"attributes": {"value": "False"}},
            "InputConfiguration": {"Configuration": {"File": {"text": "input.yxdb"}}},
            "OutputConfiguration": {"Configuration": {"File": {"text": "output.csv"}}},
        }
    )

    assert result.normalized_config == {
        "program_name": "%temp%\\RunCommand.bat",
        "arguments": "/q",
        "working_dir": "%temp%",
        "run_minimized": True,
        "run_silent": False,
        "input_file": "input.yxdb",
        "output_file": "output.csv",
    }


def test_bloboutput_parser_normalizes_file_and_blob_fields():
    result = parse_bloboutput_config(
        {
            "FileName": {"text": "%TEMP%\\BlobOutput"},
            "ModifyMethod": {"text": "FileName"},
            "ModifyFilename_Field": {"text": "FileName"},
            "BlobField": {"text": "Blob"},
        }
    )

    assert result.normalized_config == {
        "file_name": "%TEMP%\\BlobOutput",
        "modify_method": "FileName",
        "modify_filename_field": "FileName",
        "blob_field": "Blob",
    }


def test_polysplit_parser_normalizes_spatial_field_and_split_type():
    result = parse_polysplit_config(
        {"SpatialObj": {"attributes": {"field": "SpatialObject"}}, "SplitTo": {"attributes": {"type": "Point"}}}
    )

    assert result.normalized_config == {"spatial_field": "SpatialObject", "split_to": "Point"}


def test_arrange_parser_normalizes_key_fields_columns_and_rows():
    result = parse_arrange_config(
        {
            "KeyFields": {"Field": {"attributes": {"name": "RecordID"}}},
            "OutputFields": {
                "Columns": {
                    "Column": [
                        {"attributes": {"name": "Description", "type": "text"}},
                        {"attributes": {"name": "X", "type": "combobox"}},
                    ]
                },
                "Data": {"r": [{"c": [{"text": "Start"}, {"text": "X1"}]}, {"c": [{}, {"text": "X2"}]}]},
            },
        }
    )

    assert result.normalized_config == {
        "key_fields": ["RecordID"],
        "output_columns": [
            {"name": "Description", "type": "text", "context": ""},
            {"name": "X", "type": "combobox", "context": ""},
        ],
        "output_rows": [["Start", "X1"], ["", "X2"]],
    }


def test_dynamicreplace_parser_normalizes_field_contract():
    result = parse_dynamicreplace_config(
        {
            "Field_FieldName": {"text": "New Field"},
            "Field_OutputValue": {"text": "Value"},
            "Field_Expression": {"text": "Expression"},
            "ValueIsExpression": {"attributes": {"value": "True"}},
            "Unmatched_Behavior": {"text": "Warn"},
            "FieldTypeMode": {"text": "Autofield"},
            "OutputFieldType": {"attributes": {"type": "Double", "size": "8"}},
        }
    )

    assert result.normalized_config["field_field_name"] == "New Field"
    assert result.normalized_config["value_is_expression"] is True
    assert result.normalized_config["output_field_type"] == {"type": "Double", "size": "8"}


def test_expectequal_parser_has_empty_runtime_config():
    assert parse_expectequal_config({}).normalized_config == {}


def test_basicdataprofile_parser_normalizes_limits():
    result = parse_basicdataprofile_config(
        {
            "Limit_UniqueCount": {"text": "10000"},
            "Limit_UniqueValuesSize": {"text": "1000"},
            "IsMetric": {"attributes": {"value": "True"}},
        }
    )

    assert result.normalized_config == {
        "limit_unique_count": "10000",
        "limit_unique_values_size": "1000",
        "is_metric": True,
    }


def test_legacy_reporting_parsers_normalize_key_fields():
    chart = parse_alteryx_report_chart_config(
        {"ChartType": {"text": "Column"}, "LabelField": {"text": "Hour"}, "GeneralStyles": {"attributes": {"ChartTitle": "Title"}}}
    )
    layout = parse_visual_layout_config(
        {
            "LayoutFields": {
                "Document": {"TempFileType": {"text": "pdf"}, "RenderType": {"text": "PDF"}},
                "NumIncomingConnections": {"text": "2"},
            }
        }
    )
    overlay = parse_overlay_config(
        {
            "Field_Base": {"text": "Map"},
            "Field_LR": {"text": "Legend"},
            "Padding": {"attributes": {"Left": "36"}},
            "PreserveSourceFields": {"attributes": {"value": "False"}},
        }
    )

    assert chart.normalized_config["chart_type"] == "Column"
    assert layout.normalized_config["render_type"] == "PDF"
    assert overlay.normalized_config["field_base"] == "Map"
    assert overlay.normalized_config["padding"] == {"Left": "36"}


def test_makegroup_parser_normalizes_keys():
    result = parse_makegroup_config({"Key1st": {"text": "key_A"}, "Key2nd": {"text": "key_B"}})

    assert result.normalized_config == {"key_first": "key_A", "key_second": "key_B"}


def test_makegrid_parser_normalizes_spatial_grid_options():
    result = parse_makegrid_config(
        {
            "SpatialObjIn": {"text": "SpatialObj"},
            "GridSize": {"attributes": {"value": "1"}},
            "Units": {"text": "Miles"},
            "GridPerObject": {"attributes": {"value": "True"}},
            "ClipToPoly": {"attributes": {"value": "False"}},
        }
    )

    assert result.normalized_config == {
        "spatial_field": "SpatialObj",
        "grid_size": "1",
        "units": "Miles",
        "grid_per_object": True,
        "clip_to_poly": False,
    }


def test_blobinput_parser_normalizes_file_options():
    result = parse_blobinput_config(
        {
            "FileName": {"text": "image.jpg"},
            "ModifyMethod": {"text": "Path"},
            "ModifyFilename_Field": {"text": "FullPath"},
            "ModifyFilename_StopOnError": {"attributes": {"value": "False"}},
            "SplitBlobs": {"attributes": {"value": "True"}},
            "BlobChunkSize": {"text": "10"},
        }
    )

    assert result.normalized_config == {
        "file_name": "image.jpg",
        "modify_method": "Path",
        "modify_filename_field": "FullPath",
        "stop_on_error": False,
        "split_blobs": True,
        "blob_chunk_size": "10",
    }


def test_apioutput_parser_has_empty_runtime_config():
    assert parse_apioutput_config({}).normalized_config == {}


def test_dynamicinput_parser_preserves_input_config_and_mode():
    result = parse_dynamicinput_config(
        {
            "InputConfiguration": {"Configuration": {"File": {"text": "data.csv"}}},
            "Mode": {"text": "ModifySQL"},
            "Modifications": {"Modify": {"attributes": {"Action": "Spatial"}}},
        }
    )

    assert result.normalized_config["input_configuration"]["File"]["text"] == "data.csv"
    assert result.normalized_config["mode"] == "ModifySQL"
    assert result.normalized_config["modifications"]["Modify"]["attributes"]["Action"] == "Spatial"


def test_fuzzymatch_parser_normalizes_thresholds_and_match_fields():
    result = parse_fuzzymatch_config(
        {
            "RecordIdField": {"text": "transaction_id"},
            "MatchThreshold": {"attributes": {"value": "80"}},
            "OutputScore": {"attributes": {"value": "True"}},
            "OutputKey": {"attributes": {"value": "True"}},
            "MatchFields": {
                "MatchField": {
                    "FieldName": {"text": "acct_holder"},
                    "Style": {
                        "attributes": {"Name": "Company Name"},
                        "Match": {
                            "MatchFunction": {"text": "JaroTFIDF"},
                            "MatchThreshold": {"attributes": {"value": "85"}},
                        },
                    },
                }
            },
        }
    )

    assert result.normalized_config["record_id_field"] == "transaction_id"
    assert result.normalized_config["match_threshold"] == 80.0
    assert result.normalized_config["output_score"] is True
    assert result.normalized_config["output_key"] is True
    assert result.normalized_config["match_fields"] == [
        {
            "field_name": "acct_holder",
            "style_name": "Company Name",
            "match_function": "JaroTFIDF",
            "match_threshold": 85.0,
        }
    ]


def test_jupytercode_parser_preserves_script_metadata():
    result = parse_jupytercode_config(
        {
            "vEnvName": {"text": "designerbasetools_venv"},
            "productionModeScript": {"text": "Alteryx.write(df, 1)"},
            "JupyterProduction": {"text": "True"},
        }
    )

    assert result.normalized_config["venv_name"] == "designerbasetools_venv"
    assert result.normalized_config["production_mode_script"] == "Alteryx.write(df, 1)"
    assert result.normalized_config["jupyter_production"] == "True"


def test_pdfinput_parser_normalizes_directory_config():
    result = parse_pdfinput_config(
        {
            "FieldSelect": {"text": "FileName"},
            "ModeSelect": {"text": "1"},
            "PDFDirectory": {"text": "C:/pdfs"},
        }
    )

    assert result.normalized_config == {
        "field": "FileName",
        "mode": "1",
        "pdf_directory": "C:/pdfs",
    }


def test_pdftotext_parser_normalizes_path_and_options():
    result = parse_pdftotext_config(
        {
            "TextExtractionLanguage": {"LanguageName": {"text": "EN"}},
            "TextExtractionMode": {"text": "text_only"},
            "PathInputValue": {"attributes": {"isWorkflowDependency": "True"}, "text": "file.pdf"},
            "PathInputMode": {"text": "fileBrowse"},
            "OutputOptions": {"OutputString": {"text": "true"}},
        }
    )

    assert result.normalized_config["language"] == "EN"
    assert result.normalized_config["extraction_mode"] == "text_only"
    assert result.normalized_config["path_input_value"] == "file.pdf"
    assert result.normalized_config["path_is_workflow_dependency"] == "True"
    assert result.normalized_config["output_options"]["OutputString"]["text"] == "true"

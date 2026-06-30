from alteryx2python.tools.mapinput import mapinput_tool


def test_mapinput_tool_emits_rows_and_converts_spatial_objects(workflow_context):
    result = mapinput_tool(
        {},
        {
            "fields": ["Label", "SpatialObj"],
            "rows": [
                {
                    "Label": "Office",
                    "SpatialObj": '{"type":"point","coordinates":[-105.107510,39.915645]}',
                }
            ],
        },
        workflow_context,
    )

    output = result["Output"]
    assert output.to_dict("records") == [
        {"Label": "Office", "SpatialObj": "POINT (-105.10751 39.915645)"}
    ]


def test_mapinput_tool_supports_empty_selection_rows(workflow_context):
    result = mapinput_tool({}, {"fields": ["Label", "SpatialObj"], "rows": []}, workflow_context)

    output = result["Output"]
    assert list(output.columns) == ["Label", "SpatialObj"]
    assert output.empty

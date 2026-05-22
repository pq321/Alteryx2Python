import pandas as pd

from alteryx2python.comparison.schema_diff import compare_schema_snapshots, snapshot_schema
from alteryx2python.tools.select import SelectTool, select_tool


def test_select_keeps_renames_and_reorders_fields(sample_frame, workflow_context):
    result = select_tool(
        inputs={"Input": sample_frame},
        config={
            "node_id": "2",
            "source_tool_id": "10",
            "select_fields": [
                {"source": "fee", "rename": "service_fee"},
                {"source": "account"},
                {"source": "amount", "rename": "gross_amount"},
            ],
        },
        context=workflow_context,
    )

    output = result["Output"]
    assert list(output.columns) == ["service_fee", "account", "gross_amount"]
    assert output["account"].tolist() == ["A1", "A2", "A3"]
    assert output["gross_amount"].tolist() == [100, 200, 300]
    assert output.index.tolist() == sample_frame.index.tolist()

    trace = workflow_context.traces[0].to_dict()
    assert trace["node_id"] == "2"
    assert trace["tool_type"] == "Select"
    assert trace["inputs"]["Input"]["row_count"] == 3
    assert trace["outputs"]["Output"]["columns"] == ["service_fee", "account", "gross_amount"]


def test_select_applies_type_conversions(null_heavy_frame, workflow_context):
    result = select_tool(
        inputs={"Input": null_heavy_frame},
        config={
            "node_id": "5",
            "select_fields": [
                {"source": "account", "dtype": "string"},
                {"source": "amount", "dtype": "float64"},
                {"source": "flag", "dtype": "bool"},
            ],
        },
        context=workflow_context,
    )

    output = result["Output"]
    assert str(output["account"].dtype) == "string"
    assert str(output["amount"].dtype) == "float64"
    assert str(output["flag"].dtype) == "boolean"
    assert pd.isna(output.loc[1, "amount"])
    assert pd.isna(output.loc[1, "flag"])


def test_select_preserves_empty_input(empty_frame, workflow_context):
    result = select_tool(
        inputs={"Input": empty_frame},
        config={
            "node_id": "9",
            "select_fields": [
                {"source": "amount", "rename": "amount_copy", "dtype": "int64"},
            ],
        },
        context=workflow_context,
    )

    output = result["Output"]
    assert output.empty
    assert list(output.columns) == ["amount_copy"]
    assert str(output["amount_copy"].dtype) == "Int64"


def test_snapshot_schema_reports_expected_values(sample_frame):
    schema = snapshot_schema(sample_frame)
    assert schema["columns"] == ["account", "amount", "fee", "flag"]
    assert schema["row_count"] == 3
    assert schema["dtypes"]["amount"] == "int64"


def test_execution_report_exposes_trace_and_config(sample_frame, workflow_context):
    select_tool(
        inputs={"Input": sample_frame},
        config={
            "node_id": "4",
            "source_tool_id": "44",
            "select_fields": [{"source": "account"}],
        },
        context=workflow_context,
    )

    report = workflow_context.execution_report()
    assert report["runtime_config"] == {"mode": "test"}
    assert report["warnings"] == []
    assert report["errors"] == []
    assert report["traces"][0]["source_tool_id"] == "44"


def test_context_records_warning_and_error(workflow_context):
    workflow_context.record_warning("warn")
    workflow_context.record_error("err")

    report = workflow_context.execution_report()
    assert report["warnings"] == ["warn"]
    assert report["errors"] == ["err"]


def test_select_tool_class_executes_same_contract(sample_frame, workflow_context):
    tool = SelectTool()
    result = tool.execute(
        inputs={"Input": sample_frame},
        config={"node_id": "class-select", "select_fields": [{"source": "account"}]},
        context=workflow_context,
    )

    assert list(result["Output"].columns) == ["account"]


def test_compare_schema_snapshots_reports_match_and_difference(sample_frame):
    left = snapshot_schema(sample_frame[["account", "amount"]])
    right = snapshot_schema(sample_frame[["account", "amount"]])
    different = snapshot_schema(sample_frame[["amount", "account"]])

    assert compare_schema_snapshots(left, right) == []
    assert compare_schema_snapshots(left, different) == ["Column order or names differ"]


def test_compare_schema_snapshots_reports_dtype_and_row_count_difference(sample_frame):
    left = snapshot_schema(sample_frame[["amount"]])
    right_frame = sample_frame[["amount"]].astype({"amount": "float64"}).iloc[:2]
    right = snapshot_schema(right_frame)

    assert compare_schema_snapshots(left, right) == [
        "Column dtypes differ",
        "Row counts differ",
    ]
import pandas as pd
import pytest

from alteryx2python.tools.dynamicinput import DynamicInputTool, dynamicinput_tool


def test_dynamicinput_rejects_modify_sql(workflow_context):
    with pytest.raises(NotImplementedError, match="ModifySQL"):
        dynamicinput_tool({"Input": pd.DataFrame({"Latitude": [1.0]})}, {"mode": "ModifySQL"}, workflow_context)


def test_dynamicinput_reads_unique_workbook_paths_in_path_order(workflow_context, tmp_path):
    for name, value in [("a.xlsx", 3), ("b.xlsx", 7)]:
        pd.DataFrame({"Value": [value]}).to_excel(tmp_path / name, sheet_name="Data", index=False)
    paths = pd.DataFrame({"Path": ["b.xlsx", "a.xlsx", "b.xlsx"]})
    config = {"mode": "ReadList", "read_list_type": "Path", "read_list_field": "Path",
              "input_configuration": {"file": "a.xlsx|||Data$"}, "base_dir": str(tmp_path)}
    result = DynamicInputTool().execute({"Input": paths}, config, workflow_context)
    assert result["Output"]["Value"].tolist() == [3, 7]

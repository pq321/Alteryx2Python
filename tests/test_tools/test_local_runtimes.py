import pandas as pd
import pytest
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.local_runtimes import IMPLEMENTATIONS, ANCHORS
from alteryx2python.tools.unavailable import ToolUnavailableError


def test_exports_and_r_prerequisite():
    assert set(IMPLEMENTATIONS) == {"R", "Runner", "JupyterFlow", "CustomSpark"}
    assert ANCHORS["R"] == (("Input",), ("Output",))
    with pytest.raises(ToolUnavailableError):
        IMPLEMENTATIONS["R"](
            {"Input": pd.DataFrame()}, {"rscript": "missing"}, WorkflowContext()
        )


def test_customspark_requires_code():
    with pytest.raises(ValueError):
        IMPLEMENTATIONS["CustomSpark"]({}, {}, WorkflowContext())


def test_runner_returns_actual_selected_node_outputs(tmp_path):
    from alteryx2python.parity.samples import generate_samples

    source = generate_samples(tmp_path / "samples")[0]
    result = IMPLEMENTATIONS["Runner"](
        {}, {"workflow": str(source), "target_node": "1"}, WorkflowContext()
    )
    assert len(result["Output"]) == 4
    assert "中文" in result["Output"].to_string()


def test_jupyterflow_fresh_output_and_data_bridge(tmp_path):
    nbformat = pytest.importorskip("nbformat")
    pytest.importorskip("nbclient")
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                "import pandas as pd\ndf = pd.read_csv(ALTERYX_INPUT)\ndf['x'] = df['x'] * 3\ndf.to_csv(ALTERYX_OUTPUT, index=False)"
            )
        ]
    )
    path = tmp_path / "local.ipynb"
    nbformat.write(notebook, path)
    result = IMPLEMENTATIONS["JupyterFlow"](
        {"Input": pd.DataFrame({"x": [2, 4]})},
        {"notebook": str(path), "timeout": 30},
        WorkflowContext(),
    )
    assert result["Output"]["x"].tolist() == [6, 12]

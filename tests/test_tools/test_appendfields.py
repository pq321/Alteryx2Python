import pandas as pd
import pytest

from alteryx2python.parser.tool_parsers.appendfields_parser import parse_appendfields_config
from alteryx2python.tools.appendfields import appendfields_tool


def test_appendfields_allows_cartesian_append(workflow_context):
    targets = pd.DataFrame({"id": [1, 2]})
    source = pd.DataFrame({"label": ["A", "B"]})

    output = appendfields_tool(
        {"Targets": targets, "Source": source},
        {"cartesian_mode": "Allow"},
        workflow_context,
    )["Output"]

    assert output.to_dict("records") == [
        {"id": 1, "label": "A"},
        {"id": 1, "label": "B"},
        {"id": 2, "label": "A"},
        {"id": 2, "label": "B"},
    ]


def test_appendfields_error_mode_rejects_many_to_many(workflow_context):
    with pytest.raises(ValueError, match="many-to-many"):
        appendfields_tool(
            {"Targets": pd.DataFrame({"id": [1, 2]}), "Source": pd.DataFrame({"label": ["A", "B"]})},
            {"cartesian_mode": "Error"},
            workflow_context,
        )


@pytest.mark.parametrize(("mode", "expected"), [
    ("unique", {"Report": "data", "Root": "source"}),
    ("explicit-prefix", {"Report": "data", "Source_Root": "source"}),
    ("collision", {"Report": "data", "Root": "target", "Source_Root": "source"}),
    ("target-omitted", {"Report": "data", "Root": "source"}),
    ("target-renamed", {"Report": "data", "Prior": "target", "Root": "source"}),
    ("source-first", {"Root": "source", "Report": "data", "Target_Root": "target"}),
])
def test_appendfields_distinguishes_references_from_output_names(workflow_context, mode, expected):
    target = {"Report": ["data"]}
    if mode not in {"unique", "explicit-prefix"}:
        target["Root"] = ["target"]
    source_selection = {"field": "Source_Root"}
    if mode == "explicit-prefix":
        source_selection["rename"] = "Source_Root"
    selections = [source_selection, {"field": "*Unknown", "selected": "True"}]
    if mode == "target-omitted":
        selections.insert(0, {"field": "Target_Root", "selected": "False"})
    if mode == "target-renamed":
        selections.insert(0, {"field": "Target_Root", "rename": "Prior"})
    selection = {
        "SelectConfiguration": {"Configuration": {
            "OrderChanged": {"attributes": {"value": str(mode == "source-first")}},
            "SelectFields": {"SelectField": [{"attributes": field} for field in selections]},
        }},
    }
    config = parse_appendfields_config(selection).normalized_config
    output = appendfields_tool(
        {"Targets": pd.DataFrame(target), "Source": pd.DataFrame({"Root": ["source"]})},
        config,
        workflow_context,
    )["Output"]
    assert list(output.columns) == list(expected)
    assert output.to_dict("records") == [expected]

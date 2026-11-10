from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


VALUE_TOOL_TYPES = {
    "CheckBoxGroup",
    "ControlParam",
    "Date",
    "DropDown",
    "FolderBrowse",
    "ListBox",
    "Map",
    "NumericUpDown",
    "QuestionFileBrowse",
    "QuestionTextBox",
    "RadioButtonGroup",
    "Tree",
}


def _question_frame(tool_type: str, config: dict[str, Any]) -> pd.DataFrame:
    prompt = str(config.get("prompt", "") or "")
    value = config.get("default_value", prompt)
    return pd.DataFrame(
        [
            {
                "tool_type": tool_type,
                "name": str(config.get("name", "") or ""),
                "prompt": prompt,
                "value": value,
            }
        ]
    )


def _record_interface_node(
    *,
    tool_type: str,
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    outputs = {"Question": _question_frame(tool_type, config)} if tool_type in VALUE_TOOL_TYPES else {}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type=tool_type,
        source_tool_id=config.get("source_tool_id"),
        inputs={key: value for key, value in inputs.items() if isinstance(value, pd.DataFrame)},
        outputs=outputs,
        status="success",
        config={
            "name": str(config.get("name", "") or ""),
            "prompt": str(config.get("prompt", "") or ""),
            "default_value": config.get("default_value", ""),
        },
    )
    return outputs


def dropdown_tool(inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="DropDown", inputs=inputs, config=config, context=context)


def checkboxgroup_tool(
    inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext
) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="CheckBoxGroup", inputs=inputs, config=config, context=context)


def controlparam_tool(
    inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext
) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="ControlParam", inputs=inputs, config=config, context=context)


def date_tool(inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="Date", inputs=inputs, config=config, context=context)


def folderbrowse_tool(
    inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext
) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="FolderBrowse", inputs=inputs, config=config, context=context)


def label_tool(inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="Label", inputs=inputs, config=config, context=context)


def labelgroup_tool(inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="LabelGroup", inputs=inputs, config=config, context=context)


def listbox_tool(inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="ListBox", inputs=inputs, config=config, context=context)


def link_tool(inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="Link", inputs=inputs, config=config, context=context)


def map_tool(inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="Map", inputs=inputs, config=config, context=context)


def numericupdown_tool(
    inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext
) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="NumericUpDown", inputs=inputs, config=config, context=context)


def questionfilebrowse_tool(
    inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext
) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="QuestionFileBrowse", inputs=inputs, config=config, context=context)


def questiontab_tool(inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="QuestionTab", inputs=inputs, config=config, context=context)


def questiontextbox_tool(
    inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext
) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="QuestionTextBox", inputs=inputs, config=config, context=context)


def radiobuttongroup_tool(
    inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext
) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="RadioButtonGroup", inputs=inputs, config=config, context=context)


def tree_tool(inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
    return _record_interface_node(tool_type="Tree", inputs=inputs, config=config, context=context)


class CheckBoxGroupTool(BaseTool):
    tool_type = "CheckBoxGroup"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return checkboxgroup_tool(inputs, config, context)


class ControlParamTool(BaseTool):
    tool_type = "ControlParam"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return controlparam_tool(inputs, config, context)


class DateTool(BaseTool):
    tool_type = "Date"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return date_tool(inputs, config, context)


class DropDownTool(BaseTool):
    tool_type = "DropDown"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return dropdown_tool(inputs, config, context)


class FolderBrowseTool(BaseTool):
    tool_type = "FolderBrowse"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return folderbrowse_tool(inputs, config, context)


class LabelTool(BaseTool):
    tool_type = "Label"
    input_anchors = ()
    output_anchors = ()

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return label_tool(inputs, config, context)


class LabelGroupTool(BaseTool):
    tool_type = "LabelGroup"
    input_anchors = ()
    output_anchors = ()

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return labelgroup_tool(inputs, config, context)


class ListBoxTool(BaseTool):
    tool_type = "ListBox"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return listbox_tool(inputs, config, context)


class LinkTool(BaseTool):
    tool_type = "Link"
    input_anchors = ()
    output_anchors = ()

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return link_tool(inputs, config, context)


class MapTool(BaseTool):
    tool_type = "Map"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return map_tool(inputs, config, context)


class NumericUpDownTool(BaseTool):
    tool_type = "NumericUpDown"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return numericupdown_tool(inputs, config, context)


class QuestionFileBrowseTool(BaseTool):
    tool_type = "QuestionFileBrowse"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return questionfilebrowse_tool(inputs, config, context)


class QuestionTabTool(BaseTool):
    tool_type = "QuestionTab"
    input_anchors = ()
    output_anchors = ()

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return questiontab_tool(inputs, config, context)


class QuestionTextBoxTool(BaseTool):
    tool_type = "QuestionTextBox"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return questiontextbox_tool(inputs, config, context)


class RadioButtonGroupTool(BaseTool):
    tool_type = "RadioButtonGroup"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return radiobuttongroup_tool(inputs, config, context)


class TreeTool(BaseTool):
    tool_type = "Tree"
    input_anchors = ()
    output_anchors = ("Question",)

    def execute(self, inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
        return tree_tool(inputs, config, context)

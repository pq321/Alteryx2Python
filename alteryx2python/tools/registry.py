from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

import pandas as pd

from alteryx2python.runtime.context import WorkflowContext


ToolFunction = Callable[[dict[str, pd.DataFrame], dict[str, Any], WorkflowContext], dict[str, pd.DataFrame]]


@dataclass(slots=True, frozen=True)
class ToolMetadata:
    tool_type: str
    function: ToolFunction
    tool_class: type[object]
    input_anchors: tuple[str, ...]
    output_anchors: tuple[str, ...]
    maturity: str
    semantics_doc: str
    supports_certification: bool
    execution_profile: str = "native-config-subset"


class ToolRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, ToolMetadata] = {}

    def register(self, metadata: ToolMetadata) -> None:
        if metadata.tool_type in self._registry:
            raise ValueError(f"Tool already registered: {metadata.tool_type}")
        self._registry[metadata.tool_type] = metadata

    def get(self, tool_type: str) -> ToolMetadata:
        return self._registry[tool_type]

    def list_tool_types(self) -> list[str]:
        return sorted(self._registry)

    def replace(self, metadata: ToolMetadata) -> None:
        if metadata.tool_type not in self._registry:
            raise KeyError(metadata.tool_type)
        self._registry[metadata.tool_type] = metadata


from alteryx2python.tools.action import ActionTool, action_tool
from alteryx2python.tools.apioutput import APIOutputTool, apioutput_tool
from alteryx2python.tools.arrange import ArrangeTool, arrange_tool
from alteryx2python.tools.basicdataprofile import BasicDataProfileTool, basicdataprofile_tool
from alteryx2python.tools.crosstab import CrossTabTool, crosstab_tool
from alteryx2python.tools.createpoints import CreatePointsTool, createpoints_tool
from alteryx2python.tools.appendfields import AppendFieldsTool, appendfields_tool
from alteryx2python.tools.autofield import AutoFieldTool, autofield_tool
from alteryx2python.tools.baseline import BaselineTool, baseline_tool
from alteryx2python.tools.blobconvert import BlobConvertTool, blobconvert_tool
from alteryx2python.tools.blobinput import BlobInputTool, blobinput_tool
from alteryx2python.tools.bloboutput import BlobOutputTool, bloboutput_tool
from alteryx2python.tools.blockuntildone import BlockUntilDoneTool, blockuntildone_tool
from alteryx2python.tools.buffer import BufferTool, buffer_tool
from alteryx2python.tools.canvas import (
    BrowseV2Tool,
    ControlContainerTool,
    HtmlBoxTool,
    MessageTool,
    TextBoxTool,
    ToolContainerTool,
    browsev2_tool,
    controlcontainer_tool,
    htmlbox_tool,
    message_tool,
    textbox_tool,
    toolcontainer_tool,
)
from alteryx2python.tools.condition import ConditionTool, condition_tool
from alteryx2python.tools.datacleansing import DataCleansingTool, datacleansing_tool
from alteryx2python.tools.datacleansepro import DataCleanseProTool, datacleansepro_tool
from alteryx2python.tools.datetime import DateTimeTool, datetime_tool
from alteryx2python.tools.datetimenow import DateTimeNowTool, datetimenow_tool
from alteryx2python.tools.dbfileinput import DbFileInputTool, dbfileinput_tool
from alteryx2python.tools.dbfileoutput import DbFileOutputTool, dbfileoutput_tool
from alteryx2python.tools.detour import DetourTool, detour_tool
from alteryx2python.tools.detourend import DetourEndTool, detourend_tool
from alteryx2python.tools.distance import DistanceTool, distance_tool
from alteryx2python.tools.directory import DirectoryTool, directory_tool
from alteryx2python.tools.download import DownloadTool, download_tool
from alteryx2python.tools.dynamicinput import DynamicInputTool, dynamicinput_tool
from alteryx2python.tools.dynamicreplace import DynamicReplaceTool, dynamicreplace_tool
from alteryx2python.tools.dynamicrename import DynamicRenameTool, dynamicrename_tool
from alteryx2python.tools.dynamicselect import DynamicSelectTool, dynamicselect_tool
from alteryx2python.tools.error import ErrorTool, error_tool
from alteryx2python.tools.expectequal import ExpectEqualTool, expectequal_tool
from alteryx2python.tools.filter import FilterTool, filter_tool
from alteryx2python.tools.fieldinfo import FieldInfoTool, fieldinfo_tool
from alteryx2python.tools.findnearest import FindNearestTool, findnearest_tool
from alteryx2python.tools.findreplace import FindReplaceTool, findreplace_tool
from alteryx2python.tools.formula import FormulaTool, formula_tool
from alteryx2python.tools.fuzzymatch import FuzzyMatchTool, fuzzymatch_tool
from alteryx2python.tools.generalize import GeneralizeTool, generalize_tool
from alteryx2python.tools.interface import (
    CheckBoxGroupTool,
    ControlParamTool,
    DateTool,
    DropDownTool,
    FolderBrowseTool,
    LabelGroupTool,
    LabelTool,
    LinkTool,
    ListBoxTool,
    MapTool,
    NumericUpDownTool,
    QuestionFileBrowseTool,
    QuestionTabTool,
    QuestionTextBoxTool,
    RadioButtonGroupTool,
    TreeTool,
    checkboxgroup_tool,
    controlparam_tool,
    date_tool,
    dropdown_tool,
    folderbrowse_tool,
    label_tool,
    labelgroup_tool,
    link_tool,
    listbox_tool,
    map_tool,
    numericupdown_tool,
    questionfilebrowse_tool,
    questiontab_tool,
    questiontextbox_tool,
    radiobuttongroup_tool,
    tree_tool,
)
from alteryx2python.tools.generaterows import GenerateRowsTool, generaterows_tool
from alteryx2python.tools.join import JoinTool, join_tool
from alteryx2python.tools.joinmultiple import JoinMultipleTool, joinmultiple_tool
from alteryx2python.tools.jsonparse import JSONParseTool, jsonparse_tool
from alteryx2python.tools.jupytercode import JupyterCodeTool, jupytercode_tool
from alteryx2python.tools.makecolumns import MakeColumnsTool, makecolumns_tool
from alteryx2python.tools.makegrid import MakeGridTool, makegrid_tool
from alteryx2python.tools.makegroup import MakeGroupTool, makegroup_tool
from alteryx2python.tools.macroinput import MacroInputTool, macroinput_tool
from alteryx2python.tools.mapinput import MapInputTool, mapinput_tool
from alteryx2python.tools.multifieldformula import MultiFieldFormulaTool, multifieldformula_tool
from alteryx2python.tools.multirowformula import MultiRowFormulaTool, multirowformula_tool
from alteryx2python.tools.pearsoncorrelation import PearsonCorrelationTool, pearsoncorrelation_tool
from alteryx2python.tools.pdfinput import PDFInputTool, pdfinput_tool
from alteryx2python.tools.pdftotext import PDFToTextTool, pdftotext_tool
from alteryx2python.tools.polybuild import PolyBuildTool, polybuild_tool
from alteryx2python.tools.polysplit import PolySplitTool, polysplit_tool
from alteryx2python.tools.recordid import RecordIDTool, recordid_tool
from alteryx2python.tools.rank import RankTool, rank_tool
from alteryx2python.tools.regex import RegExTool, regex_tool
from alteryx2python.tools.reporting import (
    AlteryxReportChartGuiTool,
    OverlayTool,
    PlotlyChartingTool,
    PortfolioComposerImageTool,
    PortfolioComposerLayoutTool,
    PortfolioComposerRenderTool,
    PortfolioComposerTableTool,
    PortfolioComposerTextTool,
    ReportFooterTool,
    ReportHeaderTool,
    ReportLegendBuilderTool,
    ReportLegendSplitterTool,
    ReportMapTool,
    VisualLayoutTool,
    alteryxreportchartgui_tool,
    overlay_tool,
    plotlycharting_tool,
    portfoliocomposerimage_tool,
    portfoliocomposerlayout_tool,
    portfoliocomposerrender_tool,
    portfoliocomposertable_tool,
    portfoliocomposertext_tool,
    reportfooter_tool,
    reportheader_tool,
    reportlegendbuilder_tool,
    reportlegendsplitter_tool,
    reportmap_tool,
    visuallayout_tool,
)
from alteryx2python.tools.runningtotal import RunningTotalTool, runningtotal_tool
from alteryx2python.tools.runcommand import RunCommandTool, runcommand_tool
from alteryx2python.tools.sample import SampleTool, sample_tool
from alteryx2python.tools.select import SelectTool, select_tool
from alteryx2python.tools.spatialinfo import SpatialInfoTool, spatialinfo_tool
from alteryx2python.tools.spatialmatch import SpatialMatchTool, spatialmatch_tool
from alteryx2python.tools.smooth import SmoothTool, smooth_tool
from alteryx2python.tools.spatialprocess import SpatialProcessTool, spatialprocess_tool
from alteryx2python.tools.sort import SortTool, sort_tool
from alteryx2python.tools.summarize import SummarizeTool, summarize_tool
from alteryx2python.tools.test import TestTool, test_tool
from alteryx2python.tools.textinput import TextInputTool, textinput_tool
from alteryx2python.tools.texttocolumns import TextToColumnsTool, texttocolumns_tool
from alteryx2python.tools.throttle import ThrottleTool, throttle_tool
from alteryx2python.tools.tile import TileTool, tile_tool
from alteryx2python.tools.tradearea import TradeAreaTool, tradearea_tool
from alteryx2python.tools.transpose import TransposeTool, transpose_tool
from alteryx2python.tools.union import UnionTool, union_tool
from alteryx2python.tools.unique import UniqueTool, unique_tool
from alteryx2python.tools.xmlparse import XMLParseTool, xmlparse_tool


TOOL_REGISTRY = ToolRegistry()


def _register_interface_tool(
    tool_type: str,
    function: ToolFunction,
    tool_class: type[object],
    output_anchors: tuple[str, ...],
) -> None:
    TOOL_REGISTRY.register(
        ToolMetadata(
            tool_type=tool_type,
            function=function,
            tool_class=tool_class,
            input_anchors=(),
            output_anchors=output_anchors,
            maturity="L2_BASIC_IMPLEMENTATION",
            semantics_doc="docs/tools/interface.md",
            supports_certification=False,
        )
    )


def _register_reporting_tool(
    tool_type: str,
    function: ToolFunction,
    tool_class: type[object],
    output_anchors: tuple[str, ...] = ("Output",),
) -> None:
    TOOL_REGISTRY.register(
        ToolMetadata(
            tool_type=tool_type,
            function=function,
            tool_class=tool_class,
            input_anchors=("Input",),
            output_anchors=output_anchors,
            maturity="L2_BASIC_IMPLEMENTATION",
            semantics_doc="docs/tools/reporting.md",
            supports_certification=False,
        )
    )


def _baseline_function(tool_type: str) -> ToolFunction:
    return lambda inputs, config, context: baseline_tool(tool_type, inputs, config, context)


def _register_baseline_tool(tool_type: str) -> None:
    TOOL_REGISTRY.register(
        ToolMetadata(
            tool_type=tool_type,
            function=_baseline_function(tool_type),
            tool_class=BaselineTool,
            input_anchors=(),
            output_anchors=(),
            maturity="L2_BASIC_IMPLEMENTATION",
            semantics_doc="docs/tools/baseline.md",
            supports_certification=False,
        )
    )


TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Action",
        function=action_tool,
        tool_class=ActionTool,
        input_anchors=("Question", "Condition"),
        output_anchors=("Action",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/action.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="BlockUntilDone",
        function=blockuntildone_tool,
        tool_class=BlockUntilDoneTool,
        input_anchors=("Input",),
        output_anchors=("Output", "Output2", "Output3"),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/blockuntildone.md",
        supports_certification=False,
    )
)
_register_reporting_tool("PlotlyCharting", plotlycharting_tool, PlotlyChartingTool)
_register_reporting_tool("PortfolioComposerImage", portfoliocomposerimage_tool, PortfolioComposerImageTool)
_register_reporting_tool("PortfolioComposerLayout", portfoliocomposerlayout_tool, PortfolioComposerLayoutTool)
_register_reporting_tool("PortfolioComposerRender", portfoliocomposerrender_tool, PortfolioComposerRenderTool, ())
_register_reporting_tool("PortfolioComposerTable", portfoliocomposertable_tool, PortfolioComposerTableTool)
_register_reporting_tool("PortfolioComposerText", portfoliocomposertext_tool, PortfolioComposerTextTool)
_register_reporting_tool("ReportFooter", reportfooter_tool, ReportFooterTool)
_register_reporting_tool("ReportHeader", reportheader_tool, ReportHeaderTool, ("Output13",))
_register_reporting_tool("ReportLegendBuilder", reportlegendbuilder_tool, ReportLegendBuilderTool)
_register_reporting_tool("ReportLegendSplitter", reportlegendsplitter_tool, ReportLegendSplitterTool)
_register_reporting_tool("ReportMap", reportmap_tool, ReportMapTool)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="BrowseV2",
        function=browsev2_tool,
        tool_class=BrowseV2Tool,
        input_anchors=("Input",),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/canvas.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="ControlContainer",
        function=controlcontainer_tool,
        tool_class=ControlContainerTool,
        input_anchors=(),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/canvas.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Condition",
        function=condition_tool,
        tool_class=ConditionTool,
        input_anchors=("Question",),
        output_anchors=("True Condition", "False Condition"),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/condition.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="AppendFields",
        function=appendfields_tool,
        tool_class=AppendFieldsTool,
        input_anchors=("Targets", "Source"),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/appendfields.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="AutoField",
        function=autofield_tool,
        tool_class=AutoFieldTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/autofield.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="BlobConvert",
        function=blobconvert_tool,
        tool_class=BlobConvertTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/blobconvert.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Buffer",
        function=buffer_tool,
        tool_class=BufferTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/buffer.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="CreatePoints",
        function=createpoints_tool,
        tool_class=CreatePointsTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/createpoints.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="MapInput",
        function=mapinput_tool,
        tool_class=MapInputTool,
        input_anchors=(),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/mapinput.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DataCleansing",
        function=datacleansing_tool,
        tool_class=DataCleansingTool,
        input_anchors=("Input2",),
        output_anchors=("Output26",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/datacleansing.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DataCleansePro",
        function=datacleansepro_tool,
        tool_class=DataCleanseProTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/datacleansepro.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DateTime",
        function=datetime_tool,
        tool_class=DateTimeTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/datetime.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DateTimeNow",
        function=datetimenow_tool,
        tool_class=DateTimeNowTool,
        input_anchors=(),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/datetimenow.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="CrossTab",
        function=crosstab_tool,
        tool_class=CrossTabTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/crosstab.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DbFileInput",
        function=dbfileinput_tool,
        tool_class=DbFileInputTool,
        input_anchors=(),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/dbfileinput.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DbFileOutput",
        function=dbfileoutput_tool,
        tool_class=DbFileOutputTool,
        input_anchors=("Input",),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/dbfileoutput.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Distance",
        function=distance_tool,
        tool_class=DistanceTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/distance.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Generalize",
        function=generalize_tool,
        tool_class=GeneralizeTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/generalize.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Directory",
        function=directory_tool,
        tool_class=DirectoryTool,
        input_anchors=(),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/directory.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Download",
        function=download_tool,
        tool_class=DownloadTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/download.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DynamicInput",
        function=dynamicinput_tool,
        tool_class=DynamicInputTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/dynamicinput.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DynamicRename",
        function=dynamicrename_tool,
        tool_class=DynamicRenameTool,
        input_anchors=("Targets",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/dynamicrename.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DynamicSelect",
        function=dynamicselect_tool,
        tool_class=DynamicSelectTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/dynamicselect.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Filter",
        function=filter_tool,
        tool_class=FilterTool,
        input_anchors=("Input",),
        output_anchors=("True", "False"),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/filter.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="HtmlBox",
        function=htmlbox_tool,
        tool_class=HtmlBoxTool,
        input_anchors=(),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/canvas.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Join",
        function=join_tool,
        tool_class=JoinTool,
        input_anchors=("Left", "Right"),
        output_anchors=("Join", "Left", "Right"),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/join.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Formula",
        function=formula_tool,
        tool_class=FormulaTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/formula.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="FuzzyMatch",
        function=fuzzymatch_tool,
        tool_class=FuzzyMatchTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/fuzzymatch.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Message",
        function=message_tool,
        tool_class=MessageTool,
        input_anchors=("Input",),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/canvas.md",
        supports_certification=False,
    )
)
_register_interface_tool("CheckBoxGroup", checkboxgroup_tool, CheckBoxGroupTool, ("Question",))
_register_interface_tool("ControlParam", controlparam_tool, ControlParamTool, ("Question",))
_register_interface_tool("Date", date_tool, DateTool, ("Question",))
_register_interface_tool("DropDown", dropdown_tool, DropDownTool, ("Question",))
_register_interface_tool("FolderBrowse", folderbrowse_tool, FolderBrowseTool, ("Question",))
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="GenerateRows",
        function=generaterows_tool,
        tool_class=GenerateRowsTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/generaterows.md",
        supports_certification=False,
    )
)
_register_interface_tool("Label", label_tool, LabelTool, ())
_register_interface_tool("LabelGroup", labelgroup_tool, LabelGroupTool, ())
_register_interface_tool("Link", link_tool, LinkTool, ())
_register_interface_tool("ListBox", listbox_tool, ListBoxTool, ("Question",))
_register_interface_tool("Map", map_tool, MapTool, ("Question",))
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="JSONParse",
        function=jsonparse_tool,
        tool_class=JSONParseTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/jsonparse.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="JupyterCode",
        function=jupytercode_tool,
        tool_class=JupyterCodeTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/jupytercode.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="JoinMultiple",
        function=joinmultiple_tool,
        tool_class=JoinMultipleTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/joinmultiple.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="MakeColumns",
        function=makecolumns_tool,
        tool_class=MakeColumnsTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/makecolumns.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="TextBox",
        function=textbox_tool,
        tool_class=TextBoxTool,
        input_anchors=(),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/canvas.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="TextInput",
        function=textinput_tool,
        tool_class=TextInputTool,
        input_anchors=(),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/textinput.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="MacroInput",
        function=macroinput_tool,
        tool_class=MacroInputTool,
        input_anchors=(),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/textinput.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Sort",
        function=sort_tool,
        tool_class=SortTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/sort.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Transpose",
        function=transpose_tool,
        tool_class=TransposeTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/transpose.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="ToolContainer",
        function=toolcontainer_tool,
        tool_class=ToolContainerTool,
        input_anchors=(),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/canvas.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Union",
        function=union_tool,
        tool_class=UnionTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/union.md",
        supports_certification=False,
    )
)
_register_interface_tool("NumericUpDown", numericupdown_tool, NumericUpDownTool, ("Question",))
_register_interface_tool("QuestionFileBrowse", questionfilebrowse_tool, QuestionFileBrowseTool, ("Question",))
_register_interface_tool("QuestionTab", questiontab_tool, QuestionTabTool, ())
_register_interface_tool("QuestionTextBox", questiontextbox_tool, QuestionTextBoxTool, ("Question",))
_register_interface_tool("RadioButtonGroup", radiobuttongroup_tool, RadioButtonGroupTool, ("Question",))
_register_interface_tool("Tree", tree_tool, TreeTool, ("Question",))
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="RecordID",
        function=recordid_tool,
        tool_class=RecordIDTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/recordid.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Rank",
        function=rank_tool,
        tool_class=RankTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/rank.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="RegEx",
        function=regex_tool,
        tool_class=RegExTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/regex.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Select",
        function=select_tool,
        tool_class=SelectTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/select.md",
        supports_certification=True,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="SpatialInfo",
        function=spatialinfo_tool,
        tool_class=SpatialInfoTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/spatialinfo.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="SpatialMatch",
        function=spatialmatch_tool,
        tool_class=SpatialMatchTool,
        input_anchors=("Targets", "Universe"),
        output_anchors=("Matched",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/spatialmatch.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Smooth",
        function=smooth_tool,
        tool_class=SmoothTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/smooth.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="SpatialProcess",
        function=spatialprocess_tool,
        tool_class=SpatialProcessTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/spatialprocess.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="FindReplace",
        function=findreplace_tool,
        tool_class=FindReplaceTool,
        input_anchors=("Targets", "Source"),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/findreplace.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="FindNearest",
        function=findnearest_tool,
        tool_class=FindNearestTool,
        input_anchors=("Targets", "Universe"),
        output_anchors=("Matched",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/findnearest.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="MultiFieldFormula",
        function=multifieldformula_tool,
        tool_class=MultiFieldFormulaTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/multifieldformula.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="MultiRowFormula",
        function=multirowformula_tool,
        tool_class=MultiRowFormulaTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/multirowformula.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="PearsonCorrelation",
        function=pearsoncorrelation_tool,
        tool_class=PearsonCorrelationTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/pearsoncorrelation.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="PDFInput",
        function=pdfinput_tool,
        tool_class=PDFInputTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/pdfinput.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="PDFToText",
        function=pdftotext_tool,
        tool_class=PDFToTextTool,
        input_anchors=("Data Input", "Template Input"),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/pdftotext.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="PolyBuild",
        function=polybuild_tool,
        tool_class=PolyBuildTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/polybuild.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Sample",
        function=sample_tool,
        tool_class=SampleTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/sample.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="TextToColumns",
        function=texttocolumns_tool,
        tool_class=TextToColumnsTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/texttocolumns.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Tile",
        function=tile_tool,
        tool_class=TileTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/tile.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Unique",
        function=unique_tool,
        tool_class=UniqueTool,
        input_anchors=("Input",),
        output_anchors=("Unique", "Duplicates"),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/unique.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="TradeArea",
        function=tradearea_tool,
        tool_class=TradeAreaTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/tradearea.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="XMLParse",
        function=xmlparse_tool,
        tool_class=XMLParseTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/xmlparse.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Error",
        function=error_tool,
        tool_class=ErrorTool,
        input_anchors=(),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/error.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="FieldInfo",
        function=fieldinfo_tool,
        tool_class=FieldInfoTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/fieldinfo.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="RunningTotal",
        function=runningtotal_tool,
        tool_class=RunningTotalTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/runningtotal.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Summarize",
        function=summarize_tool,
        tool_class=SummarizeTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/summarize.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Test",
        function=test_tool,
        tool_class=TestTool,
        input_anchors=("Input",),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/test.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="BlobOutput",
        function=bloboutput_tool,
        tool_class=BlobOutputTool,
        input_anchors=("Input",),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/bloboutput.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Detour",
        function=detour_tool,
        tool_class=DetourTool,
        input_anchors=("Input", "Action"),
        output_anchors=("Left", "Right"),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/detour.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DetourEnd",
        function=detourend_tool,
        tool_class=DetourEndTool,
        input_anchors=("Left", "Right"),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/detourend.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="PolySplit",
        function=polysplit_tool,
        tool_class=PolySplitTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/polysplit.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="RunCommand",
        function=runcommand_tool,
        tool_class=RunCommandTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/runcommand.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Throttle",
        function=throttle_tool,
        tool_class=ThrottleTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/throttle.md",
        supports_certification=False,
    )
)
_register_reporting_tool("AlteryxReportChartGui", alteryxreportchartgui_tool, AlteryxReportChartGuiTool)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="APIOutput",
        function=apioutput_tool,
        tool_class=APIOutputTool,
        input_anchors=("Input",),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/apioutput.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="Arrange",
        function=arrange_tool,
        tool_class=ArrangeTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/arrange.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="BasicDataProfile",
        function=basicdataprofile_tool,
        tool_class=BasicDataProfileTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/basicdataprofile.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="BlobInput",
        function=blobinput_tool,
        tool_class=BlobInputTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/blobinput.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="DynamicReplace",
        function=dynamicreplace_tool,
        tool_class=DynamicReplaceTool,
        input_anchors=("Input", "Expressions"),
        output_anchors=("Output", "Counts"),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/dynamicreplace.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="MakeGrid",
        function=makegrid_tool,
        tool_class=MakeGridTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/makegrid.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="MakeGroup",
        function=makegroup_tool,
        tool_class=MakeGroupTool,
        input_anchors=("Input",),
        output_anchors=("Output",),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/makegroup.md",
        supports_certification=False,
    )
)
TOOL_REGISTRY.register(
    ToolMetadata(
        tool_type="ExpectEqual",
        function=expectequal_tool,
        tool_class=ExpectEqualTool,
        input_anchors=("Actual", "Expected"),
        output_anchors=(),
        maturity="L2_BASIC_IMPLEMENTATION",
        semantics_doc="docs/tools/expectequal.md",
        supports_certification=False,
    )
)
_register_reporting_tool("Overlay", overlay_tool, OverlayTool)
_register_reporting_tool("VisualLayout", visuallayout_tool, VisualLayoutTool)

from alteryx2python.parser.tool_catalog import CATALOG as _TOOL_CATALOG

for _catalog_entry in _TOOL_CATALOG:
    if _catalog_entry.tool_type in TOOL_REGISTRY._registry:
        continue
    if _catalog_entry.tool_type in ("UNKNOWN",):
        continue
    TOOL_REGISTRY.register(
        ToolMetadata(
            tool_type=_catalog_entry.tool_type,
            function=_baseline_function(_catalog_entry.tool_type),
            tool_class=BaselineTool,
            input_anchors=(),
            output_anchors=(),
            maturity="L1_PARSED_ONLY",
            semantics_doc="docs/tools/baseline.md",
            supports_certification=False,
        )
    )

for _baseline_tool_type in (
    "AutoML",
    "Barcode",
    "BuildFeatures",
    "CalgaryCrossCount",
    "CalgaryCrossCountAppend",
    "CalgaryInput",
    "CalgaryJoin",
    "CalgaryLoader",
    "Classification",
    "FeatureTypes",
    "Fit",
    "ImageProcessing",
    "ImageProfile",
    "ImageRecognition",
    "ImageTemplate",
    "ImageToText",
    "Insights",
    "KeyValuePairExtraction",
    "Modeling",
    "NamedEntityRecognition",
    "PartOfSpeechTagger",
    "Predict",
    "Regression",
    "Sentiment",
    "TextPreProcessing",
    "TextSummary",
    "TopicModel",
    "Transformation",
    "UNKNOWN",
    "WordCloud",
    "ZeroShotTextClassification",
):
    if _baseline_tool_type not in TOOL_REGISTRY._registry:
        _register_baseline_tool(_baseline_tool_type)


# Register executable local adapters before replacing remaining placeholders.
# Registration and behavioral/native validation remain separate evidence axes.
from importlib import import_module as _import_tool_module
from alteryx2python.tools.base_tool import BaseTool as _MappedBaseTool
from alteryx2python.tools.unavailable import unavailable_tool as _unavailable_tool


class _MappedTool(_MappedBaseTool):
    def execute(self, inputs, config, context):
        return self.function(inputs, config, context)


def _canonical_local_call(tool_type, function):
    """Delegated implementation calls expose exactly one outer node trace."""
    @wraps(function)
    def execute(inputs, config, context):
        child = WorkflowContext(runtime_config=context.runtime_config)
        try:
            outputs = function(inputs, config, child)
        finally:
            context.warnings.extend(child.warnings)
            context.errors.extend(child.errors)
            context.diagnostics.extend(child.diagnostics)
        details = child.traces[-1].config if child.traces else config
        context.record_node(node_id=str(config.get("node_id", "unknown")), source_tool_id=config.get("source_tool_id"),
                            tool_type=tool_type, inputs=inputs, outputs=outputs, status="success", config=details)
        return outputs
    return execute


for _module_name in ("local_macros", "indb", "predictive", "timeseries", "local_media", "statistics_extra", "ml_extra", "macro_engine", "text_models", "local_runtimes", "survival", "local_vision"):
    _module = _import_tool_module(f"alteryx2python.tools.{_module_name}")
    for _tool_type, _implementation in _module.IMPLEMENTATIONS.items():
        if isinstance(_implementation, type):
            _function = _implementation().execute
        else:
            _function = _implementation
        _function = _canonical_local_call(_tool_type, _function)
        _inputs, _outputs = _module.ANCHORS.get(_tool_type, (("Input",), ("Output",)))
        _inputs = (_inputs,) if isinstance(_inputs, str) else tuple(_inputs)
        _outputs = (_outputs,) if isinstance(_outputs, str) else tuple(_outputs)
        _class = type(f"{_tool_type}Tool", (_MappedTool,), {
            "tool_type": _tool_type, "function": staticmethod(_function),
            "input_anchors": _inputs, "output_anchors": _outputs,
        })
        _metadata = ToolMetadata(
            tool_type=_tool_type, function=_function, tool_class=_class,
            input_anchors=_inputs, output_anchors=_outputs, maturity="L2_BASIC_IMPLEMENTATION",
            semantics_doc=f"docs/tools/{_module_name}.md", supports_certification=False,
            execution_profile=f"local-{_module_name}",
        )
        if _tool_type in TOOL_REGISTRY.list_tool_types():
            TOOL_REGISTRY.replace(_metadata)
        else:
            TOOL_REGISTRY.register(_metadata)

_category_by_type = {entry.tool_type: entry.category for entry in _TOOL_CATALOG}
for _tool_type in TOOL_REGISTRY.list_tool_types():
    _old = TOOL_REGISTRY.get(_tool_type)
    if _old.semantics_doc != "docs/tools/baseline.md":
        continue
    _function = _unavailable_tool(_tool_type, _category_by_type.get(_tool_type, ""))
    _class = type(f"{_tool_type}Tool", (_MappedTool,), {"tool_type": _tool_type, "function": staticmethod(_function)})
    TOOL_REGISTRY.replace(ToolMetadata(
        tool_type=_tool_type, function=_function, tool_class=_class,
        input_anchors=_old.input_anchors, output_anchors=_old.output_anchors,
        maturity="L1_PREREQUISITE_REQUIRED", semantics_doc="docs/tools/unavailable.md",
        supports_certification=False, execution_profile="unavailable",
    ))

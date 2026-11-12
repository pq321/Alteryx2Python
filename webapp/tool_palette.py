"""Runtime-derived tool capabilities; registration is not execution proof."""
from __future__ import annotations

from copy import deepcopy
from xml.etree import ElementTree as ET

from alteryx2python.parser.tool_catalog import CATALOG
from alteryx2python.tools.registry import TOOL_REGISTRY


HTML_TOOLS = {"PortfolioComposerText", "PortfolioComposerTable", "PortfolioComposerLayout", "PortfolioComposerRender"}
METADATA_ONLY_TOOLS = {"APIOutput", "BlobOutput", "DynamicInput", "FuzzyMatch", "PDFInput", "PDFToText"}


def tool_ports(kind):
    if kind == "JupyterCode":
        return (["Input", *[f"Input{i}" for i in range(2, 6)]], ["Output", *[f"Output{i}" for i in range(2, 6)]])
    if kind not in TOOL_REGISTRY.list_tool_types():
        return [], []
    metadata = TOOL_REGISTRY.get(kind)
    return list(metadata.input_anchors), list(metadata.output_anchors)


def blocked_reason(metadata):
    if metadata.tool_type in METADATA_ONLY_TOOLS:
        return "The current adapter records metadata instead of performing the configured operation"
    if metadata.execution_profile == "unavailable" or metadata.semantics_doc.endswith(("/baseline.md", "/unavailable.md")):
        return "No executable Python adapter is implemented"
    if metadata.semantics_doc == "docs/tools/reporting.md" and metadata.tool_type not in HTML_TOOLS | {"Email"}:
        return "Only report metadata is implemented; no HTML renderer"
    return None


def build_palette(simple_tools):
    entries = {entry.tool_type: entry for entry in reversed(CATALOG)}
    simple = {tool["type"]: tool for tool in simple_tools}
    tools, unavailable = [], []
    for kind in TOOL_REGISTRY.list_tool_types():
        metadata = TOOL_REGISTRY.get(kind)
        entry = entries.get(kind)
        reason = blocked_reason(metadata)
        if reason:
            unavailable.append({"type": kind, "label": entry.display_name if entry else kind, "reason": reason})
            continue
        tool = deepcopy(simple.get(kind, {"type": kind, "label": entry.display_name if entry else kind,
                                          "category": entry.category if entry else "Macros" if kind.startswith("Macro_") else "Developer",
                                          "inputs": list(metadata.input_anchors), "outputs": list(metadata.output_anchors)}))
        settings = {}
        if entry:
            settings = {key: value for key, value in (("EngineDll", entry.engine_dll), ("EngineDllEntryPoint", entry.engine_entry), ("Macro", entry.engine_macro)) if value}
        tool.update(advancedConfig=True, executionProfile=metadata.execution_profile,
                    maturity=metadata.maturity, semanticsDoc=metadata.semantics_doc,
                    nativeEquivalence="unverified", configurationMode="simple" if kind in simple else "xml")
        from alteryx2python.runtime.app_config import INTERFACE, LAYOUT
        if kind in INTERFACE - LAYOUT - {"Error"}:
            tool["configurationScope"] = "workflow"
        if kind not in simple:
            tool["defaults"] = {"configurationXml": "<Configuration />",
                                "engineSettingsXml": ET.tostring(ET.Element("EngineSettings", settings), encoding="unicode")}
        if kind == "JupyterCode":
            tool["inputs"], tool["outputs"] = tool_ports(kind)
        tool.setdefault("multiInput", len(metadata.input_anchors) > 1 or kind in {"Union", "JoinMultiple"})
        tools.append(tool)
    tools.append({"type": "Macro", "label": "Custom Macro", "category": "Macros", "inputs": ["Input"], "outputs": ["Output"],
                  "multiInput": True, "advancedConfig": True, "configurationMode": "xml", "executionProfile": "local-static-macro",
                  "defaults": {"configurationXml": "<Configuration />", "engineSettingsXml": '<EngineSettings Macro="" />'}})
    return {"tools": tools, "unavailable": unavailable, "workflowConfig": {
        "xmlFields": {"workflowXml": "AlteryxDocument", "propertiesXml": "Properties", "runtimePropertiesXml": "RuntimeProperties",
                      "eventsXml": "Events", "constantsXml": "Constants"},
        "nodeXmlFields": {"configurationXml": "Configuration", "engineSettingsXml": "EngineSettings"},
        "parameterModes": ["dynamic", "specialized"],
        "runtime": {"answers": {}, "constants": {}, "delivery_profile": "html-draft-v1", "allowed_commands": []},
        "eventTimings": ["BeforeRun", "AfterRun", "AfterRunWithoutErrors", "AfterRunWithErrors", "AfterRunWithWarnings",
                         "AfterRunWithErrorsOrWarnings", "AfterRunWithoutErrorsOrWarnings"],
        "notes": ["Full XML preserves options beyond simplified editor controls.",
                  "Implemented adapters support configuration subsets; external prerequisites can still block execution.",
                  "Command permissions must be explicitly supplied; run settings never infer them.",
                  "Email events use the selected draft/SMTP profile; unsupported Action modes return explicit blockers."],
    }}

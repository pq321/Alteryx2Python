from __future__ import annotations

from alteryx2python.parser.tool_catalog import (
    CATALOG,
    CATALOG_BY_PLUGIN,
    TOOL_TYPES,
    catalog_entry_for_plugin,
    engine_binding_for_plugin,
)
from alteryx2python.parser.xml_parser import TOOL_PARSERS, _normalize_tool_type
from alteryx2python.tools.registry import TOOL_REGISTRY


def test_catalog_has_unique_plugin_ids():
    assert len(CATALOG) == len(CATALOG_BY_PLUGIN)


def test_catalog_covers_core_tool_families():
    families = {
        "AlteryxBasePluginsGui.Filter.Filter",
        "AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect",
        "AlteryxSpatialPluginsGui.Summarize.Summarize",
        "AlteryxGuiToolkit.ToolContainer.ToolContainer",
        "AlteryxGuiToolkit.Questions.TextBox.TextBox",
        "AlteryxConnectorGui.Download.Download",
        "CalgaryPluginsGui.CalgaryInput.CalgaryInput",
        "AlteryxCASSGui.CASS.CASS",
        "PortfolioPluginsGui.ComposerText.PortfolioComposerText",
        "LockInGui.LockInFormula.LockInFormula",
        "PlotlyCharting",
        "JupyterCode",
        "DateTimeNow",
    }
    for plugin_id in families:
        assert plugin_id in CATALOG_BY_PLUGIN, plugin_id


def test_catalog_engine_bindings_verified_from_exports():
    expected = {
        "AlteryxBasePluginsGui.JSONBuild.JSONBuild": ("AlteryxBasePluginsEngine.dll", "AlteryxJSONBuild"),
        "AlteryxConnectorGui.MongoInput.MongoInput": ("AlteryxConnectorEngine.dll", "AlteryxMongoInput"),
        "AlteryxCASSGui.ZIP9Coder.ZIP9Coder": ("AlteryxCASSEngine.dll", "AlteryxZIP9Coder"),
        "PortfolioPluginsGui.Email.Email": ("PortfolioPluginsEngine.dll", "AlteryxComposerEmail"),
        "LockInGui.LockInSelect.LockInSelect": ("LockInEngine.dll", "AlteryxLockInSelect"),
        "CalgaryPluginsGui.CalgaryJoin.CalgaryJoin": ("CalgaryPlugins.dll", "AlteryxCalgaryJoin"),
    }
    for plugin_id, (dll, entry) in expected.items():
        assert engine_binding_for_plugin(plugin_id)[:2] == (dll, entry), plugin_id


def test_every_catalog_tool_type_has_a_parser():
    missing = sorted(TOOL_TYPES - set(TOOL_PARSERS))
    assert missing == []


def test_every_catalog_tool_type_has_a_registry_entry():
    missing = sorted(TOOL_TYPES - set(TOOL_REGISTRY._registry))
    assert missing == []


def test_question_textbox_no_longer_collides_with_canvas_textbox():
    assert _normalize_tool_type("AlteryxGuiToolkit.Questions.TextBox.TextBox") == "QuestionTextBox"
    assert _normalize_tool_type("AlteryxGuiToolkit.Questions.TextBox.QuestionTextBox") == "QuestionTextBox"
    assert _normalize_tool_type("AlteryxGuiToolkit.TextBox.TextBox") == "TextBox"


def test_normalize_uses_catalog_first():
    assert _normalize_tool_type("AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect") == "Select"
    assert _normalize_tool_type("AlteryxSpatialPluginsGui.Summarize.Summarize") == "Summarize"
    assert _normalize_tool_type("WordCloud") == "WordCloud"
    assert _normalize_tool_type("CountRecords.yxmc") == "CountRecords"


def test_unknown_plugin_ids_still_fall_back():
    assert _normalize_tool_type("SomeVendor.Custom.Tool") == "Tool"
    entry = catalog_entry_for_plugin("SomeVendor.Custom.Tool")
    assert entry is None

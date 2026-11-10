from __future__ import annotations

from pathlib import Path

import pytest

from alteryx2python.parser.tool_catalog import TOOL_TYPES
from alteryx2python.parser.xml_parser import XmlWorkflowParser

SAMPLES_ROOT = Path("D:/Alteryx/Samples/en")
ONE_TOOL_ROOT = SAMPLES_ROOT / "02 Learn_one_tool_at_a_time"

pytestmark = pytest.mark.skipif(
    not SAMPLES_ROOT.exists(),
    reason="official Alteryx sample corpus not installed on this host",
)


def _sample_files() -> list[Path]:
    if not ONE_TOOL_ROOT.exists():
        return []
    return sorted(ONE_TOOL_ROOT.rglob("*.yxmd"))


def test_official_one_tool_corpus_parses_without_unknown_tools():
    parser = XmlWorkflowParser()
    files = _sample_files()
    assert files, "expected at least one official sample workflow"
    unknown: list[tuple[str, object]] = []
    for sample in files:
        workflow = parser.parse(sample)
        for node in workflow.nodes:
            if node.tool_type == "UNKNOWN":
                unknown.append((sample.name, node.metadata.get("plugin_name")))
    assert unknown == []


def test_official_one_tool_corpus_nodes_are_catalog_or_macro_fallback():
    parser = XmlWorkflowParser()
    for sample in _sample_files():
        workflow = parser.parse(sample)
        for node in workflow.nodes:
            if node.tool_type.startswith("Macro_"):
                continue
            assert node.tool_type in TOOL_TYPES, (sample.name, node.tool_type)


def test_catalog_metadata_attached_to_nodes():
    parser = XmlWorkflowParser()
    files = _sample_files()
    if not files:
        pytest.skip("no samples")
    workflow = parser.parse(files[0])
    cataloged = [node for node in workflow.nodes if "catalog" in node.metadata]
    assert cataloged, "expected catalog metadata on parsed nodes"
    entry = cataloged[0].metadata["catalog"]
    assert entry["tool_type"]
    assert "source" in entry

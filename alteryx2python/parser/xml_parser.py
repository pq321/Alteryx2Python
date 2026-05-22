from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree

from alteryx2python.ir.models import WorkflowIR
from alteryx2python.parser.base_parser import BaseWorkflowParser


class XmlWorkflowParser(BaseWorkflowParser):
    """Parses workflow-level XML metadata into a minimal IR shell.

    Tool extraction remains a follow-up step and is intentionally surfaced as a warning.
    """

    def parse(self, source_path: Path) -> WorkflowIR:
        contents = source_path.read_bytes()
        root = ElementTree.fromstring(contents)
        return WorkflowIR(
            workflow_id=root.attrib.get("WorkflowId", source_path.stem),
            workflow_name=root.attrib.get("name", source_path.stem),
            source_file=str(source_path),
            source_hash=sha256(contents).hexdigest(),
            parser_version="0.1.0",
            migration_spec_version="0.1.0",
            warnings=["XML parsed but node/tool extraction is not implemented yet."],
            classification="CLASS_D_PARTIAL_MIGRATION_ONLY",
        )
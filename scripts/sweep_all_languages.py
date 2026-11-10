from collections import Counter
from pathlib import Path
from alteryx2python.parser.tool_catalog import TOOL_TYPES
from alteryx2python.parser.xml_parser import XmlWorkflowParser

root = Path(r"D:\Alteryx\Samples")
parser = XmlWorkflowParser()
files = sorted(root.rglob("*.yxmd"))
unknown = 0
errors = 0
macro_types = Counter()
type_counts = Counter()
for f in files:
    try:
        ir = parser.parse(f)
    except Exception as exc:  # noqa: BLE001
        errors += 1
        print("ERR", f, str(exc)[:100])
        continue
    for node in ir.nodes:
        type_counts[node.tool_type] += 1
        if node.tool_type == "UNKNOWN":
            unknown += 1
        elif node.tool_type.startswith("Macro_"):
            macro_types[node.tool_type] += 1
print("ALL LANGUAGES files:", len(files), "errors:", errors, "unknown:", unknown)
print("distinct types:", len(type_counts))
print("generic macro fallbacks:", dict(macro_types))

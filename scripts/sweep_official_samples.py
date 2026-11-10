from collections import Counter
from pathlib import Path

from alteryx2python.parser.tool_catalog import TOOL_TYPES
from alteryx2python.parser.xml_parser import XmlWorkflowParser

root = Path(r"D:\Alteryx\Samples\en")
parser = XmlWorkflowParser()
files = sorted(root.rglob("*.yxmd"))
type_counts = Counter()
unknown_nodes = []
uncataloged = Counter()
errors = []
for f in files:
    try:
        ir = parser.parse(f)
    except Exception as exc:  # noqa: BLE001
        errors.append((f.name, str(exc)[:120]))
        continue
    for node in ir.nodes:
        type_counts[node.tool_type] += 1
        if node.tool_type == "UNKNOWN":
            unknown_nodes.append((f.name, node.metadata.get("plugin_name")))
        elif node.tool_type not in TOOL_TYPES:
            uncataloged[node.tool_type] += 1
print("files:", len(files))
print("errors:", len(errors))
for name, err in errors[:10]:
    print("  ERR", name, err)
print("unknown nodes:", len(unknown_nodes))
for name, plugin in unknown_nodes[:10]:
    print("  UNKNOWN", name, plugin)
print("uncataloged tool types:", dict(uncataloged))
print("distinct tool types seen:", len(type_counts))
print("top:", type_counts.most_common(15))

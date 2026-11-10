"""Visual workflow editor server (stdlib only - no extra dependencies).

Serves the canvas frontend and exposes:

- GET  /api/tools    -> editor tool palette (anchors + default configs)
- POST /api/import  -> uploaded CSV/TSV/XLSX -> normalized file and preview
- POST /api/compile  -> editor graph JSON -> {yxmd, python, unsupported}
- POST /api/run      -> compile + execute through the alteryx2python runtime,
                        returning the workflow output as JSON records

Run with:  uv run python webapp/server.py [--port 18081]
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import sys
import tempfile
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEBAPP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = WEBAPP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(WEBAPP_DIR) not in sys.path:
    sys.path.insert(0, str(WEBAPP_DIR))

from graph_compiler import compile_graph_to_yxmd  # noqa: E402
from standalone_gen import generate_standalone  # noqa: E402

EDITOR_TOOLS = [
    {"type": "TextInput", "label": "Text Input", "category": "In/Out", "inputs": [], "outputs": ["Output"],
     "defaults": {"fields": ["Col1", "Col2"], "rows": [["a", "1"], ["b", "2"]]}},
    {"type": "DbFileInput", "label": "Input File", "category": "In/Out", "inputs": [], "outputs": ["Output"],
     "defaults": {"file": "", "name": "", "fields": [], "rows": [], "rowCount": 0,
                  "sourceFile": "", "sheets": [], "sheet": "", "delimiter": ","}},
    {"type": "DbFileOutput", "label": "Output Data (CSV)", "category": "In/Out", "inputs": ["Input"], "outputs": [],
     "defaults": {"file": "output.csv"}},
    {"type": "Formula", "label": "Formula", "category": "Preparation", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"expressions": [{"field": "NewField", "type": "Double", "size": "", "expression": "[Col2] * 2"}]}},
    {"type": "Filter", "label": "Filter", "category": "Preparation", "inputs": ["Input"], "outputs": ["True", "False"],
     "defaults": {"expression": "[Col2] >= 1"}},
    {"type": "Select", "label": "Select", "category": "Preparation", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"fields": [{"field": "Col1", "selected": "True"}], "includeUnknown": True}},
    {"type": "Sort", "label": "Sort", "category": "Preparation", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"order": [{"field": "Col2", "order": "Ascending"}]}},
    {"type": "Unique", "label": "Unique", "category": "Preparation", "inputs": ["Input"], "outputs": ["Unique", "Duplicates"],
     "defaults": {"field": "Col1"}},
    {"type": "MultiRowFormula", "label": "Multi-Row Formula", "category": "Preparation", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"expression": "[Col2] - [Row-1:Col2]", "fieldName": "Delta"}},
    {"type": "DateTime", "label": "DateTime", "category": "Preparation", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"inputField": "DateCol", "outputField": "ParsedDate", "format": "yyyy-MM-dd"}},
    {"type": "Summarize", "label": "Summarize", "category": "Transform", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"actions": [
         {"field": "Col1", "action": "GroupBy", "rename": ""},
         {"field": "Col2", "action": "Sum", "rename": "Sum_Col2"},
     ]}},
    {"type": "CrossTab", "label": "Cross Tab", "category": "Transform", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"groupBy": "Col1", "header": "Col2", "dataField": "Col3", "method": "First"}},
    {"type": "Transpose", "label": "Transpose", "category": "Transform", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"keyFields": ["Col1"], "dataFields": ["Col2", "Col3"]}},
    {"type": "RecordID", "label": "Record ID", "category": "Transform", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"fieldName": "RecordID"}},
    {"type": "Sample", "label": "Sample", "category": "Transform", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"mode": "First", "n": "10"}},
    {"type": "RunningTotal", "label": "Running Total", "category": "Transform", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"field": "Col2"}},
    {"type": "Rank", "label": "Rank", "category": "Transform", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"field": "Col2", "order": "Descending"}},
    {"type": "TextToColumns", "label": "Text to Columns", "category": "Transform", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"field": "Col1", "delimiter": ",", "numFields": "3", "rootName": ""}},
    {"type": "Join", "label": "Join", "category": "Join", "inputs": ["Left", "Right"], "outputs": ["Join", "Left", "Right"],
     "defaults": {"leftField": "Key", "rightField": "Key"}},
    {"type": "Union", "label": "Union", "category": "Join", "inputs": ["Input"], "outputs": ["Output"], "multiInput": True,
     "defaults": {}},
    {"type": "RegEx", "label": "RegEx", "category": "Parse", "inputs": ["Input"], "outputs": ["Output"],
     "defaults": {"field": "Col1", "pattern": "(\\d+)", "outputField": "Parsed"}},
]


class EditorHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # quiet
        pass

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length < 0 or length > 30 * 1024 * 1024:
            raise ValueError("Request exceeds 30 MB")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path == "/api/tools":
            self._send_json({"tools": EDITOR_TOOLS})
            return
        static = {
            "/": ("static/index.html", "text/html; charset=utf-8"),
            "/style.css": ("static/style.css", "text/css; charset=utf-8"),
        }.get(path)
        if path.startswith("/dist/") and path.endswith(".js"):
            candidate = (WEBAPP_DIR / "static" / path.lstrip("/")).resolve()
            if candidate.is_relative_to((WEBAPP_DIR / "static/dist").resolve()) and candidate.is_file():
                static = (str(candidate), "text/javascript; charset=utf-8")
        if static:
            file_path = WEBAPP_DIR / static[0]
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", static[1])
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            return
        self._send_json({"error": "not found", "path": path}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            graph = self._read_json()
            if path == "/api/import":
                self._send_json(_import_data(graph))
            elif path == "/api/compile":
                self._send_json(_compile(graph))
            elif path == "/api/run":
                self._send_json(_run(graph))
            else:
                self._send_json({"error": "not found", "path": path}, 404)
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                {"error": str(exc), "trace": traceback.format_exc()[-2000:]}, 400
            )


def _compile(graph: dict) -> dict:
    _validate_graph(graph)
    yxmd = compile_graph_to_yxmd(graph)
    python, unsupported = generate_standalone(graph)
    return {
        "name": graph.get("name", "workflow"),
        "yxmd": yxmd,
        "python": python,
        "unsupported": unsupported,
    }


def _run(graph: dict) -> dict:
    from alteryx2python.parser.xml_parser import XmlWorkflowParser
    from alteryx2python.runtime.context import WorkflowContext
    from alteryx2python.runtime.executor import run_workflow_graph

    compile_result = _compile(graph)
    with tempfile.TemporaryDirectory(prefix="ayx_editor_") as tmp:
        yxmd_path = Path(tmp) / "workflow.yxmd"
        yxmd_path.write_text(compile_result["yxmd"], encoding="utf-8")
        workflow = XmlWorkflowParser().parse(yxmd_path)
        output_nodes = [node for node in workflow.nodes if node.tool_type == "DbFileOutput"]
        # Preview runs isolate sinks; only the user's downloaded script writes configured paths.
        for node in output_nodes:
            normalized = node.config["normalized"]
            normalized["file"] = str(Path(tmp) / (node.node_id + ".csv"))
            normalized["format_specific_options"]["CodePage"] = {"text": "65001"}
        context = WorkflowContext()
        result = run_workflow_graph(workflow, context)
        import pandas as pd

        original_ids = {str(index + 1): str(node["id"]) for index, node in enumerate(graph["nodes"])}
        previews = []
        for node_id, node_result in result.node_results.items():
            for anchor, frame in node_result.outputs.items():
                previews.append(_preview(original_ids[node_id], anchor, frame))
        for node in output_nodes:
            output = Path(node.config["normalized"]["file"])
            frame = pd.read_csv(output, dtype=object, keep_default_na=False)
            previews.append(_preview(original_ids[node.node_id], "Input", frame))
        final = previews[-1] if previews else {"columns": [], "rows": []}
        return {**compile_result, "previews": previews, "columns": final["columns"], "rows": final["rows"]}


def _preview(node_id, anchor, frame):
    return {
        "node": node_id, "anchor": anchor, "columns": [str(column) for column in frame.columns],
        "rows": json.loads(frame.head(500).to_json(orient="split", date_format="iso"))["data"],
        "rowCount": len(frame), "csv": frame.to_csv(index=False),
    }


def _validate_graph(graph):
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) or not graph["nodes"]:
        raise ValueError("Workflow requires at least one node")
    tools = {tool["type"]: tool for tool in EDITOR_TOOLS}
    nodes = {}
    for node in graph["nodes"]:
        node_id = str(node["id"])
        if node_id in nodes or node.get("type") not in tools:
            raise ValueError(f"Invalid or duplicate node: {node_id}")
        nodes[node_id] = node
        config = node.get("config", {})
        if node["type"] == "TextInput":
            _validate_fields(config.get("fields", []))
            if any(len(row) != len(config["fields"]) for row in config.get("rows", [])):
                raise ValueError(f"Text Input #{node_id}: row width must match fields")
        if node["type"] == "DbFileInput" and not config.get("file"):
            raise ValueError(f"Input File #{node_id}: import a data file first")
    occupied = set()
    adjacency = {node_id: [] for node_id in nodes}
    indegree = {node_id: 0 for node_id in nodes}
    edge_keys = set()
    for edge in graph.get("edges", []):
        source, target = str(edge["from"]), str(edge["to"])
        if source not in nodes or target not in nodes:
            raise ValueError("Connection references an unknown node")
        out_anchor, in_anchor = edge.get("fromAnchor", "Output"), edge.get("toAnchor", "Input")
        source_tool, target_tool = tools[nodes[source]["type"]], tools[nodes[target]["type"]]
        if out_anchor not in source_tool["outputs"] or in_anchor not in target_tool["inputs"]:
            raise ValueError(f"Invalid connection anchor: {source} -> {target}")
        key = (source, out_anchor, target, in_anchor)
        if key in edge_keys:
            raise ValueError("Duplicate connection")
        edge_keys.add(key)
        if (target, in_anchor) in occupied and not target_tool.get("multiInput"):
            raise ValueError(f"Node #{target}: input {in_anchor} already connected")
        occupied.add((target, in_anchor))
        adjacency[source].append(target)
        indegree[target] += 1
    for node_id, node in nodes.items():
        for anchor in tools[node["type"]]["inputs"]:
            if (node_id, anchor) not in occupied:
                raise ValueError(f"{node['type']} #{node_id}: connect the {anchor} input")
    pending = [node_id for node_id, degree in indegree.items() if degree == 0]
    visited = 0
    while pending:
        visited += 1
        for target in adjacency[pending.pop()]:
            indegree[target] -= 1
            if not indegree[target]:
                pending.append(target)
    if visited != len(nodes):
        raise ValueError("Workflow contains a cycle")


def _validate_fields(fields):
    if not fields or any(not isinstance(name, str) or not name.strip() for name in fields):
        raise ValueError("Column names must be non-empty")
    if len(set(fields)) != len(fields):
        raise ValueError("Column names must be unique")


def _import_data(payload):
    import pandas as pd

    uploads = (WEBAPP_DIR / ".uploads").resolve()
    name = str(payload.get("name", "data.csv"))
    if "content" in payload:
        content = base64.b64decode(payload["content"], validate=True)
        if len(content) > 20 * 1024 * 1024:
            raise ValueError("File exceeds 20 MB")
        suffix = Path(name).suffix.lower()
        if suffix not in {".csv", ".tsv", ".txt", ".xlsx"}:
            raise ValueError("Supported files: CSV, TSV, TXT, XLSX")
        source = uploads / (uuid.uuid4().hex + suffix)
    else:
        source = Path(str(payload.get("sourceFile", ""))).resolve()
        if not source.is_relative_to(uploads) or not source.is_file():
            raise ValueError("Uploaded file is unavailable; import it again")
        content = source.read_bytes()
        suffix = source.suffix.lower()
    sheets, sheet, delimiter = [], "", ","
    if suffix == ".xlsx":
        with pd.ExcelFile(io.BytesIO(content), engine="openpyxl") as book:
            sheets = book.sheet_names
            sheet = str(payload.get("sheet") or sheets[0])
            frame = pd.read_excel(book, sheet_name=sheet, header=None, dtype=str, keep_default_na=False)
            if frame.empty:
                raise ValueError("Worksheet is empty")
            fields = [str(column) for column in frame.iloc[0]]
            data = frame.iloc[1:].values.tolist()
    else:
        encodings = ("utf-16",) if content.startswith((b"\xff\xfe", b"\xfe\xff")) else ("utf-8-sig", "gb18030")
        for encoding in encodings:
            try:
                decoded = content.decode(encoding)
                break
            except UnicodeError:
                continue
        else:
            raise ValueError("Unsupported text encoding; save as UTF-8")
        if not decoded.strip():
            raise ValueError("File is empty")
        if suffix == ".tsv":
            delimiter = "\t"
        else:
            try:
                delimiter = csv.Sniffer().sniff(decoded[:65536], delimiters=",\t;|").delimiter
            except csv.Error:
                delimiter = ","
        records = list(csv.reader(io.StringIO(decoded, newline=""), delimiter=delimiter))
        fields, data = records[0], [row for row in records[1:] if row]
    _validate_fields(fields)
    if any(len(row) != len(fields) for row in data):
        raise ValueError("File contains rows with a different number of columns")
    uploads.mkdir(exist_ok=True)
    if "content" in payload:
        source.write_bytes(content)
    normalized = uploads / (uuid.uuid4().hex + ".csv")
    with normalized.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(data)
    return {
        "file": normalized.as_posix(), "sourceFile": source.as_posix(), "name": name,
        "fields": fields, "rows": data[:100], "rowCount": len(data),
        "sheets": sheets, "sheet": sheet, "delimiter": delimiter,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18081)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), EditorHandler)
    print("editor running at http://127.0.0.1:" + str(args.port))
    server.serve_forever()


if __name__ == "__main__":
    main()

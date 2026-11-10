"""Visual workflow editor server (stdlib only - no extra dependencies).

Serves the canvas frontend and exposes:

- GET  /api/tools    -> editor tool palette (anchors + default configs)
- POST /api/compile  -> editor graph JSON -> {yxmd, python, unsupported}
- POST /api/run      -> compile + execute through the alteryx2python runtime,
                        returning the workflow output as JSON records

Run with:  uv run python webapp/server.py [--port 8765]
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import traceback
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
     "defaults": {"field": "Col1", "delimiter": ","}},
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
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/tools":
            self._send_json({"tools": EDITOR_TOOLS})
            return
        static = {
            "/": ("static/index.html", "text/html; charset=utf-8"),
            "/app.js": ("static/app.js", "text/javascript; charset=utf-8"),
            "/style.css": ("static/style.css", "text/css; charset=utf-8"),
        }.get(path)
        if static:
            file_path = WEBAPP_DIR / static[0]
            body = file_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", static[1])
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._send_json({"error": "not found", "path": path}, 404)

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            graph = self._read_json()
            if path == "/api/compile":
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
        if not output_nodes:
            raise ValueError("workflow has no Output Data node")
        target = output_nodes[0].node_id
        context = WorkflowContext()
        result = run_workflow_graph(workflow, context, target_node_ids={target})
        if target not in result.node_results:
            raise RuntimeError("output node did not execute")
        # The DbFileOutput sink writes a CSV; read it back as records.
        file_value = str(output_nodes[0].config.get("normalized", {}).get("file", ""))
        if not file_value:
            raise ValueError("Output Data node has no file configured")
        csv_path = Path(file_value)
        if not csv_path.is_absolute():
            csv_path = (yxmd_path.parent / csv_path).resolve()
        import pandas as pd

        frame = pd.read_csv(csv_path, dtype=object, keep_default_na=False)
        return {
            "name": graph.get("name", "workflow"),
            "output_file": str(csv_path),
            "columns": [str(column) for column in frame.columns],
            "rows": frame.values.tolist(),
            "yxmd": compile_result["yxmd"],
            "python": compile_result["python"],
            "unsupported": compile_result["unsupported"],
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), EditorHandler)
    print("editor running at http://127.0.0.1:" + str(args.port))
    server.serve_forever()


if __name__ == "__main__":
    main()

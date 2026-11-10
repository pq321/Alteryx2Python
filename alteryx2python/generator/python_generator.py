from __future__ import annotations

from pprint import pformat
from dataclasses import asdict

from alteryx2python.generator.base_generator import BaseGenerator
from alteryx2python.ir.models import WorkflowIR


class PythonGenerator(BaseGenerator):
    def generate(self, workflow: WorkflowIR, *, include_main: bool = True) -> str:
        nodes = [asdict(node) for node in workflow.nodes]
        from alteryx2python.generator.macro_sources import collect_macro_sources

        embedded, missing = collect_macro_sources(workflow)
        workflow_data = {
            k: v for k, v in asdict(workflow).items() if k not in {"nodes", "edges"}
        }
        if embedded or missing:
            workflow_data["metadata"] = {
                **workflow_data["metadata"],
                "embedded_macros": embedded,
                "unresolved_macros": missing,
            }
        edges = [
            {
                "edge_id": edge.edge_id,
                "source_node_id": edge.source_node_id,
                "source_anchor": edge.source_anchor,
                "target_node_id": edge.target_node_id,
                "target_anchor": edge.target_anchor,
                "metadata": edge.metadata,
            }
            for edge in workflow.edges
        ]
        lines = [
            "from alteryx2python.ir.models import AnchorIR, EdgeIR, NodeIR, WorkflowIR",
            "from alteryx2python.runtime.context import WorkflowContext",
            "from alteryx2python.runtime.executor import run_workflow_graph",
            "",
            f"NODE_DATA = {pformat(nodes, width=100)}",
            "",
            f"EDGE_DATA = {pformat(edges, width=100)}",
            f"WORKFLOW_DATA = {pformat(workflow_data, width=100)}",
            "",
            "def build_workflow():",
            "    nodes = [NodeIR(**{**node,",
            "        'input_anchors': [AnchorIR(**anchor) for anchor in node['input_anchors']],",
            "        'output_anchors': [AnchorIR(**anchor) for anchor in node['output_anchors']]}) for node in NODE_DATA]",
            "    edges = [EdgeIR(**edge) for edge in EDGE_DATA]",
            "    return WorkflowIR(",
            "        **WORKFLOW_DATA,",
            "        nodes=nodes,",
            "        edges=edges,",
            "    )",
            "",
            "",
            "def run_workflow(runtime_config=None, initial_inputs=None, target_node_ids=None):",
            "    context = WorkflowContext(runtime_config=runtime_config)",
            "    result = run_workflow_graph(",
            "        build_workflow(),",
            "        context,",
            "        initial_inputs=initial_inputs,",
            "        target_node_ids=target_node_ids,",
            "    )",
            "    return result, context.execution_report()",
        ]
        if include_main:
            lines.extend(
                [
                    "",
                    "",
                    'if __name__ == "__main__":',
                    "    import argparse, json, sys",
                    "    from pathlib import Path",
                    "    parser = argparse.ArgumentParser(description='Run the converted workflow')",
                    "    parser.add_argument('--answers', type=Path)",
                    "    parser.add_argument('--output-dir', type=Path)",
                    "    args = parser.parse_args()",
                    "    runtime = {'answers': json.loads(args.answers.read_text(encoding='utf-8-sig'))} if args.answers else None",
                    "    if args.output_dir:",
                    "        from alteryx2python.parity.manual import export_review_results",
                    "        args.output_dir.mkdir(parents=True, exist_ok=False)",
                    "        capture = export_review_results(build_workflow(), args.output_dir, runtime_config=runtime)",
                    "        print(json.dumps({'status': capture['status'], 'failure': capture['failure'], 'output_dir': str(args.output_dir)}, ensure_ascii=False))",
                    "        sys.exit(0 if capture['status'] == 'success' else 2)",
                    "    result, trace = run_workflow(runtime_config=runtime)",
                    "    print(json.dumps({'status': 'success', 'execution_order': result.execution_order, 'outputs': {node_id: {anchor: frame.to_dict('records') for anchor, frame in node.outputs.items()} for node_id, node in result.node_results.items()}}, default=str, ensure_ascii=False))",
                ]
            )
        return "\n".join(lines)

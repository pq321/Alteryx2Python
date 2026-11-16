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
            "    return run_with_context(context, initial_inputs, target_node_ids)",
            "",
            "",
            "def run_with_context(context, initial_inputs=None, target_node_ids=None):",
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
                    "    parser.add_argument('--use-workflow-output-paths', action='store_true')",
                    "    parser.add_argument('--delivery-profile', choices=['xlsx-table-v1'])",
                    "    parser.add_argument('--log-event', action='append', default=[])",
                    "    parser.add_argument('--workflow-log', type=Path)",
                    "    parser.add_argument('--workflow-log-columns', type=Path)",
                    "    parser.add_argument('--as-of')",
                    "    parser.add_argument('--input-dir', type=Path)",
                    "    parser.add_argument('--bind-input', action='append', default=[])",
                    "    parser.add_argument('--allow-command', action='append', default=[])",
                    "    args = parser.parse_args()",
                    "    if args.use_workflow_output_paths and args.output_dir is not None:",
                    "        parser.error('Choose workflow output paths or an isolated output directory')",
                    "    runtime = {'answers': json.loads(args.answers.read_text(encoding='utf-8-sig'))} if args.answers else {}",
                    "    if args.use_workflow_output_paths:",
                    "        runtime['use_workflow_output_paths'] = True",
                    "    if args.delivery_profile:",
                    "        runtime['delivery_profile'] = args.delivery_profile",
                    "    if args.allow_command:",
                    "        runtime['allowed_commands'] = args.allow_command",
                    "    if args.as_of is not None:",
                    "        runtime['as_of'] = args.as_of",
                    "    if args.input_dir is not None:",
                    "        runtime['input_dir'] = args.input_dir.resolve()",
                    "    if args.bind_input:",
                    "        from alteryx2python.input_bindings import parse_input_bindings",
                    "        runtime['input_bindings'] = parse_input_bindings(args.bind_input)",
                    "    if args.log_event:",
                    "        from alteryx2python.workflow_logging import configure_workflow_logging",
                    "        configure_workflow_logging(args.workflow_log, args.workflow_log_columns)",
                    "        runtime['log_event_ids'] = args.log_event",
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

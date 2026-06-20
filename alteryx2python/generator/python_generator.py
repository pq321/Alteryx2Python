from __future__ import annotations

from pprint import pformat

from alteryx2python.generator.base_generator import BaseGenerator
from alteryx2python.ir.models import WorkflowIR


class PythonGenerator(BaseGenerator):
    def generate(self, workflow: WorkflowIR) -> str:
        nodes = [
            {
                "node_id": node.node_id,
                "source_tool_id": node.source_tool_id,
                "tool_type": node.tool_type,
                "tool_name": node.tool_name,
                "config": node.config,
                "supported_status": node.supported_status,
            }
            for node in workflow.nodes
        ]
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
            "from alteryx2python.ir.models import EdgeIR, NodeIR, WorkflowIR",
            "from alteryx2python.runtime.context import WorkflowContext",
            "from alteryx2python.runtime.executor import run_workflow_graph",
            "",
            f"NODE_DATA = {pformat(nodes, width=100)}",
            "",
            f"EDGE_DATA = {pformat(edges, width=100)}",
            "",
            "def build_workflow():",
            "    nodes = [NodeIR(**node) for node in NODE_DATA]",
            "    edges = [EdgeIR(**edge) for edge in EDGE_DATA]",
            "    return WorkflowIR(",
            f"        workflow_id={workflow.workflow_id!r},",
            f"        workflow_name={workflow.workflow_name!r},",
            f"        source_file={workflow.source_file!r},",
            f"        source_hash={workflow.source_hash!r},",
            f"        parser_version={workflow.parser_version!r},",
            f"        migration_spec_version={workflow.migration_spec_version!r},",
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
        return "\n".join(lines)

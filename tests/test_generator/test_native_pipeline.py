"""Synthetic, end-to-end differential coverage for native lowering stages."""
import ast
from copy import deepcopy

import pandas as pd
import pytest

from alteryx2python.generator.readable import ReadablePythonGenerator
from alteryx2python.ir.models import AnchorIR, EdgeIR, NodeIR, WorkflowIR
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.tools.registry import TOOL_REGISTRY


def _node(node_id, kind, config, schema=None):
    metadata = TOOL_REGISTRY.get(kind)
    return NodeIR(
        node_id=node_id, source_tool_id=node_id, tool_type=kind, tool_name=kind,
        config={"normalized": deepcopy(config)},
        input_anchors=[AnchorIR(name, "input") for name in metadata.input_anchors],
        output_anchors=[AnchorIR(name, "output") for name in metadata.output_anchors],
        expected_output_schema=schema or {},
    )


def _text(node_id, fields, rows):
    return _node(node_id, "TextInput", {"fields": fields, "rows": rows})


def _workflow(tmp_path, nodes, connections):
    edges = [EdgeIR(str(index), source, anchor, target, port)
             for index, (source, anchor, target, port) in enumerate(connections)]
    for node in nodes:
        node.incoming_edges = [edge.edge_id for edge in edges if edge.target_node_id == node.node_id]
        node.outgoing_edges = [edge.edge_id for edge in edges if edge.source_node_id == node.node_id]
    return WorkflowIR(
        workflow_id="synthetic-native-pipeline", workflow_name="Synthetic pipeline",
        source_file=str(tmp_path / "workflow.yxmd"), source_hash="synthetic",
        parser_version="test", migration_spec_version="test", nodes=nodes, edges=edges,
    )


def _standalone_source(source):
    tree = ast.parse(source)
    assert "checkpoints" not in source
    for node in ast.walk(tree):
        modules = ([node.module or ""] if isinstance(node, ast.ImportFrom) else
                   [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
        assert not any(name.startswith(("alteryx2python", "alteryx_runtime")) for name in modules)


def _compare(workflow, tmp_path):
    baseline = run_workflow_graph(deepcopy(workflow), WorkflowContext())
    artifact = ReadablePythonGenerator().generate(workflow)
    _standalone_source(artifact.source)
    namespace = {"__file__": str(tmp_path / "verify.py")}
    exec(artifact.verification_source, namespace)
    checkpoints = {}
    namespace["run_workflow"](input_dir=tmp_path, output_dir=tmp_path / "verification", checkpoints=checkpoints)
    assert set(checkpoints) == set(baseline.node_results)
    for node_id, result in baseline.node_results.items():
        assert set(checkpoints[node_id]) == set(result.outputs), node_id
        for anchor, expected in result.outputs.items():
            actual = checkpoints[node_id][anchor]
            try:
                pd.testing.assert_frame_equal(actual, expected, check_exact=True)
                assert actual.attrs.get("alteryx_schema", []) == expected.attrs.get("alteryx_schema", [])
            except AssertionError as exc:
                raise AssertionError(f"Checkpoint {node_id}/{anchor}: {exc}") from exc
    return artifact, checkpoints


def _unary(tmp_path, kind, fields, rows, config, schema=None, upstream=None):
    nodes = [_text("seed", fields, rows)]
    edges = []
    source, anchor = "seed", "Output"
    for node, output_anchor in upstream or []:
        nodes.append(node)
        edges.append((source, anchor, node.node_id, "Input"))
        source, anchor = node.node_id, output_anchor
    nodes.append(_node("result", kind, config, schema))
    edges.append((source, anchor, "result", "Input"))
    return _compare(_workflow(tmp_path, nodes, edges), tmp_path)[1]


@pytest.mark.parametrize(
    "selection, order, empty",
    [
        ([{"source": "quantity", "rename": "units", "dtype": "Int16"},
          {"source": "discard", "selected": False}, {"source": "*Unknown"}], ["label", "units"], False),
        ([{"source": "*Unknown"}, {"source": "quantity", "rename": "units"},
          {"source": "discard", "selected": False}], ["units", "label"], False),
        ([{"source": "quantity", "rename": "units", "dtype": "Int32"},
          {"source": "label", "rename": "tag", "dtype": "V_WString", "size": 12}], ["tag", "units"], False),
        ([{"source": "quantity", "rename": "units", "dtype": "Int64"}], ["units"], True),
    ],
    ids=["typed-wildcard", "wildcard-first", "typed-renamed-order", "typed-empty"],
)
def test_select_wildcards_renames_types_and_expected_order(tmp_path, selection, order, empty):
    checkpoints = _unary(
        tmp_path, "Select", ["quantity", "discard", "label"],
        [] if empty else [["7", "unused", "oak"], [None, "ignored", "birch"]],
        {"select_fields": selection}, {"Output": {"fields": [{"name": name} for name in order]}},
    )
    assert list(checkpoints["result"]["Output"].columns) == order


@pytest.mark.parametrize("dtype,size,rows", [
    ("Double", None, [["2.5", "cedar"], [None, "fir"], ["4", "elm"]]),
    ("FixedDecimal", "8.2", [["12.345", "pine"], [None, "ash"], ["-4.125", "oak"]]),
    ("Date", None, [["2024-02-03", "maple"], [None, "birch"], ["2023-11-09", "fir"]]),
])
def test_select_declared_types_survive_downstream_rename_and_wildcard(tmp_path, dtype, size, rows):
    declared = _node("declared", "Select", {"select_fields": [
        {"source": "raw", "rename": "converted", "dtype": dtype, "size": size},
        {"source": "label", "dtype": "V_WString", "size": 16},
    ]})
    _unary(tmp_path, "Select", ["raw", "label"], rows,
           {"select_fields": [{"source": "converted", "rename": "metric"}, {"source": "*Unknown"}]},
           upstream=[(declared, "Output")])


@pytest.mark.parametrize("empty, descending", [(False, False), (False, True), (True, False)])
def test_sort_multiple_keys_and_stable_ties(tmp_path, empty, descending):
    _unary(tmp_path, "Sort", ["category", "priority", "original"],
           [] if empty else [["b", "3", "first"], ["a", "2", "middle"],
                             ["b", "3", "second"], [None, "1", "null"]],
           {"sort_fields": [{"field": "category", "order": "Ascending"},
                            {"field": "priority", "order": "Descending" if descending else "Ascending"}]})


@pytest.mark.parametrize("mode,n", [("First", 2), ("Last", 2), ("Sample", 2), ("EveryNth", 3),
                                  ("Random", 3), ("NPercent", 50), ("EveryNth", 0)])
@pytest.mark.parametrize("grouped", [False, True])
def test_sample_modes_grouped_and_ungrouped(tmp_path, mode, n, grouped):
    _unary(tmp_path, "Sample", ["batch", "reading"],
           [["west", "9"], ["east", "2"], ["west", "7"], [None, "3"], ["east", "8"], ["west", "4"]],
           {"mode": mode, "n": n, "group_fields": ["batch"] if grouped else []})


@pytest.mark.parametrize("mode", ["First", "Last", "Sample", "EveryNth", "Random", "NPercent"])
@pytest.mark.parametrize("grouped", [False, True])
def test_sample_empty_inputs_keep_schema(tmp_path, mode, grouped):
    _unary(tmp_path, "Sample", ["region", "measurement"], [],
           {"mode": mode, "n": 2, "group_fields": ["region"] if grouped else []})


@pytest.mark.parametrize("keys,empty", [([], False), (["tag"], False), (["tag", "zone"], False), (["tag"], True)])
def test_unique_checks_both_anchors_and_preserves_indices(tmp_path, keys, empty):
    checkpoints = _unary(tmp_path, "Unique", ["tag", "zone", "weight"],
                         [] if empty else [["p", "n", "1"], ["q", "s", "2"], ["p", "n", "1"],
                                           [None, "n", "3"], [None, "n", "3"], ["p", "s", "4"]],
                         {"unique_fields": keys})
    assert set(checkpoints["result"]) == {"Unique", "Duplicates"}


@pytest.mark.parametrize("groups,position,dtype,empty", [([], 0, "Int16", False), (["team"], 1, "Int32", False),
                                                        (["team", "zone"], 0, "Int64", False), (["team"], 1, "Int64", True)])
def test_recordid_groups_start_type_and_position(tmp_path, groups, position, dtype, empty):
    _unary(tmp_path, "RecordID", ["team", "zone", "item"],
           [] if empty else [["a", "x", "p"], ["b", "x", "q"], ["a", "y", "r"], [None, "x", "s"], ["a", "x", "t"]],
           {"field_name": "sequence", "start_value": -3, "position": position,
            "field_type": dtype, "group_fields": groups})


def test_recordid_after_unique_handles_nonconsecutive_indices(tmp_path):
    _unary(tmp_path, "RecordID", ["family", "item"],
           [["a", "x"], ["a", "x"], ["b", "y"], ["a", "z"], ["b", "y"]],
           {"field_name": "ordinal", "start_value": 11, "group_fields": ["family"], "position": 1},
           upstream=[(_node("distinct", "Unique", {"unique_fields": ["item"]}), "Unique")])


@pytest.mark.parametrize("modes,groups,empty", [([mode], ["squad"] if index % 2 else [], False)
                                               for index, mode in enumerate(["Ordinal", "Dense", "Standard", "Competition", "Fractional"]) ]
                         + [(["Ordinal", "Dense", "Fractional"], ["squad"], False), (["Dense"], ["squad"], True)],
                         ids=["ordinal", "dense-grouped", "standard", "competition-grouped", "fractional", "multiple-modes", "empty"])
def test_rank_ties_modes_and_grouping(tmp_path, modes, groups, empty):
    _unary(tmp_path, "Rank", ["squad", "points", "name"],
           [] if empty else [["r", "5", "c"], ["s", "5", "b"], ["r", "5", "a"],
                             ["s", "9", "d"], [None, None, "e"], ["r", "2", "f"]],
           {"ranking_modes": modes, "group_fields": groups,
            "sort_fields": [{"field": "points", "order": "Descending"}, {"field": "name", "order": "Ascending"}]})


@pytest.mark.parametrize("groups,empty", [([], False), (["series"], False), (["series", "zone"], False), (["series"], True)])
def test_runningtotal_multiple_fields_grouping_and_nulls(tmp_path, groups, empty):
    _unary(tmp_path, "RunningTotal", ["series", "zone", "delta", "extra"],
           [] if empty else [["a", "u", "2", "1.5"], ["b", "u", "bad", "2"],
                             ["a", "v", "3", None], [None, "u", "4", "3.5"], ["a", "u", "-1", "1"]],
           {"group_by_fields": groups, "running_total_fields": ["delta", "extra"]})


@pytest.mark.parametrize("actions,grouped,empty", [
    (["Sum", "Count", "Avg", "Min", "Max"], False, False),
    (["Median", "StdDev", "Variance", "First", "Last"], True, False),
    (["Mode", "Longest", "Shortest", "CountBlank", "CountNonBlank", "Concat"], False, False),
    (["Sum", "Count", "First", "Last"], False, True),
    (["Sum", "Count"], True, True),
])
def test_summarize_aggregates_groups_and_empty(tmp_path, actions, grouped, empty):
    text_actions = {"Longest", "Shortest", "CountBlank", "CountNonBlank", "Concat", "Mode"}
    fields = ([{"field": "cluster", "action": "GroupBy", "rename": "bucket"}] if grouped else [])
    fields += [{"field": "label" if action in text_actions else "value", "action": action,
                "rename": "metric_" + action, "separator": "|", "concat_start": "[", "concat_end": "]"}
               for action in actions]
    _unary(tmp_path, "Summarize", ["cluster", "value", "label"],
           [] if empty else [["c", "2", "elm"], ["d", "8", ""], ["c", "4", "oak"],
                             [None, None, None], ["d", "6", "elm"], ["c", "4", "elm"]],
           {"summarize_fields": fields})


def test_summarize_group_fields_interspersed_with_aggregates(tmp_path):
    _unary(tmp_path, "Summarize", ["label", "value", "district"],
           [["a", "3", "west"], ["a", "2", "west"], ["b", "9", "east"]],
           {"summarize_fields": [{"field": "value", "action": "Sum", "rename": "total"},
                                 {"field": "district", "action": "GroupBy", "rename": "area"},
                                 {"field": "label", "action": "GroupBy", "rename": "group"}]})


def test_summarize_numeric_group_key_with_decimal_values(tmp_path):
    _unary(tmp_path, "Summarize", ["bucket", "amount"],
           [["1", "2.5"], ["2", "1.5"], ["1", "4.25"]],
           {"summarize_fields": [{"field": "bucket", "action": "GroupBy", "rename": "group"},
                                 {"field": "amount", "action": "Sum", "rename": "total"}]})


@pytest.mark.parametrize("scenario,selected", [("mixed", False), ("mixed", True), ("left-empty", True),
                                               ("right-empty", False), ("no-match", True), ("null-and-duplicates", False)])
def test_join_all_anchors_selections_and_unmatched_rows(tmp_path, scenario, selected):
    left_rows, right_rows = [["b", "2"], ["a", "1"], ["orphan", "7"]], [["a", "red"], ["b", "blue"], ["unused", "gray"]]
    if scenario == "left-empty":
        left_rows = []
    elif scenario == "right-empty":
        right_rows = []
    elif scenario == "no-match":
        right_rows = [["other", "pink"]]
    elif scenario == "null-and-duplicates":
        left_rows, right_rows = [["a", "2"], ["a", "3"], [None, "4"]], [["a", "red"], [None, "none"], ["a", "blue"]]
    config = {"joins": [{"connection": "Left", "field": "code"}, {"connection": "Right", "field": "reference"}]}
    if selected:
        config["select_fields"] = [{"source": "Right_color", "rename": "shade"},
                                   {"source": "Left_weight", "rename": "mass"},
                                   {"source": "Right_reference", "selected": False}]
    nodes = [_text("left", ["code", "weight"], left_rows), _text("right", ["reference", "color"], right_rows),
             _node("joined", "Join", config)]
    _compare(_workflow(tmp_path, nodes, [("left", "Output", "joined", "Left"), ("right", "Output", "joined", "Right")]), tmp_path)


@pytest.mark.parametrize("mode,custom,empty", [("ByName", False, False), ("ByName", True, False),
                                            ("ByPos", False, False), ("ByPos", True, False), ("ByName", False, True)])
def test_union_name_position_alignment_and_custom_stream_order(tmp_path, mode, custom, empty):
    nodes = [_text("alpha", ["label", "value"], [] if empty else [["one", "2"]]),
             _text("beta", ["value", "other"], [["3", "two"], [None, "three"]])]
    config = {"mode": mode}
    if custom:
        config.update(output_order=["#second", "#first"], input_connection_names={"Input": "#first", "Input_2": "#second"})
    schema = {"fields": [{"name": "first"}, {"name": "second"}]} if mode == "ByPos" else {}
    nodes.append(_node("combined", "Union", config, schema))
    _compare(_workflow(tmp_path, nodes, [("alpha", "Output", "combined", "Input"),
                                       ("beta", "Output", "combined", "Input")]), tmp_path)


def test_union_custom_order_from_edge_connection_names(tmp_path):
    nodes = [_text("alpha", ["label"], [["one"]]), _text("beta", ["label"], [["two"]]),
             _node("combined", "Union", {"mode": "ByName", "output_order": ["#second", "#first"]})]
    workflow = _workflow(tmp_path, nodes, [("alpha", "Output", "combined", "Input"),
                                          ("beta", "Output", "combined", "Input")])
    for edge, name in zip(workflow.edges, ("#first", "#second")):
        edge.metadata["raw"] = {"attributes": {"name": name}}
    _, checkpoints = _compare(workflow, tmp_path)
    assert checkpoints["combined"]["Output"]["label"].tolist() == ["two", "one"]


@pytest.mark.parametrize("scenario", ["collision", "target-empty", "source-empty", "typed-selection",
                                      "typed-source-empty", "wildcard-selection"])
def test_appendfields_collisions_empty_and_typed_selections(tmp_path, scenario):
    targets = [] if scenario == "target-empty" else [["west", "2"], ["east", "3"]]
    source = [] if scenario in {"source-empty", "typed-source-empty"} else [["unit", "7"]]
    if scenario == "typed-selection":
        source.append(["batch", "9"])
    config = {"cartesian_mode": "Error" if scenario == "collision" else "Allow"}
    if scenario in {"typed-selection", "typed-source-empty", "wildcard-selection"}:
        config["select_fields"] = [{"source": "Target_count", "rename": "quantity", "dtype": "Int16"},
                                   {"source": "Source_count", "rename": "factor", "dtype": "Double"},
                                   {"source": "Source_name", "selected": False}]
        if scenario == "wildcard-selection":
            config["select_fields"].append({"source": "*Unknown"})
    nodes = [_text("targets", ["name", "count"], targets), _text("source", ["name", "count"], source),
             _node("appended", "AppendFields", config)]
    _compare(_workflow(tmp_path, nodes, [("targets", "Output", "appended", "Targets"),
                                       ("source", "Output", "appended", "Source")]), tmp_path)


def test_branch_rejoin_and_delivery_sink_match_runtime(tmp_path):
    expected = tmp_path / "baseline" / "branches.csv"
    nodes = [
        _text("seed", ["lane", "score", "token"],
              [["x", "4", "a"], ["y", "1", "b"], ["x", "4", "a"], ["y", "8", "c"], ["y", "1", "b"]]),
        _node("split", "Unique", {"unique_fields": ["token"]}),
        _node("ordered", "Sort", {"sort_fields": [{"field": "score", "order": "Descending"}]}),
        _node("duplicates", "RecordID", {"field_name": "repeat_index", "start_value": 5, "position": 1}),
        _node("rejoin", "Union", {"mode": "ByName", "output_order": ["duplicates", "distinct"],
                                   "input_connection_names": {"Input": "distinct", "Input_2": "duplicates"}}),
        _node("sink", "DbFileOutput", {"file": str(expected), "file_attributes": {"FileFormat": "0"},
                                       "format_specific_options": {"Delimeter": ";", "LineEndStyle": "LF", "CodePage": "65001"}}),
    ]
    connections = [("seed", "Output", "split", "Input"), ("split", "Unique", "ordered", "Input"),
                   ("split", "Duplicates", "duplicates", "Input"), ("ordered", "Output", "rejoin", "Input"),
                   ("duplicates", "Output", "rejoin", "Input"), ("rejoin", "Output", "sink", "Input")]
    artifact, checkpoints = _compare(_workflow(tmp_path, nodes, connections), tmp_path)
    assert not checkpoints["split"]["Unique"].empty
    assert not checkpoints["split"]["Duplicates"].empty
    assert (tmp_path / "verification" / expected.name).read_bytes() == expected.read_bytes()
    namespace = {"__file__": str(tmp_path / "delivery.py")}
    exec(artifact.source, namespace)
    delivered = tmp_path / "delivered"
    namespace["run_workflow"](input_dir=tmp_path, output_dir=delivered)
    assert (delivered / expected.name).read_bytes() == expected.read_bytes()

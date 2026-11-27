"""Pack independent configurations of a tabular tool onto a shared canvas."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations, product
from os.path import relpath
from pathlib import Path
from xml.etree import ElementTree as ET

from alteryx2python.workflow_generator import WorkflowBuilder, escape

from .archetype_datasets import ArchetypeBundle


@dataclass(frozen=True)
class CanvasCase:
    case_id: str
    configuration_xml: str
    inputs: tuple[tuple[str, str], ...] = (("input", "Input"),)


@dataclass(frozen=True)
class WorkflowArtifact:
    workflow: Path
    case_nodes: dict[str, str]


def pairwise_cases(axes: dict[str, tuple[str, ...]]) -> list[dict[str, str]]:
    """Greedily cover each declared value pair, in deterministic order."""
    if not axes or any(not values for values in axes.values()):
        raise ValueError("Pairwise coverage requires a nonempty domain for every axis")
    keys = sorted(axes)
    candidates = list(product(*(sorted(set(axes[key])) for key in keys)))
    if len(keys) == 1:
        return [dict(zip(keys, values)) for values in candidates]
    pairs = [
        {(left, values[left], right, values[right]) for left, right in combinations(range(len(keys)), 2)}
        for values in candidates
    ]
    uncovered = set().union(*pairs)
    selected = []
    while uncovered:
        index = max(range(len(candidates)), key=lambda i: len(pairs[i] & uncovered))
        selected.append(dict(zip(keys, candidates[index])))
        uncovered.difference_update(pairs[index])
    return selected


def pack_tool_configurations(
    tool_type: str, cases: list[CanvasCase], dataset_bundle: ArchetypeBundle,
    *, workflow_path: Path, amp: bool = False,
) -> WorkflowArtifact:
    if not cases or len(cases) != len({case.case_id for case in cases}):
        raise ValueError("Canvas cases require unique IDs and at least one configuration")
    builder = WorkflowBuilder()
    sources = {}
    for index, name in enumerate(sorted({name for case in cases for name, _ in case.inputs})):
        path = dataset_bundle.files[name].resolve(strict=True)
        local_file = Path(relpath(path, workflow_path.parent.resolve())).as_posix()
        if path.suffix.lower() == ".yxdb":
            configuration = f'<File FileFormat="19">{escape(local_file)}</File><Passwords/><FormatSpecificOptions/>'
        else:
            configuration = (
                f'<File FileFormat="0">{escape(local_file)}</File><Passwords/>'
                "<FormatSpecificOptions><HeaderRow>True</HeaderRow><CodePage>65001</CodePage>"
                "<Delimeter>,</Delimeter><IgnoreQuotes>DoubleQuotes</IgnoreQuotes>"
                "<FieldLen>254</FieldLen></FormatSpecificOptions>"
            )
        sources[name] = builder._node(
            "DbFileInput",
            configuration,
            (54, 90 + 80 * index),
        )
    nodes = {}
    for index, case in enumerate(cases):
        config = ET.fromstring(case.configuration_xml)
        if config.tag != "Configuration":
            raise ValueError(f"Expected a Configuration element for {case.case_id}")
        if config.attrib or (config.text or "").strip():
            raise ValueError(f"Canvas configuration requires child elements for {case.case_id}")
        file = config.find("File")
        if file is not None and file.text and file.text.startswith("{dataset:"):
            token, marker, selector = file.text.partition("|||")
            if not token.endswith("}"):
                raise ValueError(f"Invalid dataset file binding: {file.text}")
            name = token.removeprefix("{dataset:").removesuffix("}")
            path = dataset_bundle.files[name].resolve(strict=True)
            file.text = Path(relpath(path, workflow_path.parent.resolve())).as_posix() + marker + selector
        if tool_type == "DbFileOutput" and file is not None and file.text:
            name, marker, selector = file.text.partition("|||")
            if Path(name).name != name or ":" in name or "\\" in name:
                raise ValueError("Output fixture path must be a local filename")
            file.text = f"{index + 1}_{name}{marker}{selector}"
        body = "".join(ET.tostring(child, encoding="unicode") for child in config)
        node = builder._node(tool_type, body, (240, 90 + 80 * index))
        nodes[case.case_id] = str(node)
        for name, anchor in case.inputs:
            builder.connect(sources[name], node, target_anchor=anchor)

    root = ET.fromstring(builder.render())
    properties = root.find("Properties")
    flag = properties.find("RunWithE2")
    if flag is None:
        flag = ET.SubElement(properties, "RunWithE2")
    flag.set("value", str(amp))
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    with workflow_path.open("xb") as stream:
        ET.ElementTree(root).write(stream, encoding="utf-8", xml_declaration=True)
    return WorkflowArtifact(workflow_path, nodes)

"""Local, dependency-backed adapters for media and lightweight text tools.

These adapters intentionally do not emulate hosted/model-backed Alteryx tools.
"""

from __future__ import annotations

import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.parser.tool_parsers.common import ToolParserResult
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.unavailable import ToolUnavailableError


def _frame(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    value = inputs.get("Input")
    if not isinstance(value, pd.DataFrame):
        raise KeyError("tool requires an Input anchor containing a pandas DataFrame")
    return value


def _record(
    kind: str,
    frame: pd.DataFrame,
    output: pd.DataFrame,
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type=kind,
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": frame},
        outputs={"Output": output},
        status="success",
        config={
            **config,
            "input_schema": snapshot_schema(frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return {"Output": output}


def _field(config: dict[str, Any]) -> str:
    value = str(
        config.get("field", config.get("text_field", config.get("image_field", "")))
    )
    if not value:
        raise ValueError("configuration requires field")
    return value


def jsonschema_tool(inputs, config, context):
    frame = _frame(inputs)
    field = _field(config)
    ensure_fields_exist(frame, [field])
    try:
        import jsonschema
    except ImportError as exc:
        raise RuntimeError("JSONSchema requires the jsonschema package") from exc
    schema = config.get("schema")
    if isinstance(schema, str):
        schema = json.loads(schema)
    if not isinstance(schema, dict):
        raise ValueError("JSONSchema requires an object schema")
    result = frame.copy()
    valid = []
    for value in frame[field]:
        candidate = json.loads(value) if isinstance(value, str) else value
        try:
            jsonschema.validate(candidate, schema)
            valid.append(True)
        except (
            json.JSONDecodeError,
            jsonschema.ValidationError,
            jsonschema.SchemaError,
        ):
            valid.append(False)
    result[str(config.get("result_field", "JSONSchemaValid"))] = valid
    return _record("JSONSchema", frame, result, config, context)


def imageprofile_tool(inputs, config, context):
    frame = _frame(inputs)
    field = _field(config)
    ensure_fields_exist(frame, [field])
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("ImageProfile requires Pillow") from exc
    result = frame.copy()
    widths = []
    heights = []
    modes = []
    for value in frame[field]:
        with Image.open(str(value)) as image:
            widths.append(image.width)
            heights.append(image.height)
            modes.append(image.mode)
    result["ImageWidth"] = widths
    result["ImageHeight"] = heights
    result["ImageMode"] = modes
    return _record("ImageProfile", frame, result, config, context)


def imageprocessing_tool(inputs, config, context):
    frame = _frame(inputs)
    field = _field(config)
    ensure_fields_exist(frame, [field])
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("ImageProcessing requires Pillow") from exc
    mode = str(config.get("mode", "grayscale")).lower()
    if config.get("steps"):
        steps = config["steps"]
        if len(steps) != 1 or str(steps[0].get("name", "")).lower() not in {
            "grayscale",
            "greyscale",
        }:
            raise ToolUnavailableError(
                "Local ImageProcessing supports a single grayscale step; other native step configurations need an adapter"
            )
        mode = "grayscale"
    result = frame.copy()
    values = []
    for value in frame[field]:
        with Image.open(str(value)) as image:
            if mode in {"grayscale", "greyscale"}:
                image = ImageOps.grayscale(image)
            elif mode not in {"identity", "copy"}:
                raise ValueError("ImageProcessing mode must be grayscale or identity")
            values.append(image.copy())
    result[str(config.get("result_field", field))] = values
    return _record("ImageProcessing", frame, result, config, context)


def imageoutput_tool(inputs, config, context):
    frame = _frame(inputs)
    field = _field(config)
    ensure_fields_exist(frame, [field])
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("ImageOutput requires Pillow") from exc
    if not config.get("output_dir"):
        raise ValueError("ImageOutput requires output_dir")
    directory = Path(str(config["output_dir"]))
    directory.mkdir(parents=True, exist_ok=True)
    result = frame.copy()
    paths = []
    for index, value in enumerate(frame[field]):
        target = directory / f"image_{index}.png"
        if isinstance(value, Image.Image):
            value.save(target)
        else:
            with Image.open(str(value)) as image:
                image.save(target)
        paths.append(str(target))
    result[str(config.get("result_field", "ImagePath"))] = paths
    return _record("ImageOutput", frame, result, config, context)


def textpreprocessing_tool(inputs, config, context):
    frame = _frame(inputs)
    field = _field(config)
    ensure_fields_exist(frame, [field])
    if any(
        config.get(key)
        for key in (
            "lemmatize",
            "digits",
            "punctuation",
            "stopwords",
            "default_stopwords",
            "added_stopwords",
        )
    ):
        raise ToolUnavailableError(
            "Requested native TextPreProcessing pipeline is outside the local case/whitespace profile"
        )
    mode = str(config.get("mode", "lowercase")).lower()
    result = frame.copy()
    values = []
    for value in frame[field].fillna(""):
        text = str(value)
        if mode == "lowercase":
            out = text.lower()
        elif mode == "uppercase":
            out = text.upper()
        elif mode == "strip":
            out = " ".join(text.split())
        elif mode == "tokens":
            out = " ".join(text.split())
        else:
            raise ValueError(
                "TextPreProcessing mode must be lowercase, uppercase, strip, or tokens"
            )
        values.append(out)
    result[str(config.get("result_field", field))] = values
    return _record("TextPreProcessing", frame, result, config, context)


def wordcloud_tool(inputs, config, context):
    frame = _frame(
        {"Input": inputs.get("textInput")} if "textInput" in inputs else inputs
    )
    if "imageInput" in inputs or config.get("mask") or config.get("phrases"):
        raise ToolUnavailableError(
            "Local WordCloud does not yet support native mask/phrase configuration"
        )
    field = _field(config)
    ensure_fields_exist(frame, [field])
    try:
        from wordcloud import WordCloud
    except ImportError as exc:
        raise RuntimeError("WordCloud requires the wordcloud package") from exc
    counts = Counter(
        token.lower()
        for value in frame[field].fillna("")
        for token in str(value).split()
    )
    if not counts:
        raise ValueError("WordCloud requires at least one non-empty token")
    output_path = Path(str(config.get("output_path", "wordcloud.png")))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = {
        "width": int(config.get("width", 800) or 800),
        "height": int(config.get("height", 400) or 400),
        "background_color": (config["background_color"].get("hex") or "white")
        if isinstance(config.get("background_color"), dict)
        else str(config.get("background_color", "white")),
    }
    max_words = int(config.get("max_words", 0) or 0)
    if max_words:
        kwargs["max_words"] = max_words
    WordCloud(**kwargs).generate_from_frequencies(counts).to_file(str(output_path))
    output = pd.DataFrame(
        {"WordCloudPath": [str(output_path)], "WordCount": [len(counts)]}
    )
    return _record("WordCloud", frame, output, config, context)


class _FunctionTool(BaseTool):
    function = staticmethod(lambda i, c, x: {})

    def execute(self, inputs, config, context):
        return self.function(inputs, config, context)


_SPECS = {
    "JSONSchema": jsonschema_tool,
    "ImageOutput": imageoutput_tool,
    "ImageProcessing": imageprocessing_tool,
    "ImageProfile": imageprofile_tool,
    "TextPreProcessing": textpreprocessing_tool,
    "WordCloud": wordcloud_tool,
}
IMPLEMENTATIONS = {
    name: type(
        f"{name}Tool",
        (_FunctionTool,),
        {
            "tool_type": name,
            "function": staticmethod(fn),
            "input_anchors": ("Input",),
            "output_anchors": ("Output",),
        },
    )
    for name, fn in _SPECS.items()
}
ANCHORS = {name: (("Input",), ("Output",)) for name in IMPLEMENTATIONS}
ANCHORS["WordCloud"] = (("textInput", "imageInput"), ("Output",))


def _parse(raw: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(normalized_config=dict(raw))


PARSERS = {}

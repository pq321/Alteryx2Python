"""Dependency-gated local computer-vision adapters; no model downloads."""

from __future__ import annotations
import shutil
import pandas as pd
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.unavailable import ToolUnavailableError


def _frame(inputs):
    f = inputs.get("Input")
    if f is None:
        raise KeyError("vision tool requires Input anchor")
    return f


def _done(name, inputs, out, c, ctx):
    if not isinstance(ctx, WorkflowContext):
        raise TypeError("vision tool requires WorkflowContext")
    if not c.get("source_tool_id"):
        raise ValueError("vision tool requires source_tool_id")
    ctx.record_node(
        node_id=str(c.get("node_id", "unknown")),
        tool_type=name,
        source_tool_id=str(c["source_tool_id"]),
        inputs=inputs,
        outputs=out,
        status="success",
        config=dict(c),
    )
    return out


def _path(c):
    p = c.get("image_field") or c.get("field") or "image_path"
    return p


def image_to_text(inputs, c, ctx):
    f = _frame(inputs).copy()
    field = _path(c)
    if field not in f:
        raise KeyError(field)
    if not shutil.which("tesseract"):
        raise ToolUnavailableError(
            "ImageToText unavailable: tesseract executable is not installed"
        )
    try:
        import pytesseract
    except ImportError as e:
        raise ToolUnavailableError(
            "ImageToText unavailable: optional pytesseract is not installed"
        ) from e
    from PIL import Image

    f[c.get("output_field", "Text")] = f[field].map(
        lambda p: pytesseract.image_to_string(
            Image.open(str(p)), lang=c.get("language", "eng")
        ).strip()
    )
    return _done("ImageToText", inputs, {"Output": f}, c, ctx)


def barcode(inputs, c, ctx):
    f = _frame(inputs).copy()
    field = _path(c)
    if field not in f:
        raise KeyError(field)
    try:
        import cv2
    except ImportError as e:
        raise ToolUnavailableError(
            "Barcode unavailable: optional OpenCV is not installed"
        ) from e
    detector = cv2.barcode_BarcodeDetector()
    texts = []
    for p in f[field]:
        ok, decoded, _, _ = detector.detectAndDecode(cv2.imread(str(p)))
        texts.append(decoded if ok else None)
    f[c.get("output_field", "Barcode")] = texts
    return _done("Barcode", inputs, {"Output": f}, c, ctx)


def unavailable(name):
    def run(inputs, c, ctx):
        raise RuntimeError(
            f"{name} unavailable locally: no configured licensed model/runtime; network/model download is disabled"
        )

    return run


IMPLEMENTATIONS = {"Barcode": barcode, "ImageToText": image_to_text}
UNAVAILABLE = {
    "ImageTemplate": "native annotation/template regions are not locally implemented",
    "ImageRecognition": "licensed/native model runtime is not bundled",
    "KeyValuePairExtraction": "licensed/native model runtime is not bundled",
}
ANCHORS = {k: (("Input",), ("Output",)) for k in IMPLEMENTATIONS}
try:
    from alteryx2python.parser.tool_parsers.ml_tool_parser import make_ml_parser

    PARSERS = {k: make_ml_parser(k) for k in IMPLEMENTATIONS}
except ImportError:
    PARSERS = {}

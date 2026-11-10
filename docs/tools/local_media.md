# Local media and lightweight text adapters

`alteryx2python.tools.local_media` exports `IMPLEMENTATIONS`, `ANCHORS`, and `PARSERS` for JSONSchema, ImageOutput, ImageProcessing, ImageProfile, TextPreProcessing, and WordCloud. Every adapter requires an `Input` pandas anchor and records an `Output` node trace.

The adapters use `jsonschema` and Pillow when called, so missing optional dependencies fail clearly. Image paths must be readable by Pillow; ImageOutput requires `output_dir`. Text preprocessing deliberately supports only `lowercase`, `uppercase`, `strip`, and `tokens`. WordCloud returns deterministic word/count rows, not a model-generated graphic. These are local behaviors only and do not claim equivalence for model-backed image recognition, NER, sentiment, or OCR. PDFInput remains implemented by its existing adapter.

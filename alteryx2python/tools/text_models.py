"""Opt-in local NLP adapters; model-dependent tools never fabricate results."""

from __future__ import annotations
import json
import pickle
from pathlib import Path
from typing import Any
import pandas as pd
from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.parser.tool_parsers.common import ToolParserResult
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.unavailable import ToolUnavailableError


def _field(c: dict[str, Any], *names: str) -> str:
    for name in names:
        if c.get(name):
            return str(c[name])
    raise ValueError(f"configuration requires {names[0]}")


def _run(
    kind: str,
    frame: pd.DataFrame,
    out: pd.DataFrame,
    c: dict[str, Any],
    ctx: WorkflowContext,
):
    ctx.record_node(
        node_id=str(c.get("node_id", "unknown")),
        tool_type=kind,
        source_tool_id=c.get("source_tool_id"),
        inputs={"Input": frame},
        outputs={"Output": out},
        status="success",
        config={
            **c,
            "input_schema": snapshot_schema(frame),
            "output_schema": snapshot_schema(out),
        },
    )
    return {"Output": out}


def sentiment_tool(inputs, c, ctx):
    frame = inputs.get("Input")
    field = _field(c, "field")
    ensure_fields_exist(frame, [field])
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    except ImportError as exc:
        raise ToolUnavailableError(
            "Sentiment requires the configured vaderSentiment package"
        ) from exc
    if c.get("algorithm") and str(c["algorithm"]).lower() not in {
        "vader",
        "vader lexicon",
    }:
        raise ToolUnavailableError(
            "only the explicitly configured VADER sentiment algorithm is supported"
        )
    if c.get("language") and str(c["language"]).lower() not in {"english", "en", ""}:
        raise ToolUnavailableError("local VADER profile supports English only")
    if c.get("tokenize") not in (None, False, "", "false", "False"):
        raise ToolUnavailableError(
            "custom tokenization is not supported by the local VADER profile"
        )
    analyzer = SentimentIntensityAnalyzer()
    scores = [
        analyzer.polarity_scores(str(v) if pd.notna(v) else "") for v in frame[field]
    ]
    out = frame.copy()
    out["negative_sentiment"] = [s["neg"] for s in scores]
    out["neutral_sentiment"] = [s["neu"] for s in scores]
    out["positive_sentiment"] = [s["pos"] for s in scores]
    out["compound_sentiment"] = [s["compound"] for s in scores]
    if c.get("categorical"):
        out["sentiment"] = [
            "negative"
            if s["compound"] < float(c.get("negative_threshold", -0.05))
            else "positive"
            if s["compound"] > float(c.get("positive_threshold", 0.05))
            else "neutral"
            for s in scores
        ]
    return _run("Sentiment", frame, out, c, ctx)


def _spacy(c, ctx):
    model = c.get("model_path") or (ctx.runtime_config or {}).get("nlp_model")
    if hasattr(model, "__call__"):
        return model
    if not model:
        raise ToolUnavailableError(
            "NLP tool requires a local spaCy model_path or runtime_config.nlp_model"
        )
    try:
        import spacy

        return spacy.load(str(model))
    except (ImportError, OSError) as exc:
        raise ToolUnavailableError(
            f"Unable to load local spaCy model: {model}"
        ) from exc


def ner_tool(inputs, c, ctx):
    if c.get("custom_entities") or c.get("field_entities") or c.get("field_labels"):
        raise ToolUnavailableError(
            "custom NER training/configuration is not supported; provide a trained local spaCy model"
        )
    frame = inputs.get("Input")
    field = _field(c, "field", "Field")
    ensure_fields_exist(frame, [field])
    nlp = _spacy(c, ctx)
    docs = [nlp(str(v) if pd.notna(v) else "") for v in frame[field]]
    from spacy import displacy

    out = frame.copy()
    out["Entities"] = [
        json.dumps(
            [
                {
                    "entity": e.text,
                    "label": e.label_,
                    "character_index": e.start_char,
                    "word_index": e.start,
                    "entity_length": len(e.text),
                }
                for e in doc.ents
            ],
            ensure_ascii=False,
        )
        for doc in docs
    ]
    out["entity_diagram"] = [
        displacy.render(doc, style="ent", page=False) for doc in docs
    ]
    return _run("NamedEntityRecognition", frame, out, c, ctx)


def pos_tool(inputs, c, ctx):
    frame = inputs.get("Input")
    field = _field(c, "field", "Field")
    ensure_fields_exist(frame, [field])
    nlp = _spacy(c, ctx)
    out = frame.copy()
    out["PartOfSpeech"] = [
        json.dumps(
            [(t.text, t.pos_) for t in nlp(str(v) if pd.notna(v) else "")],
            ensure_ascii=False,
        )
        for v in frame[field]
    ]
    return _run("PartOfSpeechTagger", frame, out, c, ctx)


def topic_tool(inputs, c, ctx):
    frame = inputs.get("Input")
    field = _field(c, "field")
    ensure_fields_exist(frame, [field])
    try:
        from sklearn.decomposition import LatentDirichletAllocation
        from sklearn.feature_extraction.text import CountVectorizer
    except ImportError as exc:
        raise ToolUnavailableError("TopicModel requires scikit-learn") from exc
    n_topics = int(c.get("topics", 2) or 2)
    vector = CountVectorizer(
        min_df=c.get("dict_min_freq") or 1,
        max_df=c.get("dict_max_freq") or 1.0,
        max_features=c.get("dict_max_words") or None,
    )
    matrix = vector.fit_transform(frame[field].fillna("").astype(str))
    if matrix.shape[1] == 0:
        raise ValueError("TopicModel requires non-empty text")
    model = LatentDirichletAllocation(
        n_components=n_topics,
        random_state=int(c.get("random_state", 0)),
        doc_topic_prior=c.get("alpha") or None,
        topic_word_prior=c.get("eta") or None,
    ).fit(matrix)
    probabilities = model.transform(matrix)
    out = frame.copy()
    out["Topic"] = [int(i) + 1 for i in probabilities.argmax(axis=1)]
    for index in range(n_topics):
        out[f"Topic{index + 1}_Probability"] = probabilities[:, index]
    terms = vector.get_feature_names_out()
    report = pd.DataFrame(
        {
            "Term": terms,
            **{
                f"Topic{idx + 1}_Weight": model.components_[idx]
                for idx in range(n_topics)
            },
        }
    )
    artifact = c.get("model_path")
    if artifact:
        import joblib

        Path(artifact).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"vectorizer": vector, "model": model}, artifact)
    outputs = {
        "Output": out,
        "Report": report,
        "Model": pd.DataFrame(
            {"model_blob": [pickle.dumps({"vectorizer": vector, "model": model})]}
        ),
    }
    ctx.record_node(
        node_id=str(c.get("node_id", "unknown")),
        tool_type="TopicModel",
        source_tool_id=c.get("source_tool_id"),
        inputs={"Input": frame},
        outputs=outputs,
        status="success",
        config={
            **c,
            "input_schema": snapshot_schema(frame),
            "output_schema": snapshot_schema(out),
        },
    )
    return outputs


def classification_tool(inputs, c, ctx):
    frame = inputs.get("Input")
    field = _field(c, "field", "text_field")
    ensure_fields_exist(frame, [field])
    artifact = c.get("model_path")
    if not artifact:
        raise ToolUnavailableError(
            "TextClassification requires a local fitted model_path"
        )
    try:
        import joblib

        model = joblib.load(artifact)
    except (ImportError, OSError, ValueError) as exc:
        raise ToolUnavailableError(
            f"Unable to load classifier artifact: {artifact}"
        ) from exc
    try:
        predictions = model.predict(frame[field].fillna("").astype(str))
    except Exception as exc:
        raise ValueError(
            "configured classifier cannot predict the selected field"
        ) from exc
    out = frame.copy()
    out["Class"] = predictions
    return _run("TextClassification", frame, out, c, ctx)


def transformer_tool(kind, task):
    def run(inputs, c, ctx):
        frame = inputs.get("Data") if kind == "TextSummary" else inputs.get("Input")
        field = _field(c, "text_field", "field")
        ensure_fields_exist(frame, [field])
        model = c.get("model_path") or (ctx.runtime_config or {}).get(
            "transformers_model"
        )
        if not model:
            raise ToolUnavailableError(
                f"{kind} requires a local transformers model_path"
            )
        if not Path(str(model)).is_dir():
            raise ToolUnavailableError(
                f"{kind} requires an existing local model directory"
            )
        try:
            from transformers import pipeline
        except ImportError as exc:
            raise ToolUnavailableError("transformers is not installed") from exc
        try:
            pipe = pipeline(task, model=model, tokenizer=model, local_files_only=True)
        except Exception as exc:
            raise ToolUnavailableError(
                f"Unable to load local transformers model: {model}"
            ) from exc
        values = []
        for value in frame[field].fillna("").astype(str):
            kwargs = (
                {"candidate_labels": c.get("labels") or c.get("candidate_labels")}
                if task == "zero-shot-classification"
                else {}
            )
            if task == "zero-shot-classification" and not kwargs["candidate_labels"]:
                raise ValueError("ZeroShotTextClassification requires candidate_labels")
            values.append(pipe(value, **kwargs))
        out = frame.copy()
        out["Result"] = [json.dumps(v, ensure_ascii=False) for v in values]
        return _run(kind, frame, out, c, ctx)

    return run


_SPECS = {
    "Sentiment": sentiment_tool,
    "NamedEntityRecognition": ner_tool,
    "PartOfSpeechTagger": pos_tool,
    "TopicModel": topic_tool,
    "TextClassification": classification_tool,
    "ZeroShotTextClassification": transformer_tool(
        "ZeroShotTextClassification", "zero-shot-classification"
    ),
    "TextSummary": transformer_tool("TextSummary", "summarization"),
}
IMPLEMENTATIONS = {
    n: type(
        f"{n}Tool",
        (BaseTool,),
        {
            "tool_type": n,
            "input_anchors": ("Input",),
            "output_anchors": ("Output",),
            "execute": staticmethod(fn),
        },
    )
    for n, fn in _SPECS.items()
}
ANCHORS = {n: (("Input",), ("Output",)) for n in IMPLEMENTATIONS}
ANCHORS["TopicModel"] = (("Input",), ("Output", "Report", "Model"))
ANCHORS["TextSummary"] = (("Data",), ("Output",))
# Preserve the semantic ML parsers; raw XML dictionaries must not overwrite fields.
PARSERS = {}

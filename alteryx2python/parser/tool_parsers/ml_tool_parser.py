from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.catalog_parser import (
    _normalize_value,
    parse_catalog_config,
    text_list,
)
from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def _b(value: Any) -> bool:
    return str(value).strip().lower() in ("true", "1")


def _parse_autoML(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_variable": text(child(raw, "target_variable")),
        "problem_type": text(child(raw, "problem_type")),
        "objective_function": text(child(raw, "objective_function")),
        "model_families": text_list(raw, "model_families"),
        "max_pipelines_search": int(text(child(raw, "max_pipelines_search"), "0") or 0),
        "data_checks": _b(text(child(raw, "data_checks"))),
    }


def _parse_featuretypes(raw: dict[str, Any]) -> dict[str, Any]:
    set_types = []
    for item in as_list(child(raw, "set_types")):
        attrs = attributes(item)
        if attrs:
            set_types.append(attrs)
    return {"configured_types": _normalize_value(child(raw, "configured_types")), "set_types": set_types}


def _parse_buildfeatures(raw: dict[str, Any]) -> dict[str, Any]:
    relationships = child(raw, "relationships")
    primary_keys = [attributes(item) for item in as_list(child(raw, "primary_key"))]
    return {
        "target_table": text(child(raw, "target_table")),
        "primary_keys": primary_keys,
        "relationships": _normalize_value(relationships),
        "selected_primitives": text_list(raw, "selected_primitives"),
        "table_depth": int(text(child(raw, "table_depth"), "0") or 0),
    }


def _parse_sentiment(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "language": text(child(raw, "language")),
        "field": text(child(raw, "field")),
        "algorithm": text(child(raw, "algorithm")),
        "tokenize": _b(text(child(raw, "tokenize"))),
        "categorical": _b(text(child(raw, "categorical"))),
        "negative_threshold": float(text(child(raw, "negativeThreshold"), "0") or 0),
        "positive_threshold": float(text(child(raw, "positiveThreshold"), "0") or 0),
    }


def _parse_textpreprocessing(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "field": text(child(raw, "field")),
        "language": text(child(raw, "language")),
        "lemmatize": _b(text(child(raw, "lemmatize"))),
        "digits": _b(text(child(raw, "digits"))),
        "punctuation": _b(text(child(raw, "punctuation"))),
        "stopwords": _b(text(child(raw, "stopwords"))),
        "default_stopwords": _b(text(child(raw, "defaultStopwords"))),
        "added_stopwords": text(child(raw, "addedStopwords")),
    }


def _parse_ner(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "language": text(child(raw, "Language")),
        "field": text(child(raw, "Field")),
        "custom_entities": _b(text(child(raw, "CustomEntities"))),
        "field_entities": text(child(raw, "FieldEntities")),
        "field_labels": text(child(raw, "FieldLabels")),
        "case_sensitive": _b(text(child(raw, "CaseSensitive"))),
        "epochs": int(text(child(raw, "Epochs"), "0") or 0),
        "early_stopping": _b(text(child(raw, "EarlyStopping"))),
        "max_batch_size": int(text(child(raw, "MaxBatchSize"), "0") or 0),
    }


def _parse_topicmodel(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "field": text(child(raw, "field")),
        "topics": int(text(child(raw, "topics"), "0") or 0),
        "dict_min_freq": float(text(child(raw, "dictMinFreq"), "0") or 0),
        "dict_max_freq": float(text(child(raw, "dictMaxFreq"), "0") or 0),
        "dict_max_words": int(text(child(raw, "dictMaxWords"), "0") or 0),
        "alpha": float(text(child(raw, "alpha"), "0") or 0),
        "eta": float(text(child(raw, "eta"), "0") or 0),
        "report_output_mode": text(child(raw, "reportOutputMode")),
    }


def _parse_wordcloud(raw: dict[str, Any]) -> dict[str, Any]:
    background = child(raw, "backgroundColor")
    hsl = child(background, "hsl")
    return {
        "field": text(child(raw, "field")),
        "customize": _b(text(child(raw, "customize"))),
        "background_color": {
            "hex": text(child(background, "hex")),
            "hsl": _normalize_value(hsl),
        },
        "theme": text(child(raw, "theme")),
        "max_words": int(text(child(raw, "maxWords"), "0") or 0),
        "phrases": _b(text(child(raw, "phrases"))),
        "width": int(text(child(raw, "width"), "0") or 0),
        "height": int(text(child(raw, "height"), "0") or 0),
        "mask": _normalize_value(child(raw, "mask")),
    }


def _parse_zeroshot(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "text_field": text(child(raw, "TextField")),
        "label_field": text(child(raw, "LabelField")),
        "multi_checkbox": _b(text(child(raw, "MultiCheckbox"))),
    }


def _parse_barcode(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": text(child(raw, "Mode")),
        "image_field": text(child(raw, "ImageField")),
        "include_crop": _b(text(child(raw, "IncludeCrop"))),
        "include_bounded": _b(text(child(raw, "IncludeBounded"))),
        "barcode_type": text(child(raw, "BarcodeType")),
        "text_field": text(child(raw, "TextField")),
    }


def _steps(raw: dict[str, Any]) -> list[dict[str, Any]]:
    steps = []
    for item in as_list(child(raw, "Steps")):
        if isinstance(item, dict):
            steps.append(
                {
                    "name": text(child(item, "name")),
                    "config": _normalize_value(child(item, "config")),
                }
            )
    return steps


def _parse_imageprocessing(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "image_field": text(child(raw, "ImageField")),
        "steps": _steps(raw),
    }


def _parse_imageprofile(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "image_field": text(child(raw, "ImageField")),
        "profile_option": text(child(raw, "ProfileOption")),
        "profile_type": text(child(raw, "ProfileType")),
    }


def _parse_imagerecognition(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "image_field_training": text(child(raw, "ImageFieldTraining")),
        "label_field_training": text(child(raw, "LabelFieldTraining")),
        "image_field_validation": text(child(raw, "ImageFieldValidation")),
        "label_field_validation": text(child(raw, "LabelFieldValidation")),
        "epochs": int(text(child(raw, "Epochs"), "0") or 0),
        "model": text(child(raw, "Model")),
        "batch_size": int(text(child(raw, "BatchSize"), "0") or 0),
    }


def _parse_imagetotext(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "field_select": text(child(raw, "FieldSelect")),
        "language_select": text(child(raw, "LanguageSelect")),
    }


def _parse_imagetemplate(raw: dict[str, Any]) -> dict[str, Any]:
    file_path = child(raw, "FilePath")
    return {
        "file_path": attributes(file_path),
        "page_number": int(text(child(raw, "PageNumber"), "0") or 0),
        "bounds": text(child(raw, "Bounds")),
        "mode": text(child(raw, "Mode")),
        "blob_field": text(child(raw, "BlobField")),
    }


def _parse_kvextraction(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "image_field": text(child(raw, "ImageField")),
        "language": text(child(raw, "Language")),
        "key_field": text(child(raw, "KeyField")),
        "fuzzy": _b(text(child(raw, "Fuzzy"))),
    }


def _algorithm_configs(raw: dict[str, Any]) -> list[dict[str, Any]]:
    configs = []
    for item in as_list(child(raw, "algorithm_configs")):
        configs.append(
            {
                "algorithm_name": text(child(item, "algorithm_name")),
                "config": _normalize_value(child(item, "algorithm_config")),
            }
        )
    return configs


def _parse_cfml(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "algorithm_selection": text(child(raw, "algorithm_selection")),
        "algorithm_configs": _algorithm_configs(raw),
    }


def _parse_predict(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": text(child(raw, "schemaID")),
        "designer_version": text(child(raw, "DesignerVersion")),
    }


def _parse_fit(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_id": text(child(raw, "schemaID")),
        "classes": text_list(raw, "classes_"),
        "designer_version": text(child(raw, "DesignerVersion")),
        "model_id": text(child(raw, "modelID")),
        "fit_tool_id": text(child(raw, "fitToolID")),
    }


def _parse_modeling(raw: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "TargetVariable", "RadioSelection", "LastNumRowsReceived", "schemaID",
        "DatabaseMigrationFailure", "MemoryThresholdExceeded", "DesignerVersion",
        "PythonPath", "PythonArgs", "Port",
    )
    normalized = {key: _normalize_value(child(raw, key)) for key in keep}
    normalized["assisted_modeling_metadata"] = _normalize_value(child(raw, "AssistedModelingMetadata"))
    return normalized


def _parse_insights(raw: dict[str, Any]) -> dict[str, Any]:
    container = child(raw, "InsightFields")
    return {
        "insight_data": text(child(container, "InsightData")),
        "insight_description": text(child(container, "InsightDescription")),
        "description": _normalize_value(child(raw, "Description")),
    }


def _parse_pdfinput(raw: dict[str, Any]) -> dict[str, Any]:
    directory = child(raw, "PDFDirectory")
    return {
        "pdf_directory": {"text": text(directory), "attributes": attributes(directory)},
        "field": text(child(raw, "Field")),
        "mode_select": text(child(raw, "ModeSelect")),
        "file_option": text(child(raw, "FileOption")),
        "file_type": text(child(raw, "FileType")),
        "output_field_name": text(child(raw, "OutputFieldName")),
    }


_ML_PARSERS = {
    "AutoML": _parse_autoML,
    "FeatureTypes": _parse_featuretypes,
    "BuildFeatures": _parse_buildfeatures,
    "Sentiment": _parse_sentiment,
    "TextPreProcessing": _parse_textpreprocessing,
    "NamedEntityRecognition": _parse_ner,
    "TopicModel": _parse_topicmodel,
    "WordCloud": _parse_wordcloud,
    "ZeroShotTextClassification": _parse_zeroshot,
    "Barcode": _parse_barcode,
    "ImageProcessing": _parse_imageprocessing,
    "ImageProfile": _parse_imageprofile,
    "ImageRecognition": _parse_imagerecognition,
    "ImageToText": _parse_imagetotext,
    "ImageTemplate": _parse_imagetemplate,
    "KeyValuePairExtraction": _parse_kvextraction,
    "Classification": _parse_cfml,
    "Regression": _parse_cfml,
    "Transformation": _parse_cfml,
    "Predict": _parse_predict,
    "Fit": _parse_fit,
    "Modeling": _parse_modeling,
    "Insights": _parse_insights,
}


def parse_ml_tool_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """Semantic parser for Machine Learning / Text Mining / Computer Vision tools."""
    return ToolParserResult(normalized_config=parse_catalog_config(raw_config).normalized_config)


def make_ml_parser(tool_type: str) -> Any:
    specific = _ML_PARSERS.get(tool_type)

    def _parse(raw_config: dict[str, Any]) -> ToolParserResult:
        if specific is None:
            result = parse_catalog_config(raw_config)
            return ToolParserResult(normalized_config={"tool_type": tool_type, **result.normalized_config})
        return ToolParserResult(normalized_config={"tool_type": tool_type, **specific(raw_config)})

    return _parse

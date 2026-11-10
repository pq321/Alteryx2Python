from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.catalog_parser import _normalize_value
from alteryx2python.parser.tool_parsers.common import ToolParserResult, child, text


def parse_cass_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """CASS address standardization (AlteryxCASSGui.CASS.CASS -> AlteryxCASSEngine!AlteryxCASS)."""
    normalized: dict[str, Any] = {"tool_type": "CASS"}
    for key, value in raw_config.items():
        if key in ("raw", "normalized", "base_dir"):
            continue
        normalized[key] = _normalize_value(value)
    return ToolParserResult(normalized_config=normalized)


def parse_cassparse_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """CASS Parse (AlteryxCASSGui.CASSParse -> AlteryxCASSEngine!AlteryxCASSParse)."""
    return ToolParserResult(
        normalized_config={"tool_type": "CASSParse", **_normalize_value(raw_config)}
    )


def parse_zip9coder_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """ZIP9Coder (AlteryxCASSGui.ZIP9Coder -> AlteryxCASSEngine!AlteryxZIP9Coder)."""
    return ToolParserResult(
        normalized_config={"tool_type": "ZIP9Coder", **_normalize_value(raw_config)}
    )


def parse_geocoder_config(raw_config: dict[str, Any]) -> ToolParserResult:
    """Geocoder (PortfolioPluginsGui.Geocoder -> PortfolioPluginsEngine!AlteryxGeocoder)."""
    normalized: dict[str, Any] = {"tool_type": "Geocoder"}
    for key, value in raw_config.items():
        if key in ("raw", "normalized", "base_dir"):
            continue
        normalized[key] = _normalize_value(value)
    return ToolParserResult(normalized_config=normalized)

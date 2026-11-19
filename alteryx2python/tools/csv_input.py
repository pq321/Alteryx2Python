"""Read delimited files with the workflow's Windows code page."""

import codecs
from io import StringIO
import re

import pandas as pd


def detect_legacy_encoding(sample, decode_error, source):
    from charset_normalizer import from_bytes

    if len(sample) == 65536 and b'\n' in sample:
        sample = sample.rsplit(b'\n', 1)[0]
    if sample.isascii():
        sample = decode_error.object[max(0, decode_error.start - 1024):decode_error.start + 4096]
    matches = list(from_bytes(sample, cp_isolation=['cp932', 'gb18030', 'big5', 'cp949', 'cp1251', 'cp1252']))
    if matches:
        best = matches[0]
        ambiguous = any(str(match) != str(best) and match.chaos - best.chaos < 0.02
                        and best.coherence - match.coherence < 0.10 for match in matches[1:])
        if not ambiguous:
            return best.encoding
    raise ValueError(f"Cannot determine the CSV encoding for {source}. Set the Input Data CodePage explicitly.") from decode_error


def _parse_delimited_file(path, encoding, options, *, text_fields=False):
    options = {"keep_default_na": False, "na_values": [""], **options}
    if text_fields:
        options.setdefault("dtype", str)
    delimiter = options.get("delimiter", ",")
    if len(delimiter) != 1 or options.get("nrows") == 0:
        return pd.read_csv(path, encoding=encoding, **options)

    with open(path, encoding=encoding, newline="") as source:
        data = source.read()
    if '""' not in data:
        return pd.read_csv(StringIO(data, newline=""), **options)

    # Protect quoted empty fields before pandas strips the quotes. In Alteryx,
    # quoted empties are strings and unquoted empty fields are null.
    separators = re.escape(delimiter) + r"\r\n"
    fields = re.compile(rf'(^|[{separators}])("(?:[^"]|"")*"|[^{separators}]*)(?=[{separators}]|$)')
    token = "__a2p_quoted_empty__"
    while token in data:
        token += "_"
    protected = fields.sub(
        lambda field: field[1] + token if field[2] == '""' else field[0],
        data,
    )
    frame = pd.read_csv(StringIO(protected, newline=""), **options)
    if any(isinstance(column, str) and token in column for column in frame.columns):
        header_options = {**options, "nrows": 0}
        frame.columns = pd.read_csv(StringIO(data, newline=""), **header_options).columns
    return frame.replace(token, "")


def read_delimited_file(path, *, encoding=None, **options):
    if encoding == "cp932":
        return _parse_delimited_file(path, encoding, options, text_fields=True)
    if encoding not in {None, "utf-8", "utf-8-sig", "utf8"}:
        return _parse_delimited_file(path, encoding, options)

    with open(path, 'rb') as source:
        prefix = source.read(4)
    if prefix.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        return _parse_delimited_file(path, 'utf-32', options)
    if prefix.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return _parse_delimited_file(path, 'utf-16', options)
    try:
        return _parse_delimited_file(path, 'utf-8-sig', options)
    except UnicodeDecodeError as error:
        with open(path, 'rb') as source:
            detected = detect_legacy_encoding(source.read(65536), error, path)
    return _parse_delimited_file(path, detected, options, text_fields=True)

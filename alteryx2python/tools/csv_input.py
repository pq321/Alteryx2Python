"""Read delimited files with the workflow's Windows code page."""

import codecs
import csv
from io import StringIO
from itertools import dropwhile, islice
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


def input_field_names(labels, prefix):
    """Name blank headers and disambiguate duplicates in input order."""
    names = [
        str(label) if label is not None and str(label).strip() else f"{prefix}{index}"
        for index, label in enumerate(labels, 1)
    ]
    reserved = {name.casefold() for name in names}
    seen = set()
    for index, name in enumerate(names):
        key = name.casefold()
        if key not in seen:
            seen.add(key)
            continue
        single_digit = re.fullmatch(r"(.*?)(?<![0-9])([2-8])", name)
        if single_digit:
            stem, digit = single_digit.groups()
            candidates = (f"{stem}{n}" for n in range(int(digit) + 1, 10))
            replacement = next((value for value in candidates if value.casefold() not in reserved), None)
            suffix = f"{stem}9_"
        else:
            replacement = None
            suffix = name + ("_" if name[-1] in "0123456789" else "")
        if replacement is None:
            number = 2
            while f"{suffix}{number}".casefold() in reserved:
                number += 1
            replacement = f"{suffix}{number}"
        names[index] = replacement
        reserved.add(replacement.casefold())
        seen.add(replacement.casefold())
    return names


def _csv_headers(source, options):
    start = options.get("skiprows") or 0
    lines = dropwhile(lambda line: not line.strip(), islice(source, start, None))
    labels = next(csv.reader(lines, delimiter=options.get("delimiter", ",")), [])
    return input_field_names(labels, "Field_")


def _parse_delimited_file(path, encoding, options, *, text_fields=False):
    options = {"keep_default_na": False, "na_values": [""], **options}
    if text_fields:
        options.setdefault("dtype", str)
    delimiter = options.get("delimiter", ",")
    if len(delimiter) != 1:
        return pd.read_csv(path, encoding=encoding, **options)

    has_header = options.get("header", "infer") is not None
    if options.get("nrows") == 0:
        frame = pd.read_csv(path, encoding=encoding, **options)
        if has_header:
            with open(path, encoding=encoding, newline="") as source:
                names = _csv_headers(source, options)
            if len(names) == len(frame.columns):
                frame.columns = names
        return frame
    with open(path, encoding=encoding, newline="") as source:
        data = source.read()
    names = _csv_headers(StringIO(data, newline=""), options) if has_header else None
    if '""' not in data:
        frame = pd.read_csv(StringIO(data, newline=""), **options)
        if names is not None and len(names) == len(frame.columns):
            frame.columns = names
        return frame

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
    if names is not None and len(names) == len(frame.columns):
        frame.columns = names
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

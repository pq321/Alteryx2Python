"""Read delimited files with the workflow's Windows code page."""

import codecs

import pandas as pd


def _detect_legacy_encoding(path, decode_error):
    from charset_normalizer import from_bytes

    with open(path, 'rb') as source:
        sample = source.read(65536)
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
    raise ValueError(f"Cannot determine the CSV encoding for {path}. Set the Input Data CodePage explicitly.") from decode_error


def read_delimited_file(path, *, encoding=None, **options):
    if encoding == "cp932":
        return pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False, na_values=[""], **options)
    if encoding not in {None, "utf-8", "utf-8-sig", "utf8"}:
        return pd.read_csv(path, encoding=encoding, **options)

    with open(path, 'rb') as source:
        prefix = source.read(4)
    if prefix.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
        return pd.read_csv(path, encoding='utf-32', **options)
    if prefix.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return pd.read_csv(path, encoding='utf-16', **options)
    try:
        return pd.read_csv(path, encoding='utf-8-sig', **options)
    except UnicodeDecodeError as error:
        detected = _detect_legacy_encoding(path, error)
    return pd.read_csv(path, encoding=detected, dtype=str, keep_default_na=False, na_values=[""], **options)

"""Shared local YXDB decoding for Input Data and native parity evidence."""

from pathlib import Path
from decimal import Decimal
from xml.etree import ElementTree as ET

import pandas as pd


def read_yxdb_frame(path: Path, *, limit: int | None = None) -> pd.DataFrame:
    schema, rows = read_yxdb_records(path, limit=limit, include_field_metadata=True)
    frame = pd.DataFrame(rows, columns=[field["name"] for field in schema], dtype=object)
    frame.attrs["alteryx_schema"] = schema
    return frame


def read_yxdb_records(
    path: Path, *, limit: int | None = None, include_field_metadata: bool = False,
) -> tuple[list[dict], list[list]]:
    try:
        from yxdb.yxdb_reader import YxdbReader
    except ImportError as exc:
        raise NotImplementedError("YXDB input requires the optional parity dependencies") from exc

    class TimeAwareReader(YxdbReader):
        def _get_fields(self):
            super()._get_fields()
            # yxdb 1.1.1 lacks Time. The on-disk field matches a fixed
            # string with a null byte. Keep the original XML metadata.
            for field in self._fields:
                if field.data_type == "Time":
                    field.data_type = "String"
                    field.size = field.size or 8
                elif field.data_type == "FixedDecimal":
                    field.data_type = "String"

    with path.open("rb") as stream:
        try:
            reader = TimeAwareReader(stream=stream)
        except Exception as exc:
            # The library raises a plain Exception for invalid or unsupported headers.
            if type(exc) is not Exception:
                raise
            raise ValueError(f"{path} is not a valid YXDB for the installed decoder: {exc}") from exc
        fields = reader.list_fields()
        meta = ET.fromstring(reader.meta_info_str)
        record_info = meta if meta.tag == "RecordInfo" else meta.find("./RecordInfo")
        if record_info is None:
            raise ValueError("YXDB has no RecordInfo")
        keys = ("name", "type", "size", "scale")
        if include_field_metadata:
            keys += ("source", "description")
        schema = [{key: field.get(key) for key in keys} for field in record_info.iter("Field")]
        if [field["name"] for field in schema] != [field.name for field in fields]:
            raise ValueError("YXDB RecordInfo does not match decoded fields")
        decimal_columns = [index for index, field in enumerate(schema) if field["type"] == "FixedDecimal"]
        rows = []
        while (limit is None or len(rows) < limit) and reader.next():
            values = [reader.read_index(index) for index in range(len(fields))]
            for index in decimal_columns:
                if values[index] is not None:
                    values[index] = Decimal(values[index])
            rows.append(values)
    return schema, rows

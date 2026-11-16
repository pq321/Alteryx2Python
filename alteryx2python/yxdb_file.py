"""Shared local YXDB decoding for Input Data and native parity evidence."""

from pathlib import Path
from xml.etree import ElementTree as ET


def read_yxdb_records(path: Path, *, limit: int | None = None) -> tuple[list[dict], list[list]]:
    try:
        from yxdb.yxdb_reader import YxdbReader
    except ImportError as exc:
        raise NotImplementedError("YXDB input requires the optional parity dependencies") from exc

    with path.open("rb") as stream:
        reader = YxdbReader(stream=stream)
        fields = reader.list_fields()
        meta = ET.fromstring(reader.meta_info_str)
        record_info = meta if meta.tag == "RecordInfo" else meta.find("./RecordInfo")
        if record_info is None:
            raise ValueError("YXDB has no RecordInfo")
        schema = [
            {key: field.get(key) for key in ("name", "type", "size", "scale")}
            for field in record_info.iter("Field")
        ]
        if [field["name"] for field in schema] != [field.name for field in fields]:
            raise ValueError("YXDB RecordInfo does not match decoded fields")
        rows = []
        while (limit is None or len(rows) < limit) and reader.next():
            rows.append([reader.read_index(index) for index in range(len(fields))])
    return schema, rows

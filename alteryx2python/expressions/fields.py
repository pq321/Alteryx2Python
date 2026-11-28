"""Resolve Alteryx field references without changing the output schema."""


def field_value(record, name):
    try:
        return record[name]
    except KeyError:
        folded = name.casefold()
        matches = [key for key in record.keys() if isinstance(key, str) and key.casefold() == folded]
        if len(matches) == 1:
            return record[matches[0]]
        raise

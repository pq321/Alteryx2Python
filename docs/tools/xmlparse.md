# XMLParse Tool Semantics

Maturity: `L2_BASIC_IMPLEMENTATION`

Supported baseline behavior:

- Reads XML text from the configured `xml_field`.
- Preserves the input row fields in each output row.
- Parses the root element when `parse_root` is true.
- Parses every matching descendant/root element when `xml_element` is set.
- When `xml_element` is blank and `parse_root` is false, targets repeated parent elements when possible, then leaf descendants as a fallback.
- Emits a column named after the parsed element containing its text value.
- Emits XML attributes as columns.
- Emits direct child text values when `child_values` is true.
- Emits `{element}_OuterXML` when `outer_xml` is true.
- Honors `ignore_errors` by passing malformed XML rows through unchanged; otherwise malformed XML raises `ValueError`.

Known gaps:

- Namespace prefixes are normalized to local names.
- Automatic target selection is a deterministic approximation of Alteryx's blank-element behavior.
- Mixed-content XML, repeated sibling columns with the same tag, and schema typing are not yet fully modeled.

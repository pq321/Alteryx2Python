# DynamicRename Tool

Status: `L2_BASIC_IMPLEMENTATION`

`Targets` supplies the data, and the right-hand `Source` supplies field names
in the right-input modes. `Output` emits the renamed data.

The installed Designer sample covers Formula using `_CurrentField_`, First
Row, Add Prefix, Remove Suffix, Right Input Metadata, and both positional and
mapped Right Input Rows. The implementation applies the saved field selections
and raises an error on duplicate output names. Right Input Metadata type and
size changes still require a runtime adapter.

# DataCleansing

Implements the Alteryx `Cleanse.yxmc` macro as a first-class runtime tool.

Supported anchors:

- Input: `Input2`
- Output: `Output26`

Supported options map directly from the macro questions:

- `Check Box (135)`: remove rows where all selected fields are null or blank
- `Check Box (136)`: remove selected columns where all values are null or blank
- `Check Box (84)`: replace string nulls with blanks
- `Check Box (117)`: replace numeric nulls with zero
- `Check Box (15)`: trim leading and trailing whitespace
- `Check Box (109)`: collapse tabs, line breaks, and duplicate whitespace
- `Check Box (122)`: remove all whitespace
- `Check Box (53)`: remove letters
- `Check Box (58)`: remove numbers
- `Check Box (70)`: remove punctuation
- `Check Box (77)` and `Drop Down (81)`: modify case (`upper`, `lower`, or `title`)

The implementation preserves unselected fields and emits trace/schema evidence through the canonical runtime.

# Blank headers and Data Cleansing

Designer 2025.1.2.165 ran the same synthetic workflow in Classic and AMP with
Engine Compatibility Mode off. The compared checkpoints include 13 CSV inputs,
7 Excel inputs, 21 Data Cleansing outputs, and one Text Input control. The
reports retain Designer's field metadata and compare field names, order, and
cell values against generated Python Phase 1 and Phase 2. The AMP comparison also
checks the complete record counts when row order differs.

| Engine | Exact records and order | Match after reorder | Data mismatch |
| --- | ---: | ---: | ---: |
| [Classic](classic/comparison.json) | 42 | 0 | 0 |
| [AMP](amp/comparison.json) | 39 | 3 | 0 |

AMP output order changed at Tools 21, 37, and 55. These cases enable Remove
Null Rows. Each surviving record and its multiplicity matched. The standalone
Phase 2 script ran successfully. Its synthetic CSV sinks collapse empty strings
and nulls into empty fields at six anchors per engine. The checkpoint reports
retain both original values and show these CSV serialization differences.

To replay an engine, copy that engine's `.yxmd` and the `input*` files to a fresh
directory and run the workflow in Designer. Classic YXDB captures are in
`classic/designer-yxdb`. The decoded AMP tables are in `amp/classic-export`.
The AMP report records a hash for the original e2 probe and its Classic export.

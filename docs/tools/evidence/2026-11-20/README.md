# Common tool configuration evidence

[The coverage CSV](common-tools-coverage.csv) tracks 811 cases across the 95
selected Designer tools and the related workflow features. Evidence paths are
relative to the repository root. Designer sample paths are relative to the
installed `Samples/en` directory. A sample path identifies a candidate for
testing.

- [Core tool comparisons](designer-vs-python.json) cover 37 native outputs.
  Thirty-six match Python for column names and ordered values. The random
  Sample case selects different record IDs.
- [Dynamic Input comparisons](dynamic-input/dynamic-input-regression.json)
  cover seven Designer Classic outputs for CSV file name and XLSX worksheet
  selector actions. All seven match both Python phases and the independent
  Phase Two outputs. A [53-test regression receipt](dynamic-input/pytest-regression.xml)
  records the related Python checks.
- [The installed sample inventory](designer-sample-inventory.json) catalogs
  candidate workflows for 94 of the 95 selected tools.
- [Blank headers and Data Cleansing](blank-headers-data-cleansing/README.md)
  compare 42 synthetic output anchors in Classic and another 42 in AMP.

The bundle includes synthetic probes and portable workflow copies. The workflow
copies use relative input and replay output paths. Recorded workflow hashes
refer to the files used at capture time. Probe and standalone CSV hashes refer
to the bundled files. The comparisons certify the named sample outputs and
engine settings. Native field metadata is retained where it was captured.

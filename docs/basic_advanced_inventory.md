# Basic And Advanced Sample Inventory

This inventory uses the parser/runtime canonical `NodeIR.tool_type` names.

## 04 Basic

| Workflow | Nodes | Edges | Tool types | Dependencies |
| --- | ---: | ---: | --- | --- |
| `01 Combine 2 Spreadsheets Containing Customer Data.yxmd` | 12 | 6 | `DbFileInput`, `DbFileOutput`, `Join`, `Select`, `Sort`, `TextBox` | `Excel.CustomerLocationData.xlsx`, `Excel.CustomerResponderData.xlsx`, `%temp%Excel.CustomerProfileOutput.csv` |
| `01 Normalize_a_string_field.yxmd` | 42 | 18 | `BrowseV2`, `DbFileInput`, `Formula`, `RegEx`, `TextBox`, `TextToColumns`, `ToolContainer` | `Clothing_Search.csv` |
| `02 Learn_frequently-used_tools.yxmd` | 25 | 15 | `BrowseV2`, `DbFileInput`, `Filter`, `Formula`, `Join`, `RecordID`, `Sample`, `Select`, `Sort`, `Summarize`, `TextBox`, `ToolContainer`, `Union`, `Unique` | `CSVGeocode_example.csv` |
| `02 Normalize_phone_numbers.yxmd` | 16 | 8 | `BrowseV2`, `DbFileInput`, `Filter`, `Formula`, `RegEx`, `Select`, `TextBox`, `ToolContainer` | `REGEX_TEST.yxdb` |
| `03 Normalize_an_Unstructured_TXT_File.yxmd` | 25 | 16 | `BrowseV2`, `CrossTab`, `DbFileInput`, `Filter`, `Formula`, `Join`, `MultiRowFormula`, `RegEx`, `Select`, `Summarize`, `TextBox`, `TextToColumns`, `ToolContainer`, `Transpose` | `SecurityLog.txt` |
| `05 Analyze a sales pipeline.yxmd` | 20 | 14 | `BrowseV2`, `CrossTab`, `DbFileInput`, `DbFileOutput`, `Filter`, `Formula`, `Join`, `TextBox`, `Transpose` | `SalesPipeline.*.yxdb`, `%temp%SalesPipeline_Output.csv` |
| `05 Infer_ZIP_codes_from_latitude_and_longitude.yxmd` | 8 | 2 | `BrowseV2`, `DbFileInput`, `DynamicInput`, `TextBox`, `ToolContainer` | `DynamIn.mdb`, `DynamInZips.yxdb` |
| `06 Calculate_a_trend_and_sort_data.yxmd` | 12 | 6 | `BrowseV2`, `DbFileInput`, `Filter`, `Formula`, `Sample`, `Select`, `Sort`, `TextBox`, `ToolContainer` | `CountyDensity.yxdb` |
| `08 Create_an_XML_File.yxmd` | 21 | 13 | `DbFileOutput`, `Formula`, `Join`, `Summarize`, `TextBox`, `TextInput`, `ToolContainer`, `Union` | `%temp%CountiesByStates.xml` |
| `09 Read_a_FLAT_File.yxmd` | 8 | 2 | `BrowseV2`, `DbFileInput`, `Filter`, `TextBox`, `ToolContainer` | `out.flat` |

## 05 Advanced

| Workflow | Nodes | Edges | Tool types | Dependencies |
| --- | ---: | ---: | --- | --- |
| `01 Create_service_boundaries.yxmd` | 28 | 23 | `BrowseV2`, `CreatePoints`, `DbFileInput`, `Distance`, `Formula`, `Join`, `Select`, `SpatialMatch`, `Summarize`, `TextBox`, `ToolContainer`, `TradeArea`, `Union` | DBF/TAB spatial sample data |
| `02 Map a trade area around a store.yxmd` | 20 | 14 | `BrowseV2`, `CreatePoints`, `DbFileInput`, `DbFileOutput`, `Formula`, `Select`, `SpatialInfo`, `SpatialMatch`, `SpatialProcess`, `TextBox`, `TradeArea` | DBF/YXDB spatial sample data |
| `03 Convert stock info from XML to a spreadsheet.yxmd` | 21 | 16 | `CrossTab`, `DbFileInput`, `DbFileOutput`, `DynamicRename`, `DynamicSelect`, `Formula`, `RecordID`, `RegEx`, `Select`, `TextBox`, `Transpose`, `Union`, `XMLParse` | XML input, Excel output |
| `03 Find_the_closest_stores_to_customers.yxmd` | 13 | 7 | `BrowseV2`, `CreatePoints`, `DbFileInput`, `FindNearest`, `Select`, `Summarize`, `TextBox`, `ToolContainer` | DBF/TAB spatial sample data |
| `03 Map_trade_areas_1.yxmd` | 26 | 19 | `CreatePoints`, `DbFileInput`, `Filter`, `FindNearest`, `Formula`, `Join`, `PolyBuild`, `PortfolioComposerRender`, `RecordID`, `ReportMap`, `Sort`, `Summarize`, `TextBox`, `Tile`, `ToolContainer` | DBF/TAB spatial sample data |
| `03 Measure_the_quality_of_data.yxmd` | 18 | 11 | `AppendFields`, `BrowseV2`, `DbFileInput`, `Formula`, `Message`, `Sort`, `Summarize`, `TextBox`, `ToolContainer`, `Transpose` | `ParsedData.csv` |
| `04 Create_a_report_with_a_thematic_map.yxmd` | 24 | 18 | `AppendFields`, `CreatePoints`, `DbFileInput`, `Formula`, `PortfolioComposerLayout`, `PortfolioComposerRender`, `PortfolioComposerText`, `ReportMap`, `SpatialMatch`, `Summarize`, `TextBox`, `ToolContainer`, `UNKNOWN` | DBF/GEO spatial sample data |
| `04 Find_all_customers_within_30_miles_of_a_store.yxmd` | 16 | 11 | `BrowseV2`, `CreatePoints`, `DbFileInput`, `Distance`, `Join`, `Select`, `Sort`, `SpatialMatch`, `Summarize`, `TextBox`, `ToolContainer`, `TradeArea` | DBF/TAB spatial sample data |
| `04 Map_trade_areas_2.yxmd` | 14 | 7 | `CreatePoints`, `DbFileInput`, `PortfolioComposerRender`, `PortfolioComposerText`, `ReportMap`, `Select`, `TextBox`, `ToolContainer`, `TradeArea` | `ClubLocCO.tab` |
| `04 Normalize_an_Unstructured_XML_File.yxmd` | 10 | 4 | `BrowseV2`, `DbFileInput`, `Select`, `TextBox`, `ToolContainer`, `XMLParse` | `Donuts.xml` |
| `04 Report opioid epidemic trends by year.yxmd` | 15 | 9 | `BrowseV2`, `CrossTab`, `DbFileInput`, `Filter`, `Insights`, `MultiFieldFormula`, `PlotlyCharting`, `PortfolioComposerRender`, `Summarize`, `TextBox` | opioid trends CSV |
| `05 Download_and_parse_web_data.yxmd` | 53 | 39 | `AutoField`, `BrowseV2`, `CreatePoints`, `DateTime`, `Download`, `DynamicRename`, `Formula`, `Join`, `Message`, `MultiFieldFormula`, `PortfolioComposerLayout`, `PortfolioComposerRender`, `PortfolioComposerTable`, `PortfolioComposerText`, `ReportMap`, `Sample`, `Select`, `Sort`, `TextBox`, `TextInput`, `TextToColumns`, `ToolContainer`, `UNKNOWN` | web download |
| `05 Overlay_a_zip_code_map_1.yxmd` | 10 | 5 | `BrowseV2`, `DbFileInput`, `ReportMap`, `SpatialMatch`, `TextBox`, `ToolContainer` | TAB/YXDB spatial sample data |
| `06 Analyze and report on traffic fatalities.yxmd` | 38 | 33 | `AutoField`, `BrowseV2`, `CreatePoints`, `DbFileInput`, `Filter`, `Formula`, `Join`, `PlotlyCharting`, `PortfolioComposerRender`, `ReportMap`, `Select`, `Summarize`, `TextBox` | CSV/YXDB sample data |
| `06 Calculate_a_trend_and_sort_data.yxmd` | 12 | 6 | `BrowseV2`, `DbFileInput`, `Filter`, `Formula`, `Sample`, `Select`, `Sort`, `TextBox`, `ToolContainer` | `CountyDensity.yxdb` |
| `06 Create_a_report_with_a_chart_and_a_table.yxmd` | 17 | 13 | `AlteryxReportChartGui`, `DbFileInput`, `JoinMultiple`, `PortfolioComposerImage`, `PortfolioComposerLayout`, `PortfolioComposerRender`, `PortfolioComposerTable`, `PortfolioComposerText`, `Sort`, `TextBox`, `ToolContainer` | report YXDB sample data |
| `06 Overlay_a_zip_code_map_2.yxmd` | 12 | 6 | `BrowseV2`, `DbFileInput`, `Formula`, `Join`, `SpatialInfo`, `Summarize`, `TextBox`, `ToolContainer` | CSV/YXDB spatial sample data |
| `07 Create_summary_tables_for_a_report.yxmd` | 23 | 21 | `CrossTab`, `DbFileInput`, `JoinMultiple`, `PortfolioComposerImage`, `PortfolioComposerLayout`, `PortfolioComposerRender`, `PortfolioComposerTable`, `PortfolioComposerText`, `Select`, `Summarize`, `TextBox`, `ToolContainer` | DBF report sample data |
| `07 Measure_the_Vverlap_of_Ad_Coverage.yxmd` | 19 | 13 | `BrowseV2`, `CreatePoints`, `DbFileInput`, `Formula`, `Select`, `SpatialInfo`, `SpatialMatch`, `SpatialProcess`, `TextBox`, `ToolContainer`, `TradeArea` | DBF/YXDB spatial sample data |
| `07 Smooth_spatial_objects_on_a_map.yxmd` | 28 | 21 | `Buffer`, `CreatePoints`, `DbFileInput`, `Generalize`, `PortfolioComposerRender`, `PortfolioComposerText`, `ReportMap`, `Smooth`, `TextBox`, `TextInput`, `ToolContainer`, `TradeArea` | `NJOC.yxdb` |
| `10 Create_tables_from_unicode_data.yxmd` | 15 | 11 | `AlteryxReportChartGui`, `Join`, `JoinMultiple`, `PortfolioComposerImage`, `PortfolioComposerLayout`, `PortfolioComposerRender`, `PortfolioComposerTable`, `PortfolioComposerText`, `TextBox`, `TextInput`, `ToolContainer` | embedded TextInput |
| `11 Create_a_report_layout.yxmd` | 36 | 29 | `DbFileInput`, `JoinMultiple`, `PlotlyCharting`, `PortfolioComposerImage`, `PortfolioComposerLayout`, `PortfolioComposerRender`, `PortfolioComposerTable`, `PortfolioComposerText`, `ReportMap`, `Summarize`, `TextBox`, `ToolContainer`, `UNKNOWN`, `VisualLayout` | report sample YXDB |

## 05 Advanced Macro Subdirectory

| Workflow | Nodes | Edges | Tool types | Dependencies |
| --- | ---: | ---: | --- | --- |
| `02 Build_a_Macro/03 Assign_supply_to_demand.yxmd` | 25 | 16 | `AppendFields`, `BrowseV2`, `DbFileInput`, `Distance`, `RecordID`, `Select`, `Sort`, `Summarize`, `Test`, `TextBox`, `ToolContainer`, `UNKNOWN` | sample demand/supply YXDB |
| `02 Build_a_Macro/04 Map_customers_by_store.yxmd` | 19 | 12 | `CreatePoints`, `DbFileInput`, `FindNearest`, `Join`, `PortfolioComposerRender`, `PortfolioComposerText`, `RecordID`, `ReportMap`, `TextBox`, `ToolContainer`, `UNKNOWN` | DBF/TAB spatial sample data |
| `02 Build_a_Macro/05 Create_a_heat_map_for_purchase_data.yxmd` | 12 | 6 | `CreatePoints`, `DbFileInput`, `PortfolioComposerRender`, `PortfolioComposerText`, `ReportMap`, `TextBox`, `ToolContainer`, `UNKNOWN` | DBF/TAB spatial sample data |
| `02 Build_a_Macro/06 Identify_tools_and_macros_used_in_a_workflow.yxmd` | 8 | 2 | `BrowseV2`, `Directory`, `TextBox`, `ToolContainer`, `UNKNOWN` | none |
| `02 Build_a_Macro/08 Optimize_location_by_minimizing_distance.yxmd` | 11 | 5 | `BrowseV2`, `DbFileInput`, `TextBox`, `ToolContainer`, `UNKNOWN` | location YXDB sample data |
| `02 Build_a_Macro/09 Optimize_location_with_a_gravity_model.yxmd` | 12 | 6 | `BrowseV2`, `DbFileInput`, `TextBox`, `ToolContainer`, `UNKNOWN` | location YXDB sample data |
| `02 Build_a_Macro/10 Merge_to_a_master_file_with_fuzzy_matching.yxmd` | 104 | 101 | `BrowseV2`, `DbFileInput`, `Filter`, `Formula`, `Join`, `Select`, `Sort`, `Summarize`, `TextBox`, `ToolContainer`, `UNKNOWN`, `Union`, `Unique` | customer/master YXDB sample data |

## Certification Priority

Completed:

- `04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd`: certified against an Alteryx CSV oracle.

Recommended next candidates:

- `04 Basic/02 Learn_frequently-used_tools.yxmd`: needs `Sample`, `Unique`, and `Summarize`.
- `04 Basic/06 Calculate_a_trend_and_sort_data.yxmd`: needs `Sample` and YXDB input support.
- `05 Advanced/03 Measure_the_quality_of_data.yxmd`: needs `AppendFields`, `Message`, `Summarize`, and stronger data-quality semantics.

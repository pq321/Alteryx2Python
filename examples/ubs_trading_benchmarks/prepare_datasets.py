"""Build deterministic, synthetic trading fixtures and their Designer workflows."""

from argparse import ArgumentParser
from pathlib import Path
import csv
import json
import random
from xml.etree import ElementTree as ET

import pandas as pd

from alteryx2python.workflow_generator import WorkflowBuilder, escape


ROOT = Path(__file__).resolve().parent
SCENARIOS = (
    "01_equities_fx_recon",
    "02_trade_surveillance_app",
    "03_multiregion_position_risk",
    "04_mifid_ii_regulatory",
)
MARKETS = [
    ("US0378331005", "AAPL", "USD", "Equities", 158.40, 0.88),
    ("CH0038863350", "NESN", "CHF", "Equities", 85.20, 1.0),
    ("DE0007164600", "SAP", "EUR", "Equities", 165.15, 0.94),
    ("KYG875721634", "腾讯控股", "HKD", "Equities", 275.35, 0.112),
    ("JP3633400001", "トヨタ自動車", "JPY", "Equities", 2730, 0.0058),
    ("FX_USDCHF", "USDCHF", "CHF", "FX", 0.88, 1.0),
]


def input_table(builder, path, y, *, encoding=65001, sheet=None):
    file = escape(f"{path}|||`{sheet}$`" if sheet else path)
    xml = f'<File FileFormat="{25 if sheet else 0}">{file}</File><Passwords/>'
    options = (
        "<FirstRowData>False</FirstRowData>"
        if sheet else
        f"<HeaderRow>True</HeaderRow><CodePage>{encoding}</CodePage><Delimeter>,</Delimeter>"
        "<IgnoreQuotes>DoubleQuotes</IgnoreQuotes><FieldLen>254</FieldLen>"
    )
    return builder._node("DbFileInput", xml + f"<FormatSpecificOptions>{options}</FormatSpecificOptions>", (54, y))


def workbook_output(builder, source, filename, sheet, y):
    sink = builder._node(
        "DbFileOutput",
        f'<File FileFormat="25">{escape(filename)}|||{escape(sheet)}</File>'
        "<Passwords/><FormatSpecificOptions><OutputOption>Overwrite</OutputOption></FormatSpecificOptions>"
        '<MultiFile value="False"/>',
        (1000, y),
    )
    builder.connect(source, sink)


def html_report(builder, source, filename, y, fields):
    columns = "".join(f'<Field name="{escape(name)}" selected="True"/>' for name in fields)
    table = builder._node(
        "PortfolioComposerTable",
        f'<TableMode>Basic</TableMode><ShowHeader value="True"/><TableFields>{columns}</TableFields>',
        (850, y),
    )
    render = builder._node(
        "PortfolioComposerRender",
        f'<TempFileType/><BatchMode value="False"/><OutputFile>{filename}</OutputFile><DataField>Table</DataField>'
        '<Separator>Continuous</Separator><ShowHeader value="False"/><ShowFooter value="False"/>'
        '<PaperType Width="612" Height="792" Left="36" Right="36" Top="36" Bottom="36"/>',
        (990, y),
    )
    builder.connect(source, table)
    builder.connect(table, render)


def cast_numbers(builder, source, fields, y):
    select = builder.add_select(
        [(name, "True") for name in fields],
        position=(200, y),
        field_types={name: ("Double", None) for name in fields},
    )
    builder.connect(source, select)
    return select


def join(builder, left, right, key, position):
    node = builder.add_join(key, key, position)
    xml = ET.fromstring(builder.nodes_xml[-1])
    fields = xml.find("./Properties/Configuration/SelectConfiguration/Configuration/SelectFields")
    ET.SubElement(fields, "SelectField", field=f"Right_{key}", selected="False", input="Right_")
    builder.nodes_xml[-1] = ET.tostring(xml, encoding="unicode")
    builder.connect(left, node, target_anchor="Left")
    builder.connect(right, node, target_anchor="Right")
    return node


def write_workflow(builder, path, *, amp=False, app=None):
    root = ET.fromstring(builder.render())
    ET.SubElement(root.find("Properties"), "RunWithE2", value=str(amp))
    incoming = {}
    for edge in root.findall("./Connections/Connection"):
        destination = edge.find("Destination")
        key = destination.get("ToolID"), destination.get("Connection")
        incoming.setdefault(key, []).append(edge)
    for edges in incoming.values():
        if len(edges) > 1:
            for index, edge in enumerate(edges, 1):
                edge.set("name", f"#{index}")
    if app:
        app(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def equities(folder):
    rng = random.Random(28)
    rows = []
    for index in range(1800):
        isin, ticker, currency, asset, price, _ = MARKETS[index % len(MARKETS)]
        quantity = rng.randint(5, 1500) * (-1 if index % 89 == 0 else 1)
        rows.append((f"T{index:05}", f"O{index // 2:05}", "2026-11-27",
                     "FX_SPOT" if asset == "FX" else ("EMEA_EQ", "APAC_EQ")[index % 2],
                     f"Trader {index % 13}", isin, ticker, "Sell" if index % 3 == 0 else "Buy",
                     quantity, round(price * rng.uniform(.98, 1.02), 4), currency,
                     f"Broker {index % 5}", "" if index % 3 else "amended"))
    oms = pd.DataFrame(rows, columns=[
        "TradeID", "OrderID", "TradeDate", "Desk", "Trader", "ISIN", "Ticker", "Side",
        "Quantity", "ExecPrice", "TradeCcy", "Counterparty", "Note",
    ])
    oms.to_csv(folder / "oms_executions.csv", index=False)
    clearing = oms.loc[oms.index.difference(range(5)), ["TradeID"]].copy()
    clearing["BrokerAmount"] = (oms.Quantity * oms.ExecPrice).round(2)
    clearing.loc[5:19, "BrokerAmount"] += 0.03
    clearing = pd.concat([clearing, pd.DataFrame({"TradeID": ["BROKER_ONLY"], "BrokerAmount": [150.0]})])
    currencies = {item[2]: item[5] for item in MARKETS}
    with pd.ExcelWriter(folder / "prime_broker_clearing.xlsx") as book:
        clearing.to_excel(book, sheet_name="Clears", index=False)
        pd.DataFrame({"TradeCcy": list(currencies), "CommissionBps": [3, 2, 4, 8, 5][:len(currencies)]}).to_excel(
            book, sheet_name="FeeSchedule", index=False,
        )
    pd.DataFrame(currencies.items(), columns=["TradeCcy", "FX_to_CHF"]).to_csv(folder / "fx_rates_chf.csv", index=False)
    pd.DataFrame([(i, a, p) for i, _, _, a, p, _ in MARKETS],
                 columns=["ISIN", "AssetClass", "ReferencePrice"]).to_csv(folder / "security_master.csv", index=False)
    graph = WorkflowBuilder()
    data = cast_numbers(graph, input_table(graph, "oms_executions.csv", 80), ["Quantity", "ExecPrice"], 80)
    fx = cast_numbers(graph, input_table(graph, "fx_rates_chf.csv", 220), ["FX_to_CHF"], 220)
    security = cast_numbers(graph, input_table(graph, "security_master.csv", 360), ["ReferencePrice"], 360)
    fees = input_table(graph, "prime_broker_clearing.xlsx", 500, sheet="FeeSchedule")
    clears = input_table(graph, "prime_broker_clearing.xlsx", 640, sheet="Clears")
    fx_join = join(graph, data, fx, "TradeCcy", (350, 150))
    security_join = join(graph, fx_join, security, "ISIN", (440, 190))
    graph.connections[-2] = (fx_join, "Join", security_join, "Left")
    fee_join = join(graph, security_join, fees, "TradeCcy", (540, 270))
    graph.connections[-2] = (security_join, "Join", fee_join, "Left")
    pnl = graph.add_formula([
        ("Gross_Notional_CHF", "Double", "8", "[Quantity] * [ExecPrice] * [FX_to_CHF]"),
        ("Commission_CHF", "Double", "8", "Abs([Gross_Notional_CHF]) * [CommissionBps] / 10000"),
        ("Net_Settlement_CHF", "Double", "8", "[Gross_Notional_CHF] - [Commission_CHF]"),
        ("Realized_PnL_CHF", "Double", "8", 'IF [Side]="Buy" THEN [Quantity] * ([ReferencePrice]-[ExecPrice]) * [FX_to_CHF] - [Commission_CHF] ELSE [Quantity] * ([ExecPrice]-[ReferencePrice]) * [FX_to_CHF] - [Commission_CHF] ENDIF'),
    ], (650, 270))
    graph.connect(fee_join, pnl, "Join")
    summary = graph.add_summarize([
        ("Desk", "GroupBy", "Desk"), ("TradeID", "Count", "Executions"),
        ("Net_Settlement_CHF", "Sum", "Net_Settlement_CHF"), ("Realized_PnL_CHF", "Sum", "Realized_PnL_CHF"),
    ], (770, 90))
    graph.connect(pnl, summary)
    ordered_summary = graph.add_sort([("Desk", "Ascending")], (880, 90))
    graph.connect(summary, ordered_summary)
    matched = join(graph, pnl, clears, "TradeID", (770, 440))
    breaks = graph.add_filter("Abs([Quantity] * [ExecPrice] - [BrokerAmount]) > 0.01", (860, 420))
    graph.connect(matched, breaks, "Join")
    all_breaks = graph.add_union((930, 540))
    graph.connect(breaks, all_breaks, "True")
    graph.connect(matched, all_breaks, "Left")
    graph.connect(matched, all_breaks, "Right")
    order = graph.add_sort([("TradeID", "Ascending")], (1010, 560))
    graph.connect(all_breaks, order)
    workbook_output(graph, ordered_summary, "trade_recon_pack.xlsx", "Desk_PnL_Summary", 90)
    workbook_output(graph, order, "trade_recon_pack.xlsx", "Recon_Breaks", 600)
    pivot = graph.add_crosstab("Desk", "AssetClass", "Realized_PnL_CHF", position=(780, 215))
    graph.connect(pnl, pivot)
    ordered_pivot = graph.add_sort([("Desk", "Ascending")], (875, 215))
    graph.connect(pivot, ordered_pivot)
    html_report(graph, ordered_pivot, "desk_pnl_daily_report.html", 215, ["Desk", "Equities", "FX"])
    write_workflow(graph, folder / "equities_fx_recon_pnl.yxmd")


def surveillance(folder, *, threshold=2000000, desk="ALL"):
    rng = random.Random(29)
    rows = []
    for index in range(2000):
        symbol = ["NESN", "AAPL", "7203"][index // 6 % 3]
        vwap = [85.2, 158.4, 2730][index // 6 % 3]
        rows.append((f"2026-11-27 {9+index//720:02}:{index//12%60:02}:{index%12*5:02}",
                     f"C{index//6:04}", f"U{index%12:02}", ("APAC_EQ", "EMEA_EQ")[index//6%2],
                     symbol, "Sell" if index % 53 == 0 else "Buy", rng.randrange(100, 4800),
                     round(vwap * (1.012 if index % 17 == 0 else 1.0002), 4), vwap,
                     [0.90, 0.88, 0.0058][index // 6 % 3],
                     "Filled" if index % 57 else "Cancelled"))
    fields = ["ExecTimestamp", "ClientAccount", "TraderID", "Desk", "Symbol", "Side", "Qty",
              "ExecPrice", "MarketVWAP", "FX_to_CHF", "Status"]
    pd.DataFrame(rows, columns=fields).to_csv(folder / "intraday_order_blotter.csv", index=False)
    graph = WorkflowBuilder()
    source = cast_numbers(graph, input_table(graph, "intraday_order_blotter.csv", 180),
                          ["Qty", "ExecPrice", "MarketVWAP", "FX_to_CHF"], 180)
    filled = graph.add_filter(
        '[Status] = "Filled" AND StartsWith([ExecTimestamp], "__trade_date__") '
        'AND ("__desk__" = "ALL" OR [Desk] = "__desk__")', (310, 180),
    )
    graph.connect(source, filled)
    sorted_orders = graph.add_sort([(key, "Ascending") for key in ("ClientAccount", "Symbol", "ExecTimestamp")], (420, 180))
    graph.connect(filled, sorted_orders, "True")
    same_order = "[ClientAccount]=[Row-1:ClientAccount] AND [Symbol]=[Row-1:Symbol]"
    wash = graph.add_multi_row_formula(f"IF {same_order} AND [Side]!=[Row-1:Side] THEN 1 ELSE 0 ENDIF",
                                      "Is_Wash_Suspect", "Int32", (530, 180))
    graph.connect(sorted_orders, wash)
    split = graph.add_multi_row_formula(
        f"IF {same_order} THEN [Qty]*[ExecPrice]*[FX_to_CHF]+[Row-1:Rolling_Split_Notional] "
        "ELSE [Qty]*[ExecPrice]*[FX_to_CHF] ENDIF",
        "Rolling_Split_Notional", "Double", (650, 180),
    )
    graph.connect(wash, split)
    risk = graph.add_formula([
        ("VWAP_Slippage_Bps", "Double", "8", "Abs([ExecPrice]/[MarketVWAP]-1)*10000"),
        ("Risk_Level", "V_WString", "16", 'IF [Rolling_Split_Notional] >= 2000000 OR [VWAP_Slippage_Bps] >= 100 THEN "HIGH" ELSE "MEDIUM" ENDIF'),
    ], (770, 180))
    graph.connect(split, risk)
    alert = graph.add_filter('[Risk_Level]="HIGH" OR [Is_Wash_Suspect]=1', (885, 180))
    graph.connect(risk, alert)
    ranking = graph.add_sort([("Risk_Level", "Ascending"), ("Rolling_Split_Notional", "Descending"),
                              ("ExecTimestamp", "Ascending")], (990, 180))
    graph.connect(alert, ranking, "True")
    top = graph.add_sample("First", "50", (1100, 180))
    record_id = graph.add_record_id((1045, 180))
    graph.connect(ranking, record_id)
    graph.connect(record_id, top)
    sink = graph.add_csv_output("surveillance_breach_alerts.csv", (1230, 180))
    graph.connect(top, sink)
    html_report(graph, top, "compliance_alert_body.html", 290,
                ["ExecTimestamp", "ClientAccount", "Symbol", "Risk_Level", "VWAP_Slippage_Bps"])
    mail = graph._node("Email", """
        <From>surveillance@example.test</From><To>compliance@example.test</To>
        <Subject>Trade surveillance review</Subject><Body>See the attached alert table.</Body>
        <SMTPServerName>127.0.0.1</SMTPServerName><Port>1</Port>
        <Enabled>True</Enabled><SMTPAuth>False</SMTPAuth><Encryption>None</Encryption>
        """, (1240, 400))
    mail_input = graph.add_summarize([("ClientAccount", "Count", "Alerts")], (1120, 400))
    graph.connect(top, mail_input)
    graph.connect(mail_input, mail)

    def app(root):
        from alteryx2python.benchmark import _add_interface_node, _add_interface_tab, _add_numeric_interface, _add_question
        from alteryx2python.runtime.app_config import MANUAL_CHOICE_SEPARATOR

        questions, first_id = _add_interface_tab(root, macro=False)
        _add_numeric_interface(root, questions, first_id, target=risk,
                               destination=f"{risk}/FormulaFields/FormulaField[2]/@expression",
                               name="threshold", description="Exposure threshold", default=str(threshold),
                               maximum="20000000", token="2000000")
        for offset, kind, plugin, name, label, token in (
            (2, "Date", "Date.Date", "trade_date", "Trade date", "__trade_date__"),
            (4, "ListBox", "DropDownListBox.DropDown", "desk", "Trading desk", "__desk__"),
        ):
            question_id, action_id = str(first_id + offset), str(first_id + offset + 1)
            _add_interface_node(root.find("Nodes"), question_id, f"AlteryxGuiToolkit.Questions.{plugin}", "70", str(40 + offset * 25))
            _add_interface_node(root.find("Nodes"), action_id, "AlteryxGuiToolkit.Action.Action", "180", str(40 + offset * 25))
            question = _add_question(questions, kind, question_id, name, label)
            if kind == "ListBox":
                ET.SubElement(question, "Multiple", value="False")
                ET.SubElement(question, "Default").text = desk
                ET.SubElement(question, "Mode").text = "Manual"
                ET.SubElement(question, "Manual_Values").text = "\n".join(
                    f"{choice}{MANUAL_CHOICE_SEPARATOR}{choice}" for choice in (desk, *[value for value in ("ALL", "APAC_EQ", "EMEA_EQ") if value != desk])
                )
            for origin, destination, anchor in ((question_id, action_id, "Question"), (action_id, str(filled), "Action")):
                edge = ET.SubElement(root.find("Connections"), "Connection")
                ET.SubElement(edge, "Origin", ToolID=origin, Connection=anchor)
                ET.SubElement(edge, "Destination", ToolID=destination, Connection=anchor)
            actions = root.find("Properties/RuntimeProperties/Actions/NoCondition/True")
            action = ET.SubElement(actions, "Action")
            for key, value in {"Type": "UpdateValue", "Mode": "Simple", "Variable": name,
                               "ReplaceText": token, "Destination": f"{filled}/Expression"}.items():
                ET.SubElement(action, key).text = value
            ET.SubElement(action, "ToolId", value=action_id)
            ET.SubElement(action, "Replace", value="True")
    write_workflow(graph, folder / "trade_surveillance_alert.yxwz", app=app)


def positions(folder):
    rng = random.Random(30)
    region_specs = [("Zurich", 65001, "utf-8", "Instrument"),
                    ("Hong Kong", 936, "gbk", "证券"),
                    ("Tokyo", 932, "cp932", "銘柄")]
    graph = WorkflowBuilder()
    union = graph.add_union((410, 230))
    for index, (region, code_page, codec, title) in enumerate(region_specs):
        market = MARKETS[(1, 3, 4)[index]]
        filename = f"positions_{region.lower().replace(' ', '_')}.csv"
        rows = [(f"{index+1}{i:04}", region, market[0], market[1], rng.randrange(-300, 1200), market[4],
                 market[2], market[3], None if i % 17 == 0 else round(rng.uniform(.18, .34), 4))
                for i in range(325)]
        pd.DataFrame(rows, columns=["PositionID", "Region", "ISIN", title, "Units", "Price",
                                    "TradeCcy", "AssetClass", "Annualized_Vol"]).to_csv(
            folder / filename, index=False, encoding=codec,
        )
        y = 85 + index * 135
        source = input_table(graph, filename, y, encoding=code_page)
        select = cast_numbers(graph, source, ["Units", "Price", "Annualized_Vol"], y)
        node = ET.fromstring(graph.nodes_xml[-1])
        fields = node.find("./Properties/Configuration/SelectFields")
        ET.SubElement(fields, "SelectField", field=title, rename="Instrument", selected="True")
        graph.nodes_xml[-1] = ET.tostring(node, encoding="unicode")
        graph.connect(select, union)
    rates = {item[2]: item[5] for item in MARKETS}
    pd.DataFrame(rates.items(), columns=["TradeCcy", "FX_to_CHF"]).to_csv(folder / "fx_rates_chf.csv", index=False)
    fx = cast_numbers(graph, input_table(graph, "fx_rates_chf.csv", 500), ["FX_to_CHF"], 500)
    priced = join(graph, union, fx, "TradeCcy", (530, 310))
    average = graph.add_summarize([
        ("AssetClass", "GroupBy", "AssetClass"), ("Annualized_Vol", "Avg", "Mean_Vol"),
    ], (650, 450))
    graph.connect(priced, average, "Join")
    with_average = join(graph, priced, average, "AssetClass", (740, 310))
    graph.connections[-2] = (priced, "Join", with_average, "Left")
    risk = graph.add_formula([
        ("Annualized_Vol", "Double", "8", "IF IsNull([Annualized_Vol]) THEN [Mean_Vol] ELSE [Annualized_Vol] ENDIF"),
        ("Market_Value_CHF", "Double", "8", "[Units]*[Price]*[FX_to_CHF]"),
        ("VaR_99_1D_CHF", "Double", "8", "Abs([Market_Value_CHF])*[Annualized_Vol]*2.326347874/15.8745078664"),
    ], (850, 315))
    graph.connect(with_average, risk, "Join")
    ranked = graph.add_sort([("Market_Value_CHF", "Ascending"), ("PositionID", "Ascending")], (940, 315))
    graph.connect(risk, ranked)
    tile = graph._node(
        "Tile", '<Method>EqualRecords</Method><EqualRecords><NumTiles value="5"/></EqualRecords>', (1010, 315),
    )
    graph.connect(ranked, tile)
    summary = graph.add_summarize([
        ("Region", "GroupBy", "Region"), ("AssetClass", "GroupBy", "AssetClass"),
        ("Tile_Num", "GroupBy", "Risk_Bucket"), ("VaR_99_1D_CHF", "Sum", "VaR_99_1D_CHF"),
        ("Market_Value_CHF", "Sum", "Market_Value_CHF"),
    ], (1050, 475))
    graph.connect(tile, summary)
    ordered_summary = graph.add_sort(
        [(field, "Ascending") for field in ("Region", "AssetClass", "Risk_Bucket")], (1160, 475),
    )
    graph.connect(summary, ordered_summary)
    order = graph.add_sort([("PositionID", "Ascending")], (1070, 310))
    graph.connect(tile, order)
    workbook_output(graph, order, "consolidated_positions.xlsx", "Positions", 315)
    workbook_output(graph, ordered_summary, "consolidated_positions.xlsx", "Risk_Buckets", 525)
    html_report(graph, ordered_summary, "global_position_risk.html", 600,
                ["Region", "AssetClass", "Risk_Bucket", "VaR_99_1D_CHF", "Market_Value_CHF"])
    write_workflow(graph, folder / "multiregion_position_risk.yxmd")


def mifid(folder, endpoint):
    root = ET.parse(ROOT.parent / "sample_workflows" / "MIFID II.yxwz").getroot()

    def configuration(node):
        return root.find(f".//Node[@ToolID='{node}']/Properties/Configuration")

    input_name = "ROB-102928 Input template - EQ.xlsx"
    records = [
        ("Equity", "" if index % 2 else f"EQ_{index}_1", "MIFID", "EQ", str(index), "1")
        for index in range(1, 13)
    ]
    pd.DataFrame(records, columns=["Product Classification", "Internal Identifier", "Regulation",
                                   "tradeDomain", "tradeId", "tradeVersion"]).to_excel(
        folder / input_name, index=False, sheet_name="Sheet1",
    )
    target_fields = [
        item.get("name") for item in configuration(53).findall("./Fields/Field")
        if item.get("name", "")[:3].isdigit()
    ]
    if len(target_fields) != 87:
        raise ValueError(f"Expected 87 regulatory columns, got {len(target_fields)}")
    source_fields = [
        item.get("field") for item in configuration(46).findall("./DataFields/Field")
        if item.get("selected") == "True"
    ]

    def normalize(name):
        return "".join(char.lower() for char in name if char.isalnum())

    aliases = {"Report_Status": "reportStatus", "Executing_Entity_ID": "executingEntityId",
               "Buyer_ID": "buyerId", "Instrument_ID": "instrumentId", "Price": "price",
               "Quantity": "quantity", "Data_Category": "dataCategory"}
    names = {normalize(name): name for name in source_fields}
    used = set()
    with (folder / "mapping.csv").open("w", encoding="iso-8859-1", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["SourceField", "OutputOrder", "TargetField"])
        for index, field in enumerate(target_fields, 1):
            target = field[4:]
            candidate = aliases.get(target, names.get(normalize(target)))
            if candidate not in source_fields or candidate in used:
                candidate = f"Unreported_{index:03}"
            used.add(candidate)
            writer.writerow([candidate, index, target])
    keys = [
        item.get("name").removeprefix("result_exceptions_0_")
        for item in configuration(45).findall("./Fields/Field")
        if item.get("name", "").startswith("result_exceptions_0_")
    ]
    responses = {}
    for _, _, _, _, trade_id, _ in records:
        record = {key: "" for key in keys}
        record.update(assetClass="Equity", buyerId="SYNTHETICBUYER", executingEntityId="SYNTHETICDESK",
                      instrumentId="DE0007164600", price=f"{120+int(trade_id)/4:.2f}", priceCurrency="EUR",
                      quantity=str(100*int(trade_id)), reportStatus="Accepted", tradingCapacity="DEAL",
                      tradingDateTime="2026-11-27T09:15:00Z", transactionReferenceNumber=f"SYN-{trade_id}",
                      venue="XETR", tradeValidationRules="", dataCategory="Transaction")
        responses[trade_id] = {"result": {"exceptions": [record]}}
    (folder / "omr_responses.json").write_text(json.dumps(responses, indent=2), encoding="utf-8")
    for node_id in (4, 18, 32, 48, 59):
        setting = configuration(node_id).find("File")
        if node_id in {4, 18}:
            filename = input_name + "|||`Sheet1$`" if node_id == 4 else "disabled_replay.csv"
        else:
            filename = "MIFID output.xlsx|||Sheet1" if node_id == 59 else "mapping.csv"
        setting.text = filename
    # The fixture has one fixed Excel sheet. The file question changes the
    # workbook path while the Input Data node keeps its Excel format and sheet.
    question = root.find(".//Question[Type='FileBrowse']")
    question.find("Mode").text = "FileSpec"
    for tag in ("InputToolId", "DW2_SpatialOnly", "DW2_FieldMap"):
        question.remove(question.find(tag))
    ET.SubElement(question, "FileSpec").text = "Excel workbook (*.xlsx)|*.xlsx"
    file_action = root.find(".//Action[Type='UpdateInput']")
    file_action.find("Type").text = "UpdateValue"
    file_action.remove(file_action.find("InputTool"))
    file_action.remove(file_action.find("Required"))
    ET.SubElement(file_action, "Mode").text = "Simple"
    ET.SubElement(file_action, "Replace", value="True")
    ET.SubElement(file_action, "ReplaceText").text = input_name
    ET.SubElement(file_action, "Destination").text = "4/File"
    pd.DataFrame({"Payload": []}).to_csv(folder / "disabled_replay.csv", index=False)
    constant = ET.SubElement(root.find("./Properties/Constants"), "Constant")
    ET.SubElement(constant, "Namespace").text = "User"
    ET.SubElement(constant, "Name").text = "OMR_URL"
    ET.SubElement(constant, "Value").text = endpoint
    ET.SubElement(constant, "IsNumeric", value="False")
    for item in configuration(12).findall("./FormulaFields/FormulaField"):
        if item.get("field") == "URL":
            item.set("expression", "[User.OMR_URL]")
        elif item.get("field") == "Cookie":
            item.set("expression", '"__ubs_cookie__"')
    cookie_action = next(action for action in root.iter("Action") if action.findtext("ToolId") == "58" or action.findtext("Destination", "").startswith("12/"))
    cookie_action.find("ReplaceText").text = "__ubs_cookie__"
    # Remove source-machine provenance from the portable benchmark copy.
    for element in root.iter():
        for attribute, value in tuple(element.attrib.items()):
            if attribute == "source" and ("OneDrive" in value or ":\\" in value or "://" in value):
                del element.attrib[attribute]
        if element.tag in {"DefaultAnnotationText", "Name"} and element.text and "OneDrive" in element.text:
            element.text = None
    ET.ElementTree(root).write(folder / "MIFID II.yxwz", encoding="utf-8", xml_declaration=True)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    args = parser.parse_args()
    for index, generator in enumerate((equities, surveillance, positions, mifid)):
        folder = args.output_dir / SCENARIOS[index]
        folder.mkdir(parents=True, exist_ok=True)
        if generator is mifid:
            generator(folder, "http://127.0.0.1:1/omr")
        else:
            generator(folder)


if __name__ == "__main__":
    main()

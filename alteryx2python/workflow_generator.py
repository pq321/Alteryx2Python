"""Deterministic Alteryx workflow generator for equivalence testing.

Renders runnable .yxmd documents whose tool Configuration XML mirrors the
official sample shapes (D:/Alteryx/Samples "Learn one tool at a time"), with
embedded Text Input data and CSV output nodes, so the same workflow can be
executed by the native Alteryx engine and by the converted Python runtime
without any external data dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from xml.sax.saxutils import escape as _xml_escape


def escape(value):
    # The helpers interpolate values into both XML text and quoted attributes.
    return _xml_escape(str(value), {'"': "&quot;", "'": "&apos;"})


def render_workflow_spec(spec: object) -> str:
    """Render a validated :class:`WorkflowSpec` without changing preset APIs."""
    return spec.to_xml()


BASE_GUI = "AlteryxBasePluginsGui"
ENGINE_DLL = "AlteryxBasePluginsEngine.dll"

_GUI_TAIL = {"Select": "AlteryxSelect", "RegEx": "RegEx", "CrossTab": "CrossTab"}


def _plugin_id(kind: str) -> str:
    tail = _GUI_TAIL.get(kind, kind)
    return f"{BASE_GUI}.{tail}.{tail}"


def _entry(kind: str) -> str:
    from alteryx2python.parser.tool_catalog import CATALOG

    entry = next((item for item in CATALOG if item.tool_type == kind), None)
    if entry is None or not entry.engine_entry:
        raise ValueError(f"No verified engine entry for {kind}; use a node template")
    return entry.engine_entry


@dataclass
class WorkflowBuilder:
    """Compose a runnable Alteryx workflow as .yxmd XML."""

    next_tool_id: int = 1
    nodes_xml: list[str] = field(default_factory=list)
    connections: list[tuple[int, str, int, str]] = field(default_factory=list)
    output_tool_ids: list[int] = field(default_factory=list)

    def _tool_id(self) -> int:
        tool_id = self.next_tool_id
        self.next_tool_id += 1
        return tool_id

    def _node(
        self,
        kind: str,
        configuration_xml: str,
        position: tuple[int, int],
        gui_plugin: str | None = None,
    ) -> int:
        tool_id = self._tool_id()
        plugin = gui_plugin or _plugin_id(kind)
        entry = _entry(kind)
        from alteryx2python.parser.tool_catalog import CATALOG

        binding = next(item for item in CATALOG if item.tool_type == kind)
        dll = binding.engine_dll
        if not dll:
            raise ValueError(f"{kind} requires a macro/template binding")
        self.nodes_xml.append(
            f'<Node ToolID="{tool_id}">'
            f'<GuiSettings Plugin="{plugin}">'
            f'<Position x="{position[0]}" y="{position[1]}" />'
            f"</GuiSettings>"
            f"<Properties>"
            f"<Configuration>{configuration_xml}</Configuration>"
            f'<Annotation DisplayMode="0"><Name /><DefaultAnnotationText /><Left value="False" /></Annotation>'
            f"</Properties>"
            f'<EngineSettings EngineDll="{dll}" EngineDllEntryPoint="{entry}" />'
            f"</Node>"
        )
        return tool_id

    def connect(
        self,
        source: int,
        target: int,
        source_anchor: str = "Output",
        target_anchor: str = "Input",
    ) -> None:
        self.connections.append((source, source_anchor, target, target_anchor))

    # ---- input / output -------------------------------------------------

    def add_text_input(
        self,
        fields: list[str],
        rows: list[list[object]],
        position: tuple[int, int] = (54, 186),
    ) -> int:
        field_xml = "".join(f'<Field name="{escape(name)}" />' for name in fields)
        rows_xml = []
        for row in rows:
            cells = "".join(
                f"<c>{escape(str(value))}</c>" if str(value) != "" else "<c />"
                for value in row
            )
            rows_xml.append(f"<r>{cells}</r>")
        config = (
            f'<NumRows value="{len(rows)}" />'
            f"<Fields>{field_xml}</Fields>"
            f"<Data>{''.join(rows_xml)}</Data>"
        )
        return self._node("TextInput", config, position)

    def add_csv_output(
        self, file_path: str, position: tuple[int, int] = (600, 186)
    ) -> int:
        config = (
            f'<File MaxRecords="" FileFormat="0">{escape(file_path)}</File>'
            "<Passwords />"
            "<FormatSpecificOptions>"
            "<LineEndStyle>CRLF</LineEndStyle>"
            "<Delimeter>,</Delimeter>"
            "<ForceQuotes>False</ForceQuotes>"
            "<HeaderRow>True</HeaderRow>"
            "<CodePage>28591</CodePage>"
            "<WriteBOM>True</WriteBOM>"
            "</FormatSpecificOptions>"
            '<MultiFile value="False" />'
        )
        tool_id = self._node("DbFileOutput", config, position)
        self.output_tool_ids.append(tool_id)
        return tool_id

    # ---- transformation tools (official Configuration shapes) -----------

    def add_formula(
        self,
        expressions: list[tuple[str, str, str, str]],
        position: tuple[int, int] = (250, 186),
    ) -> int:
        """expressions: list of (field, type, size, expression)."""
        fields_xml = []
        for name, ftype, size, expr in expressions:
            size_attr = f' size="{size}"' if size else ""
            fields_xml.append(
                f'<FormulaField field="{escape(name)}"{size_attr} type="{ftype}"'
                f' expression="{escape(expr)}" />'
            )
        return self._node(
            "Formula", f"<FormulaFields>{''.join(fields_xml)}</FormulaFields>", position
        )

    def add_filter(
        self, expression: str, position: tuple[int, int] = (250, 186)
    ) -> int:
        config = (
            "<Mode>Custom</Mode>"
            "<Simple><Operator>=</Operator><Operands /></Simple>"
            f"<Expression>{escape(expression)}</Expression>"
        )
        return self._node("Filter", config, position)

    def add_select(
        self,
        fields: list[tuple[str, str]],
        include_unknown: bool = True,
        position: tuple[int, int] = (250, 186),
    ) -> int:
        entries = "".join(
            f'<SelectField field="{escape(name)}" selected="{selected}" />'
            for name, selected in fields
        )
        if include_unknown:
            entries += '<SelectField field="*Unknown" selected="True" />'
        config = (
            '<OrderChanged value="False" />'
            '<CommaDecimal value="False" />'
            f"<SelectFields>{entries}</SelectFields>"
        )
        return self._node("Select", config, position)

    def add_sort(
        self, order: list[tuple[str, str]], position: tuple[int, int] = (250, 186)
    ) -> int:
        entries = "".join(
            f'<Field field="{escape(name)}" order="{direction}" />'
            for name, direction in order
        )
        config = f'<SortInfo locale="0">{entries}</SortInfo>'
        return self._node("Sort", config, position)

    def add_summarize(
        self,
        actions: list[tuple[str, str, str]],
        position: tuple[int, int] = (250, 186),
    ) -> int:
        entries = []
        for name, action, rename in actions:
            rename_attr = f' rename="{escape(rename)}"' if rename else ""
            entries.append(
                f'<SummarizeField field="{escape(name)}" action="{action}"{rename_attr} />'
            )
        return self._node(
            "Summarize",
            f"<SummarizeFields>{''.join(entries)}</SummarizeFields>",
            position,
        )

    def add_join(
        self, left_field: str, right_field: str, position: tuple[int, int] = (250, 186)
    ) -> int:
        config = (
            f'<JoinInfo connection="Left"><Field field="{escape(left_field)}" /></JoinInfo>'
            f'<JoinInfo connection="Right"><Field field="{escape(right_field)}" /></JoinInfo>'
            "<SelectConfiguration>"
            '<Configuration outputConnection="Output">'
            '<OrderChanged value="False" /><CommaDecimal value="False" />'
            '<SelectFields><SelectField field="*Unknown" selected="True" /></SelectFields>'
            "</Configuration>"
            "</SelectConfiguration>"
        )
        return self._node("Join", config, position)

    def add_union(self, position: tuple[int, int] = (250, 186)) -> int:
        config = (
            "<Mode>ByName</Mode>"
            "<OutputMode>Combine</OutputMode>"
            '<InPerm><Input SubId="1" /><Input SubId="2" /></InPerm>'
        )
        return self._node("Union", config, position)

    def add_record_id(self, position: tuple[int, int] = (250, 186)) -> int:
        config = (
            "<FieldName>RecordID</FieldName>"
            "<StartValue>1</StartValue>"
            "<FieldType>Int64</FieldType>"
            "<FieldSize>6</FieldSize>"
            "<Position>0</Position>"
        )
        return self._node("RecordID", config, position)

    def add_sample(
        self, mode: str, value: str, position: tuple[int, int] = (250, 186)
    ) -> int:
        config = (
            f'<Mode>{mode}</Mode><N>{value}</N><GroupFields orderChanged="False" />'
        )
        return self._node("Sample", config, position)

    def add_unique(
        self, field_name: str, position: tuple[int, int] = (250, 186)
    ) -> int:
        config = f'<UniqueFields><Field field="{escape(field_name)}" /></UniqueFields>'
        return self._node("Unique", config, position)

    def add_crosstab(
        self,
        group_by: str,
        header: str,
        data_field: str,
        method: str = "Sum",
        position: tuple[int, int] = (250, 186),
    ) -> int:
        config = (
            f'<GroupFields><Field field="{escape(group_by)}" /></GroupFields>'
            f'<HeaderField field="{escape(header)}" />'
            f'<DataField field="{escape(data_field)}" />'
            f'<Methods><Method method="{method}" /></Methods>'
        )
        return self._node("CrossTab", config, position)

    def add_transpose(
        self,
        key_fields: list[str],
        data_fields: list[str],
        position: tuple[int, int] = (250, 186),
    ) -> int:
        keys = "".join(f'<Field field="{escape(k)}" />' for k in key_fields)
        data = "".join(
            f'<Field field="{escape(d)}" selected="True" />' for d in data_fields
        )
        config = (
            "<ErrorWarn>Ignore</ErrorWarn>"
            f"<KeyFields>{keys}</KeyFields>"
            f"<DataFields>{data}</DataFields>"
        )
        return self._node("Transpose", config, position)

    def add_multi_row_formula(
        self,
        expression: str,
        field_name: str = "NewField",
        ftype: str = "Double",
        position: tuple[int, int] = (250, 186),
    ) -> int:
        config = (
            '<UpdateField value="False" />'
            "<UpdateField_Name />"
            f"<CreateField_Name>{escape(field_name)}</CreateField_Name>"
            f"<CreateField_Type>{ftype}</CreateField_Type>"
            "<CreateField_Size>254</CreateField_Size>"
            "<OtherRows>Empty</OtherRows>"
            '<NumRows value="1" />'
            f"<Expression>{escape(expression)}</Expression>"
            "<GroupByFields />"
        )
        return self._node("MultiRowFormula", config, position)

    def add_datetime(
        self,
        input_field: str,
        output_field: str,
        date_format: str = "yyyy-MM-dd",
        position: tuple[int, int] = (250, 186),
    ) -> int:
        config = (
            '<IsFrom value="True" />'
            f"<InputFieldName>{escape(input_field)}</InputFieldName>"
            "<Language>English</Language>"
            f"<Format>{escape(date_format)}</Format>"
            f"<OutputFieldName>{escape(output_field)}</OutputFieldName>"
        )
        return self._node("DateTime", config, position)

    def add_regex(
        self,
        field_name: str,
        pattern: str,
        output_fields: list[tuple[str, str, int]] | None = None,
        method: str = "ParseComplex",
        position: tuple[int, int] = (250, 186),
    ) -> int:
        fields = "".join(
            f'<Field field="{escape(name)}" type="V_String" size="{size}" />'
            for name, _ftype, size in (output_fields or [])
        )
        config = (
            f"<Field>{escape(field_name)}</Field>"
            f'<RegExExpression value="{escape(pattern)}" />'
            '<CaseInsensitve value="False" />'
            f"<Method>{method}</Method>"
            f"<ParseComplex>{fields}</ParseComplex>"
        )
        return self._node("RegEx", config, position)

    def add_rank(
        self,
        field_name: str,
        order: str = "Descending",
        position: tuple[int, int] = (250, 186),
    ) -> int:
        config = (
            '<RankingModes><Mode value="Ordinal" /></RankingModes>'
            f'<SortInfo locale="0"><Field field="{escape(field_name)}" order="{order}" /></SortInfo>'
            "<GroupFields />"
        )
        return self._node("Rank", config, position)

    def add_running_total(
        self,
        field_name: str,
        group_field: str | None = None,
        position: tuple[int, int] = (250, 186),
    ) -> int:
        if group_field:
            groups = f"<GroupByFields><Field field='{escape(group_field)}' /></GroupByFields>"
        else:
            groups = "<GroupByFields />"
        config = (
            groups
            + f'<RunningTotalFields><Field field="{escape(field_name)}" /></RunningTotalFields>'
        )
        return self._node("RunningTotal", config, position)

    def add_tile(
        self,
        tile_method: str,
        num_tiles: int,
        field_name: str,
        position: tuple[int, int] = (250, 186),
    ) -> int:
        config = (
            "<CreateTileName>False</CreateTileName>"
            f"<TileMethod>{tile_method}</TileMethod>"
            f'<NumTiles value="{num_tiles}" />'
            f'<SortField field="{escape(field_name)}" />'
        )
        return self._node("Tile", config, position)

    def add_text_to_columns(
        self,
        field_name: str,
        delimiter: str = ",",
        position: tuple[int, int] = (250, 186),
    ) -> int:
        config = (
            f"<Field>{escape(field_name)}</Field>"
            f"<Delimeter>{escape(delimiter)}</Delimeter>"
            "<Split>0</Split><Advanced>0</Advanced>"
        )
        return self._node("TextToColumns", config, position)

    def render(self) -> str:
        connections_xml = []
        for source, source_anchor, target, target_anchor in self.connections:
            connections_xml.append(
                f'<Connection><Origin ToolID="{source}" Connection="{source_anchor}" />'
                f'<Destination ToolID="{target}" Connection="{target_anchor}" /></Connection>'
            )
        return (
            '<?xml version="1.0"?>\n'
            '<AlteryxDocument yxmdVer="2022.1">\n'
            f"<Nodes>{''.join(self.nodes_xml)}</Nodes>\n"
            f"<Connections>{''.join(connections_xml)}</Connections>\n"
            "<Properties>"
            '<Memory default="True" />'
            '<GlobalRecordLimit value="0" />'
            '<TempFiles fileCollation="True" />'
            "<RuntimeProperties><Actions /><Questions /></RuntimeProperties>"
            "</Properties>"
            "</AlteryxDocument>\n"
        )

import pandas as pd
import pytest

from alteryx2python.tools.xmlparse import xmlparse_tool


def test_xmlparse_root_outputs_attributes_and_child_values(workflow_context):
    frame = pd.DataFrame(
        {
            "row_id": [1],
            "customer_xml": [
                '<customer id="C001"><membership_level>Gold</membership_level><membership_start>2020-01-01</membership_start></customer>'
            ],
        }
    )

    result = xmlparse_tool(
        {"Input": frame},
        {
            "xml_field": "customer_xml",
            "parse_root": True,
            "child_values": True,
            "outer_xml": False,
        },
        workflow_context,
    )

    output = result["Output"]
    assert output.to_dict("records") == [
        {
            "row_id": 1,
            "customer_xml": frame.loc[0, "customer_xml"],
            "customer": "",
            "id": "C001",
            "membership_level": "Gold",
            "membership_start": "2020-01-01",
        }
    ]
    trace = workflow_context.traces[-1].to_dict()
    assert trace["outputs"]["Output"]["row_count"] == 1


def test_xmlparse_selected_repeated_element_expands_rows(workflow_context):
    frame = pd.DataFrame(
        {
            "row_id": [1],
            "customer_xml": [
                """
                <customer>
                  <transactions>
                    <transaction id="1"><date>2026-01-01</date><amount>10</amount></transaction>
                    <transaction id="2"><date>2026-01-02</date><amount>20</amount></transaction>
                  </transactions>
                </customer>
                """
            ],
        }
    )

    result = xmlparse_tool(
        {"Input": frame},
        {
            "xml_field": "customer_xml",
            "xml_element": "transaction",
            "parse_root": False,
            "child_values": True,
            "outer_xml": False,
        },
        workflow_context,
    )

    output = result["Output"]
    assert output[["transaction", "id", "date", "amount"]].to_dict("records") == [
        {"transaction": "", "id": "1", "date": "2026-01-01", "amount": "10"},
        {"transaction": "", "id": "2", "date": "2026-01-02", "amount": "20"},
    ]


def test_xmlparse_outer_xml_adds_element_xml_column(workflow_context):
    frame = pd.DataFrame({"xml": ["<root><item>A</item></root>"]})

    result = xmlparse_tool(
        {"Input": frame},
        {
            "xml_field": "xml",
            "xml_element": "item",
            "outer_xml": True,
        },
        workflow_context,
    )

    output = result["Output"]
    assert output.loc[0, "item"] == "A"
    assert output.loc[0, "item_OuterXML"] == "<item>A</item>"


def test_xmlparse_ignore_errors_passes_original_row(workflow_context):
    frame = pd.DataFrame({"xml": ["<root>"]})

    result = xmlparse_tool(
        {"Input": frame},
        {"xml_field": "xml", "ignore_errors": True},
        workflow_context,
    )

    assert result["Output"].to_dict("records") == [{"xml": "<root>"}]


def test_xmlparse_rejects_malformed_xml_by_default(workflow_context):
    with pytest.raises(ValueError, match="XMLParse failed"):
        xmlparse_tool(
            {"Input": pd.DataFrame({"xml": ["<root>"]})},
            {"xml_field": "xml"},
            workflow_context,
        )


def test_xmlparse_rejects_missing_xml_field(workflow_context):
    with pytest.raises(KeyError, match="Missing input fields: xml"):
        xmlparse_tool(
            {"Input": pd.DataFrame({"other": ["<root />"]})},
            {"xml_field": "xml"},
            workflow_context,
        )

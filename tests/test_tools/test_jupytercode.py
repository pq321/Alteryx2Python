import pandas as pd
import pytest

from alteryx2python.tools.jupytercode import JupyterCodeTool, jupytercode_tool


def test_jupytercode_propagates_script_failure(workflow_context):
    frame = pd.DataFrame({"a": [1]})

    with pytest.raises(RuntimeError):
        jupytercode_tool({"Input": frame}, {"production_mode_script": "raise RuntimeError()"}, workflow_context)
    assert not workflow_context.traces


def test_jupytercode_tool_class_executes_same_contract(workflow_context):
    script = 'from ayx import Alteryx\nimport pandas as pd\nAlteryx.write(pd.DataFrame({"value": [17]}), 2)'
    result = JupyterCodeTool().execute({}, {'production_mode_script': script}, workflow_context)
    assert set(result) == {'Output2'}
    assert result['Output2']['value'].tolist() == [17]
    assert workflow_context.traces[-1].config['external_code_executed'] is True


def test_jupytercode_copies_inputs_and_outputs_at_boundaries(workflow_context):
    original = pd.DataFrame({'value': [2, 5]})
    script = 'from ayx import Alteryx\nf = Alteryx.read("#1")\nf["value"] *= 3\nAlteryx.write(f, 3)\nf["value"] *= 2\nAlteryx.write(f, 1)'
    outputs = jupytercode_tool({'Input': original}, {'production_mode_script': script}, workflow_context)
    assert original['value'].tolist() == [2, 5]
    assert outputs['Output3']['value'].tolist() == [6, 15]
    assert outputs['Output']['value'].tolist() == [12, 30]


def test_missing_script_is_blocked_instead_of_passthrough(workflow_context):
    with pytest.raises(ValueError, match='saved production'):
        jupytercode_tool({'Input': pd.DataFrame({'value': [1]})}, {}, workflow_context)


def test_explicit_date_metadata_overrides_unsupported_inference(workflow_context):
    script = '''from ayx import Alteryx
import pandas as pd
frame = pd.DataFrame({"day": pd.to_datetime(["2026-11-12"]).astype("datetime64[us]")})
Alteryx.write(frame, 1, columns={"day": {"type": "Date", "length": 10}})
'''
    result = jupytercode_tool({}, {'production_mode_script': script}, workflow_context)
    assert result['Output']['day'].tolist() == ['2026-11-12']
    assert result['Output'].attrs['alteryx_schema'][0]['type'] == 'Date'

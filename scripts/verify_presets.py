from pathlib import Path
import tempfile
from alteryx2python.workflow_presets import preset_names, render_preset
from alteryx2python.equivalence import run_python_workflow, find_output_node

tmp = Path(tempfile.mkdtemp(prefix='ayx_verify_'))
for name in preset_names():
    yxmd = tmp / f'{name}.yxmd'
    yxmd.write_text(render_preset(name, str(tmp / f'{name}_native.csv')), encoding='utf-8')
    try:
        node = find_output_node(yxmd)
        frame = run_python_workflow(yxmd, node, tmp / f'{name}_python.csv')
        print(f'{name:26s} OK rows={len(frame):3d} cols={list(frame.columns)[:5]}')
    except Exception as exc:
        print(f'{name:26s} FAIL {str(exc)[:90]}')
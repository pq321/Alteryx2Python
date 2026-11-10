import pandas as pd
from alteryx2python.tools.local_macros import *
from alteryx2python.runtime.context import WorkflowContext
def test_count_and_frequency_record_real_outputs():
    c=WorkflowContext(); f=pd.DataFrame({'x':['a','a','b']})
    assert count_records({'Input8':f},{},c)['Output9'].iloc[0,0]==3
    assert frequency({'Input':f},{'field':'x'},c)['Output'].to_dict('records')==[{'x':'a','Count':2},{'x':'b','Count':1}]
    assert len(c.traces)==2
def test_json_base64_and_select():
    c=WorkflowContext(); f=pd.DataFrame({'x':['a',None],'y':[1,2]})
    parsed = pd.DataFrame({'JSON_Name':['x','nested.y'], 'JSON_ValueString':['a','b']})
    assert json_build({'Input':parsed},{},c)['Output']['JSON'].iloc[0]=='{"x":"a","nested":{"y":"b"}}'
    assert base64_encoder({'Input':f},{'field':'x'},c)['Output']['x_Base64'].iloc[0]=='YQ=='
    assert len(select_records({'Input':f},{'start':1,'end':1},c)['Output'])==1
def test_statistics_and_bad_config():
    c=WorkflowContext(); f=pd.DataFrame({'a':[1,2,3],'b':[3,2,1]})
    assert spearman({'Input':f},{'fields':['a','b']},c)['Output'].iloc[0,1]==-1
    try: imputation({'Input':f},{'method':'unknown','fields':['a']},c)
    except ValueError: pass
    else: raise AssertionError('unsupported method must fail')

def test_random_records_duplicate_index_and_validation():
    c=WorkflowContext(); frame=pd.DataFrame({'x':[1,2,3]}, index=[7,7,8])
    result=random_records({'Input':frame},{'number':1,'seed':2},c)
    assert len(result['Output']) == 1
    try: random_records({'Input':frame},{'number':4},c)
    except ValueError: pass
    else: raise AssertionError('out of range count must fail')

def test_ranges_create_samples_and_oversample_edge():
    c=WorkflowContext(); frame=pd.DataFrame({'g':['yes','no','no','no']})
    split=select_records({'Input':frame},{'ranges':[(1,1),(3,3)]},c)
    assert len(split['Output']) == 2
    samples=create_samples({'Input':frame},{'estimation pct':50,'validation pct':25,'rand seed':1},c)
    assert set(samples) == {'Estimation','Validation','Holdout'}
    over=oversample({'Input':frame},{'Selected_Field':'g','Oversample_Value':'yes','Desired_Pct':100},c)
    assert len(over['Output']) == 7

def test_official_value_shapes_parse_to_runtime_config():
    parsed = PARSERS['SelectRecords']({'Value': [{'attributes': {'name': 'Ranges'}, 'text': '1-2\n5+'}]})
    assert parsed.normalized_config['ranges'] == [(1, 2), (5, 2147483647)]
    encoded = PARSERS['Base64Encoder']({'Value': [{'attributes': {'name': 'Input.Macro Input'}, 'text': 'Text=Field1\n'}]})
    assert encoded.normalized_config['source_field'] == 'Field1'

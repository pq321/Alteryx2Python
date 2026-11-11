from decimal import Decimal

import pandas as pd
import pytest

from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.field_contracts import coerce_field, field_contract
from alteryx2python.tools.select import select_tool
from alteryx2python.tools.formula import formula_tool
from alteryx2python.tools.fieldinfo import fieldinfo_tool


@pytest.mark.parametrize('kind,size,minimum,maximum', [('Byte',1,0,255),('Int16',2,-32768,32767),('Int32',4,-2147483648,2147483647),('Int64',8,-9223372036854775808,9223372036854775807)])
def test_integer_storage_width_and_overflow(kind,size,minimum,maximum):
    with pytest.warns(RuntimeWarning, match='overflow'):
        result = coerce_field(pd.Series([str(minimum),str(maximum),str(maximum+1),None]), kind, size)
    assert result.iloc[:2].tolist() == [minimum,maximum]
    assert result.iloc[2:].isna().all()
    assert field_contract(kind)['size'] == size
    with pytest.raises(ValueError, match='fixed storage'):
        field_contract(kind, 20)


def test_unicode_width_and_decimal_scale():
    with pytest.warns(RuntimeWarning, match='truncated'):
        text = coerce_field(pd.Series(['abcd','中文测试',None,'']), 'V_WString', 3)
    assert text.iloc[:2].tolist() == ['abc','中文测']
    assert pd.isna(text.iloc[2]) and text.iloc[3] == ''
    with pytest.warns(RuntimeWarning, match='overflow'):
        numbers = coerce_field(pd.Series(['12.345','-1.235','9999.99',None]), 'FixedDecimal', '6.2')
    assert numbers.iloc[:2].tolist() == [Decimal('12.35'),Decimal('-1.24')]
    assert numbers.iloc[2:].isna().all()


def test_select_formula_and_fieldinfo_keep_declared_size():
    context = WorkflowContext()
    with pytest.warns(RuntimeWarning, match='truncated'):
        selected = select_tool({'Input':pd.DataFrame({'name':['abcdef'],'n':['2']})},
            {'select_fields':[{'source':'name','rename':'short','dtype':'V_WString','size':'4'},
                              {'source':'n','dtype':'Int16','size':'2'}]},context)['Output']
    assert selected['short'].tolist() == ['abcd']
    output = formula_tool({'Input':selected},{'formula_fields':[
        {'field':'money','expression':'[n] / 3','type':'FixedDecimal','size':'8.3'}]},context)['Output']
    assert output['money'].tolist() == [Decimal('0.667')]
    schemas = {row['name']:row for row in output.attrs['alteryx_schema']}
    assert schemas['short']['size'] == 4
    assert schemas['n']['size'] == 2
    assert schemas['money']['size'] == '8.3'
    info = fieldinfo_tool({'Input':output},{},context)['Output'].set_index('Name')
    assert info.loc['money','Scale'] == 3
    assert info.loc['short','Size'] == 4

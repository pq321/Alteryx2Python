import test from 'node:test';
import assert from 'node:assert/strict';
import {decodeGraph, connectError, upstreamFields, exampleGraph} from '../static/dist/model.js';
import {getLanguage, setLanguage, t, tr, dictionary} from '../static/dist/i18n.js';
import {parseObject} from '../static/dist/advanced.js';

test('imported workflows preserve complete XML, runtime, custom ports and unknown JSON', () => {
  const source = {
    name: '原始名称', workflowXml: '<AlteryxDocument><Properties><Unknown value="keep" /></Properties></AlteryxDocument>',
    propertiesXml: '<Properties><Events /></Properties>', eventsXml: '<Events/>', constantsXml: '<Constants/>', runtimePropertiesXml: '<RuntimeProperties/>',
    sourcePath: 'nested/root.yxwz', parameterMode: 'specialized', runtime: {answers: {selected: ['A', 'B']}, constants: {Minimum: 3}, delivery_profile: 'html-draft-v1', allowed_commands: []},
    future: {nested: [{value: null, preserved: true}]},
    nodes: [
      {id: '1', type: 'Vendor.Custom', x: 5, y: 20, parentId: 'container', inputs: [], outputs: ['Data'], extra: {keep: 7}, config: {configurationXml: '<Configuration><NewSetting/></Configuration>', engineSettingsXml: '<EngineSettings Macro="outer.yxmc"/>', future: [null, {enabled: true}]}},
      {id: '2', type: 'OtherTool', x: 250, y: 20, inputs: ['CustomInput'], outputs: [], config: {configurationXml: '<Configuration />'}},
    ], edges: [{from: '1', fromAnchor: 'Data', to: '2', toAnchor: 'CustomInput', wireless: true}],
  };
  const decoded = decodeGraph(source, []);
  assert.deepEqual(decoded, source);
  decoded.nodes[0].config.future[1].enabled = false;
  assert.equal(source.nodes[0].config.future[1].enabled, true);
});

test('raw Text Input does not inject simple defaults or lose its typed XML', () => {
  const graph = {name: 'raw', nodes: [{id: '1', type: 'TextInput', x: 0, y: 0, config: {configurationXml: '<Configuration><MetaInfo><RecordInfo><Field name="金额" type="FixedDecimal" size="19.2"/></RecordInfo></MetaInfo><Data/></Configuration>'}}], edges: []};
  const decoded = decodeGraph(graph, [{type: 'TextInput', inputs: [], outputs: ['Output'], defaults: {fields: ['Col1'], rows: []}}]);
  assert.deepEqual(decoded.nodes[0].config, graph.nodes[0].config);
});

test('custom macro JSON restores without a separately registered backend tool', () => {
  const graph = {name: 'macro', nodes: [{id: '1', type: 'Macro_outer', x: 0, y: 0, inputs: [], outputs: ['Output'], config: {configurationXml: '<Configuration/>', engineSettingsXml: '<EngineSettings Macro="C:/bundle/outer.yxmc"/>'}}], edges: []};
  assert.deepEqual(decodeGraph(graph, []), graph);
});
test('connected custom macros restore saved definitions before validating edges', () => {
  const tool = {type: 'Macro_local', label: 'Local macro', category: 'Macros', inputs: ['Input'], outputs: ['Output'], defaults: {configurationXml: '<Configuration/>', engineSettingsXml: '<EngineSettings Macro="local.yxmc"/>'}};
  const graph = {name: 'restore', toolDefinitions: [tool], nodes: [{id: '1', type: 'TextInput', x: 0, y: 0, config: {fields: ['a'], rows: [['1']]}}, {id: '2', type: tool.type, x: 250, y: 0, config: tool.defaults}], edges: [{from: '1', fromAnchor: 'Output', to: '2', toAnchor: 'Input'}]};
  assert.deepEqual(decodeGraph(graph, [{type: 'TextInput', inputs: [], outputs: ['Output'], defaults: {}}]), graph);
  assert.throws(() => decodeGraph({...graph, toolDefinitions: [{...tool, outputs: 'invalid'}]}, []));
});

test('connections use instance ports when the tool catalogue has different defaults', () => {
  const graph = {name: 'ports', nodes: [{id: '1', type: 'Python', x: 0, y: 0, inputs: [], outputs: ['Output5'], config: {}}, {id: '2', type: 'Select', x: 0, y: 0, inputs: ['Input2'], outputs: [], config: {}}], edges: []};
  assert.equal(connectError(graph, {from: '1', fromAnchor: 'Output5', to: '2', toAnchor: 'Input2'}, []), null);
});

test('Select configuration retains type, length, scale and rename and exposes renamed fields', () => {
  const graph = {name: 'select', nodes: [{id: '1', type: 'TextInput', x: 0, y: 0, config: {fields: ['Amount'], rows: [[1]]}}, {id: '2', type: 'Select', x: 250, y: 0, config: {fields: [{field: 'Amount', selected: 'True', rename: 'Total', type: 'FixedDecimal', size: '19', scale: '2'}], includeUnknown: false}}], edges: [{from: '1', fromAnchor: 'Output', to: '2', toAnchor: 'Input'}]};
  assert.deepEqual(upstreamFields(graph, '2'), ['Total']);
  assert.deepEqual(decodeGraph(graph, [{type: 'TextInput', inputs: [], outputs: ['Output'], defaults: {}}, {type: 'Select', inputs: ['Input'], outputs: ['Output'], defaults: {}}]).nodes[1].config, graph.nodes[1].config);
});

test('language preference persists and interpolation never mutates graph or code values', () => {
  const store = new Map();
  globalThis.localStorage = {getItem: key => store.get(key) ?? null, setItem: (key, value) => store.set(key, value)};
  const graph = exampleGraph(), before = JSON.stringify(graph);
  setLanguage('en');
  assert.equal(getLanguage(), 'en');
  assert.equal(store.get('alteryx2python.language'), 'en');
  assert.equal(t('第 {row} 行第 {column} 列', {row: 4, column: 2}), 'Row 4 column 2');
  assert.equal(tr('筛选条件'), 'Filter expression');
  assert.equal(tr('Vendor.Unknown'), 'Vendor.Unknown');
  assert.equal(JSON.stringify(graph), before);
  for (const [key, value] of Object.entries(dictionary)) assert.deepEqual([...key.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort(), [...value.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort());
  setLanguage('zh');
  assert.equal(tr('Filter expression'), '筛选条件');
  delete globalThis.localStorage;
});

test('advanced config JSON accepts unknown nested keys but rejects non-object roots', () => {
  assert.deepEqual(parseObject('{"known":null,"unknown":{"nested":[true,3,"x"]}}'), {known: null, unknown: {nested: [true, 3, 'x']}});
  assert.throws(() => parseObject('[]'));
  assert.throws(() => parseObject('null'));
});

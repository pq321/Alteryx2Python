import test from 'node:test';
import assert from 'node:assert/strict';
import {parseClipboard, pasteCells, connectError, decodeGraph, upstreamFields, exampleGraph} from '../static/dist/model.js';
const tools = [
  {type: 'TextInput', inputs: [], outputs: ['Output'], defaults: {fields: ['A'], rows: []}},
  {type: 'Formula', inputs: ['Input'], outputs: ['Output'], defaults: {expressions: []}},
  {type: 'Filter', inputs: ['Input'], outputs: ['True', 'False'], defaults: {}},
  {type: 'Sort', inputs: ['Input'], outputs: ['Output'], defaults: {}},
  {type: 'DbFileOutput', inputs: ['Input'], outputs: [], defaults: {}},
];
test('clipboard preserves commas, quoted tabs/newlines, empty cells and escaped quotes', () => {
  assert.deepEqual(parseClipboard('a,b\t"line 1\nline 2"\t"say ""hi"""\r\n3\t\t4\r\n'), [['a,b', 'line 1\nline 2', 'say "hi"'], ['3', '', '4']]);
});
test('pasting expands table without deleting existing data', () => {
  const config = {fields: ['Col1'], rows: [['keep']]};
  pasteCells(config, 'x\ty\nz\t', 1, 1);
  assert.deepEqual(config.fields, ['Col1', 'Col2', 'Col3']);
  assert.deepEqual(config.rows, [['keep', '', ''], ['', 'x', 'y'], ['', 'z', '']]);
});
test('connections reject cycles, duplicates, wrong anchors and occupied inputs', () => {
  const graph = {name: 'test', nodes: ['1', '2', '3'].map(id => ({id, type: 'Formula', x: 0, y: 0, config: {}})), edges: [{from: '1', fromAnchor: 'Output', to: '2', toAnchor: 'Input'}]};
  assert.match(connectError(graph, {to: '2', toAnchor: 'Input', fromAnchor: 'Output', from: '1'}, tools), /已存在/);
  assert.match(connectError(graph, {from: '3', fromAnchor: 'Output', to: '2', toAnchor: 'Input'}, tools), /已有连线/);
  assert.match(connectError(graph, {from: '2', fromAnchor: 'Output', to: '1', toAnchor: 'Input'}, tools), /循环/);
  assert.match(connectError(graph, {from: '1', fromAnchor: 'False', to: '3', toAnchor: 'Input'}, tools), /不存在/);
});
test('workflow import validates unknown tools, duplicate IDs, and invalid connections', () => {
  const graph = exampleGraph();
  assert.equal(decodeGraph(graph, tools).nodes.length, 5);
  assert.throws(() => decodeGraph({...graph, nodes: [...graph.nodes, graph.nodes[0]]}, tools), /重复节点/);
  assert.throws(() => decodeGraph({...graph, edges: [...graph.edges, {from: 'missing', fromAnchor: 'Output', to: '2', toAnchor: 'Input'}]}, tools), /不存在/);
});
test('upstream formula fields are available to downstream field pickers', () => {
  const graph = exampleGraph();
  assert.deepEqual(upstreamFields(graph, '3'), ['Region', 'Product', 'Qty', 'Price', 'Total']);
});


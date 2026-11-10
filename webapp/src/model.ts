export type Cell = string | number | boolean | null;
export type Entry = Record<string, string>;
export interface Config {
  [key: string]: string | number | boolean | string[] | Cell[][] | Entry[];
}
export interface Tool {
  type: string; label: string; category: string; inputs: string[]; outputs: string[];
  defaults: Config; multiInput?: boolean;
}
export interface WorkflowNode { id: string; type: string; x: number; y: number; config: Config; }
export interface Edge { from: string; fromAnchor: string; to: string; toAnchor: string; }
export interface Graph { name: string; nodes: WorkflowNode[]; edges: Edge[]; }
export interface Point { x: number; y: number; }
export interface CompileResult { name: string; python: string; yxmd: string; unsupported: string[]; }
export interface Preview { node: string; anchor: string; columns: string[]; rows: Cell[][]; rowCount: number; csv: string; }
export interface RunResult extends CompileResult { previews: Preview[]; }
export interface ImportedData {
  file: string; sourceFile: string; name: string; fields: string[]; rows: Cell[][]; rowCount: number;
  sheets: string[]; sheet: string; delimiter: string;
}
export const NODE_W = 190, NODE_H = 76;
export const labels: Record<string, string> = {
  TextInput: '文本输入', DbFileInput: '文件输入', DbFileOutput: '输出数据', Formula: '公式', Filter: '筛选',
  Select: '选择字段', Sort: '排序', Unique: '去重', MultiRowFormula: '多行公式', DateTime: '日期转换',
  Summarize: '汇总', CrossTab: '交叉表', Transpose: '转置', RecordID: '记录 ID', Sample: '抽样',
  RunningTotal: '累计求和', Rank: '排名', TextToColumns: '文本分列', Join: '连接', Union: '合并', RegEx: '正则解析',
};
export const symbols: Record<string, string> = {
  TextInput: '▦', DbFileInput: '↥', DbFileOutput: '↧', Formula: 'ƒ', Filter: '▽', Select: '☷', Sort: '↕',
  Unique: '≠', MultiRowFormula: 'ƒ', DateTime: '◷', Summarize: 'Σ', CrossTab: '⊞', Transpose: '⇄',
  RecordID: '#', Sample: '⅟', RunningTotal: '∑', Rank: '≡', TextToColumns: '⋮', Join: '⋈', Union: '∪', RegEx: '.*',
};
export const categories: Record<string, string> = { 'In/Out': '输入 / 输出', Preparation: '数据准备', Transform: '数据转换', Join: '数据连接', Parse: '解析' };
export const text = (config: Config, key: string, fallback = ''): string => String(config[key] ?? fallback);
export function strings(config: Config, key: string): string[] {
  const value = config[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}
export function entries(config: Config, key: string): Entry[] {
  const value = config[key];
  return Array.isArray(value) ? value.filter((item): item is Entry => !!item && typeof item === 'object' && !Array.isArray(item)) : [];
}
export function rows(config: Config): Cell[][] {
  const value = config.rows;
  return Array.isArray(value) ? value.filter((item): item is Cell[] => Array.isArray(item)) : [];
}
export function uniqueField(fields: string[]): string {
  let n = fields.length + 1;
  while (fields.includes('Col' + n)) n++;
  return 'Col' + n;
}
// Clipboard tables use tabs. Preserve commas, quoted newlines and escaped quotes inside cells.
export function parseClipboard(source: string): string[][] {
  const result: string[][] = [[]];
  let value = '', quoted = false;
  for (let i = 0; i < source.length; i++) {
    const char = source[i];
    if (char === '"' && (quoted || !value)) {
      if (quoted && source[i + 1] === '"') { value += '"'; i++; }
      else quoted = !quoted;
    } else if (!quoted && (char === '\t' || char === '\n' || char === '\r')) {
      result[result.length - 1]!.push(value); value = '';
      if (char !== '\t') {
        if (char === '\r' && source[i + 1] === '\n') i++;
        result.push([]);
      }
    } else value += char;
  }
  result[result.length - 1]!.push(value);
  if (result.length > 1 && result.at(-1)?.length === 1 && result.at(-1)?.[0] === '' && /[\r\n]$/.test(source)) result.pop();
  return result;
}
export function pasteCells(config: Config, source: string, startRow: number, startCol: number): void {
  const pasted = parseClipboard(source), fields = strings(config, 'fields'), data = rows(config);
  const width = startCol + Math.max(...pasted.map(row => row.length));
  while (fields.length < width) fields.push(uniqueField(fields));
  while (data.length < startRow + pasted.length) data.push([]);
  pasted.forEach((row, r) => row.forEach((cell, c) => { data[startRow + r]![startCol + c] = cell; }));
  config.fields = fields; config.rows = data.map(row => fields.map((_, c) => row[c] ?? ''));
}
export function connectError(graph: Graph, edge: Edge, tools: Tool[]): string | null {
  const source = graph.nodes.find(n => n.id === edge.from), target = graph.nodes.find(n => n.id === edge.to);
  if (!source || !target) return '连线引用了不存在的节点';
  if (!tools.find(t => t.type === source.type)?.outputs.includes(edge.fromAnchor) || !tools.find(t => t.type === target.type)?.inputs.includes(edge.toAnchor)) return '输入或输出端口不存在';
  if (edge.from === edge.to) return '节点不能连接到自身';
  if (graph.edges.some(e => e.from === edge.from && e.to === edge.to && e.fromAnchor === edge.fromAnchor && e.toAnchor === edge.toAnchor)) return '这条连线已存在';
  if (!tools.find(t => t.type === target.type)?.multiInput && graph.edges.some(e => e.to === edge.to && e.toAnchor === edge.toAnchor)) return '该输入已有连线，请先移除原连线';
  const pending = [edge.to], visited = new Set<string>();
  while (pending.length) {
    const id = pending.pop()!;
    if (id === edge.from) return '连线会形成循环';
    if (visited.has(id)) continue;
    visited.add(id); graph.edges.filter(e => e.from === id).forEach(e => pending.push(e.to));
  }
  return null;
}
export function upstreamFields(graph: Graph, id: string, seen = new Set<string>(), anchor = 'Output'): string[] {
  if (seen.has(id)) return [];
  seen.add(id);
  const node = graph.nodes.find(n => n.id === id);
  if (!node) return [];
  const c = node.config;
  if (node.type === 'TextInput' || node.type === 'DbFileInput') return strings(c, 'fields');
  const incoming = graph.edges.filter(e => e.to === id);
  if (node.type === 'Join') return incoming.flatMap(e => {
    const fields = upstreamFields(graph, e.from, new Set(seen), e.fromAnchor);
    if (anchor === 'Left' || anchor === 'Right') return e.toAnchor === anchor ? fields : [];
    return fields.map(f => e.toAnchor + '_' + f);
  });
  let result = [...new Set(incoming.flatMap(e => upstreamFields(graph, e.from, new Set(seen), e.fromAnchor)))];
  if (node.type === 'Select') {
    const picks = entries(c, 'fields');
    result = result.filter(f => picks.find(p => p.field === f)?.selected !== 'False' && (Boolean(c.includeUnknown) || picks.some(p => p.field === f)));
  }
  if (node.type === 'Formula') result.push(...entries(c, 'expressions').map(e => e.field ?? ''));
  if (node.type === 'Summarize') result = entries(c, 'actions').map(e => e.rename || e.field || '');
  if (node.type === 'RecordID') result.unshift(text(c, 'fieldName', 'RecordID'));
  if (node.type === 'DateTime') result.push(text(c, 'outputField'));
  if (node.type === 'MultiRowFormula') result.push(text(c, 'fieldName'));
  if (node.type === 'RegEx') result.push(text(c, 'outputField'));
  if (node.type === 'RunningTotal') result.push('RunningTotal_' + text(c, 'field'));
  if (node.type === 'Rank') result.push('Rank');
  if (node.type === 'TextToColumns') result.push(...Array.from({length: Math.max(1, Math.min(100, Number(c.numFields) || 3))}, (_, i) => (text(c, 'rootName') || text(c, 'field')) + (i + 1)));
  return [...new Set(result.filter(Boolean))];
}
function object(value: unknown): value is Record<string, unknown> { return !!value && typeof value === 'object' && !Array.isArray(value); }
export function decodeGraph(value: unknown, tools: Tool[]): Graph {
  if (!object(value) || typeof value.name !== 'string' || !Array.isArray(value.nodes) || !Array.isArray(value.edges)) throw new Error('工作流需要 name、nodes 和 edges');
  const nodes: WorkflowNode[] = [], ids = new Set<string>();
  for (const raw of value.nodes) {
    if (!object(raw) || typeof raw.id !== 'string' || ids.has(raw.id) || typeof raw.type !== 'string' || !tools.some(t => t.type === raw.type) || typeof raw.x !== 'number' || !Number.isFinite(raw.x) || typeof raw.y !== 'number' || !Number.isFinite(raw.y) || !object(raw.config)) throw new Error('工作流包含无效或重复节点');
    const tool = tools.find(t => t.type === raw.type)!;
    const config: Config = structuredClone(tool.defaults);
    for (const [key, item] of Object.entries(raw.config)) {
      if (typeof item === 'string' || typeof item === 'boolean' || typeof item === 'number') config[key] = item;
      else if (Array.isArray(item) && item.every(v => typeof v === 'string')) config[key] = item as string[];
      else if (Array.isArray(item) && item.every(v => Array.isArray(v) && v.every(c => c === null || ['string', 'number', 'boolean'].includes(typeof c)))) config[key] = item as Cell[][];
      else if (Array.isArray(item) && item.every(v => object(v) && Object.values(v).every(c => typeof c === 'string'))) config[key] = item as Entry[];
      else throw new Error('工作流包含无效的节点配置');
    }
    if (raw.type === 'TextInput' && (!strings(config, 'fields').length || (config.fields as unknown[]).some(v => typeof v !== 'string'))) throw new Error('文本输入的字段配置无效');
    nodes.push({id: raw.id, type: raw.type, x: raw.x, y: raw.y, config}); ids.add(raw.id);
  }
  const graph: Graph = {name: value.name, nodes, edges: []};
  for (const raw of value.edges) {
    if (!object(raw) || !['from', 'to', 'fromAnchor', 'toAnchor'].every(k => typeof raw[k] === 'string')) throw new Error('连线格式无效');
    const edge = raw as unknown as Edge;
    const error = connectError(graph, edge, tools);
    if (error) throw new Error(error);
    graph.edges.push(edge);
  }
  return graph;
}
export function exampleGraph(): Graph {
  return {
    name: '销售分析',
    nodes: [
      {id: '1', type: 'TextInput', x: 65, y: 140, config: {fields: ['Region', 'Product', 'Qty', 'Price'], rows: [['North', 'Widget', '4', '25'], ['South', 'Gadget', '9', '15'], ['North', 'Gear', '2', '70'], ['South', 'Widget', '6', '30'], ['East', 'Gear', '3', '70']]}},
      {id: '2', type: 'Formula', x: 330, y: 140, config: {expressions: [{field: 'Total', type: 'Double', size: '', expression: '[Qty] * [Price]'}]}},
      {id: '3', type: 'Filter', x: 595, y: 140, config: {expression: '[Qty] >= 4'}},
      {id: '4', type: 'Sort', x: 860, y: 140, config: {order: [{field: 'Total', order: 'Descending'}]}},
      {id: '5', type: 'DbFileOutput', x: 1125, y: 140, config: {file: 'sales.csv'}},
    ],
    edges: [
      {from: '1', fromAnchor: 'Output', to: '2', toAnchor: 'Input'}, {from: '2', fromAnchor: 'Output', to: '3', toAnchor: 'Input'},
      {from: '3', fromAnchor: 'True', to: '4', toAnchor: 'Input'}, {from: '4', fromAnchor: 'Output', to: '5', toAnchor: 'Input'},
    ],
  };
}


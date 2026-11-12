import { tr } from './i18n.js';
export const NODE_W = 190, NODE_H = 76;
export const labels = {
    TextInput: '文本输入', DbFileInput: '文件输入', DbFileOutput: '输出数据', Formula: '公式', Filter: '筛选',
    Select: '选择字段', Sort: '排序', Unique: '去重', MultiRowFormula: '多行公式', DateTime: '日期转换',
    Summarize: '汇总', CrossTab: '交叉表', Transpose: '转置', RecordID: '记录 ID', Sample: '抽样',
    RunningTotal: '累计求和', Rank: '排名', TextToColumns: '文本分列', Join: '连接', Union: '合并', RegEx: '正则解析',
};
export const symbols = {
    TextInput: '▦', DbFileInput: '↥', DbFileOutput: '↧', Formula: 'ƒ', Filter: '▽', Select: '☷', Sort: '↕',
    Unique: '≠', MultiRowFormula: 'ƒ', DateTime: '◷', Summarize: 'Σ', CrossTab: '⊞', Transpose: '⇄',
    RecordID: '#', Sample: '⅟', RunningTotal: '∑', Rank: '≡', TextToColumns: '⋮', Join: '⋈', Union: '∪', RegEx: '.*',
};
export const categories = { 'In/Out': '输入 / 输出', Preparation: '数据准备', Transform: '数据转换', Join: '数据连接', Parse: '解析' };
export const toolLabel = (tool) => tool ? tr(labels[tool.type] ?? ('label' in tool && typeof tool.label === 'string' ? tool.label : tool.type)) : '';
export const categoryLabel = (category) => tr(categories[category] ?? category);
export function ports(node, tools, input) { return (input ? node.inputs : node.outputs) ?? (input ? tools.find(t => t.type === node.type)?.inputs : tools.find(t => t.type === node.type)?.outputs) ?? []; }
export const text = (config, key, fallback = '') => String(config[key] ?? fallback);
export function strings(config, key) {
    const value = config[key];
    return Array.isArray(value) ? value.filter((item) => typeof item === 'string') : [];
}
export function entries(config, key) {
    const value = config[key];
    return Array.isArray(value) ? value.filter((item) => !!item && typeof item === 'object' && !Array.isArray(item)) : [];
}
export function rows(config) {
    const value = config.rows;
    return Array.isArray(value) ? value.filter((item) => Array.isArray(item)) : [];
}
export function uniqueField(fields) {
    let n = fields.length + 1;
    while (fields.includes('Col' + n))
        n++;
    return 'Col' + n;
}
// Clipboard tables use tabs. Preserve commas, quoted newlines and escaped quotes inside cells.
export function parseClipboard(source) {
    const result = [[]];
    let value = '', quoted = false;
    for (let i = 0; i < source.length; i++) {
        const char = source[i];
        if (char === '"' && (quoted || !value)) {
            if (quoted && source[i + 1] === '"') {
                value += '"';
                i++;
            }
            else
                quoted = !quoted;
        }
        else if (!quoted && (char === '\t' || char === '\n' || char === '\r')) {
            result[result.length - 1].push(value);
            value = '';
            if (char !== '\t') {
                if (char === '\r' && source[i + 1] === '\n')
                    i++;
                result.push([]);
            }
        }
        else
            value += char;
    }
    result[result.length - 1].push(value);
    if (result.length > 1 && result.at(-1)?.length === 1 && result.at(-1)?.[0] === '' && /[\r\n]$/.test(source))
        result.pop();
    return result;
}
export function pasteCells(config, source, startRow, startCol) {
    const pasted = parseClipboard(source), fields = strings(config, 'fields'), data = rows(config);
    const width = startCol + Math.max(...pasted.map(row => row.length));
    while (fields.length < width)
        fields.push(uniqueField(fields));
    while (data.length < startRow + pasted.length)
        data.push([]);
    pasted.forEach((row, r) => row.forEach((cell, c) => { data[startRow + r][startCol + c] = cell; }));
    config.fields = fields;
    config.rows = data.map(row => fields.map((_, c) => row[c] ?? ''));
}
export function connectError(graph, edge, tools) {
    const source = graph.nodes.find(n => n.id === edge.from), target = graph.nodes.find(n => n.id === edge.to);
    if (!source || !target)
        return tr('连线引用了不存在的节点');
    if (!ports(source, tools, false).includes(edge.fromAnchor) || !ports(target, tools, true).includes(edge.toAnchor))
        return tr('输入或输出端口不存在');
    if (edge.from === edge.to)
        return tr('节点不能连接到自身');
    if (graph.edges.some(e => e.from === edge.from && e.to === edge.to && e.fromAnchor === edge.fromAnchor && e.toAnchor === edge.toAnchor))
        return tr('这条连线已存在');
    if (!tools.find(t => t.type === target.type)?.multiInput && graph.edges.some(e => e.to === edge.to && e.toAnchor === edge.toAnchor))
        return tr('该输入已有连线，请先移除原连线');
    const pending = [edge.to], visited = new Set();
    while (pending.length) {
        const id = pending.pop();
        if (id === edge.from)
            return tr('连线会形成循环');
        if (visited.has(id))
            continue;
        visited.add(id);
        graph.edges.filter(e => e.from === id).forEach(e => pending.push(e.to));
    }
    return null;
}
export function upstreamFields(graph, id, seen = new Set(), anchor = 'Output') {
    if (seen.has(id))
        return [];
    seen.add(id);
    const node = graph.nodes.find(n => n.id === id);
    if (!node)
        return [];
    const c = node.config;
    if (node.type === 'TextInput' || node.type === 'DbFileInput') {
        if (strings(c, 'fields').length || typeof c.configurationXml !== 'string' || typeof DOMParser === 'undefined')
            return strings(c, 'fields');
        const document = new DOMParser().parseFromString(c.configurationXml, 'application/xml');
        return Array.from(document.querySelectorAll('Fields > Field, RecordInfo > Field')).map(field => field.getAttribute('name') ?? '').filter(Boolean);
    }
    const incoming = graph.edges.filter(e => e.to === id);
    if (node.type === 'Join')
        return incoming.flatMap(e => {
            const fields = upstreamFields(graph, e.from, new Set(seen), e.fromAnchor);
            if (anchor === 'Left' || anchor === 'Right')
                return e.toAnchor === anchor ? fields : [];
            return fields.map(f => e.toAnchor + '_' + f);
        });
    let result = [...new Set(incoming.flatMap(e => upstreamFields(graph, e.from, new Set(seen), e.fromAnchor)))];
    if (node.type === 'Select') {
        const picks = entries(c, 'fields');
        result = result.filter(f => picks.find(p => p.field === f)?.selected !== 'False' && (Boolean(c.includeUnknown) || picks.some(p => p.field === f))).map(f => picks.find(p => p.field === f)?.rename || f);
    }
    if (node.type === 'Formula')
        result.push(...entries(c, 'expressions').map(e => e.field ?? ''));
    if (node.type === 'Summarize')
        result = entries(c, 'actions').map(e => e.rename || e.field || '');
    if (node.type === 'RecordID')
        result.unshift(text(c, 'fieldName', 'RecordID'));
    if (node.type === 'DateTime')
        result.push(text(c, 'outputField'));
    if (node.type === 'MultiRowFormula')
        result.push(text(c, 'fieldName'));
    if (node.type === 'RegEx')
        result.push(text(c, 'outputField'));
    if (node.type === 'RunningTotal')
        result.push('RunningTotal_' + text(c, 'field'));
    if (node.type === 'Rank')
        result.push('Rank');
    if (node.type === 'TextToColumns')
        result.push(...Array.from({ length: Math.max(1, Math.min(100, Number(c.numFields) || 3)) }, (_, i) => (text(c, 'rootName') || text(c, 'field')) + (i + 1)));
    return [...new Set(result.filter(Boolean))];
}
function object(value) { return !!value && typeof value === 'object' && !Array.isArray(value); }
export function decodeGraph(value, tools) {
    if (!object(value) || typeof value.name !== 'string' || !Array.isArray(value.nodes) || !Array.isArray(value.edges))
        throw new Error(tr('工作流需要 name、nodes 和 edges'));
    const definitions = value.toolDefinitions ?? [];
    if (!Array.isArray(definitions))
        throw new Error(tr('工作流包含无效的节点配置'));
    for (const definition of definitions) {
        if (!object(definition) || typeof definition.type !== 'string' || typeof definition.label !== 'string' || typeof definition.category !== 'string' || !Array.isArray(definition.inputs) || !definition.inputs.every(item => typeof item === 'string') || !Array.isArray(definition.outputs) || !definition.outputs.every(item => typeof item === 'string') || !object(definition.defaults) || !isJson(definition.defaults))
            throw new Error(tr('工作流包含无效的节点配置'));
    }
    tools = [...tools, ...definitions];
    const nodes = [], ids = new Set();
    for (const raw of value.nodes) {
        if (!object(raw) || typeof raw.id !== 'string' || ids.has(raw.id) || typeof raw.type !== 'string' || (!tools.some(t => t.type === raw.type) && !value.workflowXml && !(object(raw.config) && typeof raw.config.engineSettingsXml === 'string' && /\bMacro\s*=/.test(raw.config.engineSettingsXml))) || typeof raw.x !== 'number' || !Number.isFinite(raw.x) || typeof raw.y !== 'number' || !Number.isFinite(raw.y) || !object(raw.config))
            throw new Error(tr('工作流包含无效或重复节点'));
        const tool = tools.find(t => t.type === raw.type);
        const config = typeof raw.config.configurationXml === 'string' ? {} : structuredClone(tool?.defaults ?? {});
        for (const [key, item] of Object.entries(raw.config)) {
            if (isJson(item))
                Object.defineProperty(config, key, { value: structuredClone(item), writable: true, enumerable: true, configurable: true });
            else
                throw new Error(tr('工作流包含无效的节点配置'));
        }
        if (!config.configurationXml && raw.type === 'TextInput' && (!strings(config, 'fields').length || config.fields.some(v => typeof v !== 'string')))
            throw new Error(tr('文本输入的字段配置无效'));
        for (const key of ['inputs', 'outputs'])
            if (raw[key] !== undefined && (!Array.isArray(raw[key]) || !raw[key].every(port => typeof port === 'string')))
                throw new Error(tr('工作流包含无效或重复节点'));
        nodes.push({ ...structuredClone(raw), id: raw.id, type: raw.type, x: raw.x, y: raw.y, config });
        ids.add(raw.id);
    }
    const graph = { ...structuredClone(value), name: value.name, nodes, edges: [] };
    for (const raw of value.edges) {
        if (!object(raw) || !['from', 'to', 'fromAnchor', 'toAnchor'].every(k => typeof raw[k] === 'string'))
            throw new Error(tr('连线格式无效'));
        const edge = raw;
        const error = graph.workflowXml ? (!ids.has(edge.from) || !ids.has(edge.to) ? '连线引用了不存在的节点' : null) : connectError(graph, edge, tools);
        if (error)
            throw new Error(error);
        graph.edges.push(edge);
    }
    return graph;
}
export function isJson(value) {
    return value === null || typeof value === 'string' || typeof value === 'boolean' || (typeof value === 'number' && Number.isFinite(value)) || (Array.isArray(value) ? value.every(isJson) : object(value) && Object.values(value).every(isJson));
}
export function exampleGraph() {
    return {
        name: '销售分析',
        nodes: [
            { id: '1', type: 'TextInput', x: 65, y: 140, config: { fields: ['Region', 'Product', 'Qty', 'Price'], rows: [['North', 'Widget', '4', '25'], ['South', 'Gadget', '9', '15'], ['North', 'Gear', '2', '70'], ['South', 'Widget', '6', '30'], ['East', 'Gear', '3', '70']] } },
            { id: '2', type: 'Formula', x: 330, y: 140, config: { expressions: [{ field: 'Total', type: 'Double', size: '', expression: '[Qty] * [Price]' }] } },
            { id: '3', type: 'Filter', x: 595, y: 140, config: { expression: '[Qty] >= 4' } },
            { id: '4', type: 'Sort', x: 860, y: 140, config: { order: [{ field: 'Total', order: 'Descending' }] } },
            { id: '5', type: 'DbFileOutput', x: 1125, y: 140, config: { file: 'sales.csv' } },
        ],
        edges: [
            { from: '1', fromAnchor: 'Output', to: '2', toAnchor: 'Input' }, { from: '2', fromAnchor: 'Output', to: '3', toAnchor: 'Input' },
            { from: '3', fromAnchor: 'True', to: '4', toAnchor: 'Input' }, { from: '4', fromAnchor: 'Output', to: '5', toAnchor: 'Input' },
        ],
    };
}

import { categories, labels, strings, entries, rows, text, upstreamFields } from './model.js';
import { el, button, byId, editGrid, readTable } from './ui.js';
const order = ['Ascending', 'Descending'];
const specs = {
    DbFileOutput: [{ key: 'file', label: '输出文件名 (.csv)' }],
    Filter: [{ key: 'expression', label: '筛选条件', expression: true }],
    Unique: [{ key: 'field', label: '去重字段', field: true }],
    Join: [{ key: 'leftField', label: '左侧关联字段', field: true }, { key: 'rightField', label: '右侧关联字段', field: true }],
    RegEx: [{ key: 'field', label: '输入字段', field: true }, { key: 'pattern', label: '正则表达式', expression: true }, { key: 'outputField', label: '输出字段名' }],
    DateTime: [{ key: 'inputField', label: '输入字段', field: true }, { key: 'outputField', label: '输出字段名' }, { key: 'format', label: '日期格式' }],
    MultiRowFormula: [{ key: 'fieldName', label: '输出字段名' }, { key: 'expression', label: '表达式', expression: true }],
    Sample: [{ key: 'mode', label: '抽样方式', options: ['First', 'Last'] }, { key: 'n', label: '行数', numeric: true }],
    CrossTab: [{ key: 'groupBy', label: '分组字段', field: true }, { key: 'header', label: '列标题字段', field: true }, { key: 'dataField', label: '值字段', field: true }, { key: 'method', label: '聚合方式', options: ['First'] }],
    RecordID: [{ key: 'fieldName', label: '记录 ID 字段名' }],
    RunningTotal: [{ key: 'field', label: '累计字段', field: true }],
    Rank: [{ key: 'field', label: '排名字段', field: true }, { key: 'order', label: '排名方向', options: order }],
    TextToColumns: [{ key: 'field', label: '输入字段', field: true }, { key: 'delimiter', label: '分隔符' }, { key: 'numFields', label: '输出列数 (1–100)', numeric: true }, { key: 'rootName', label: '输出字段前缀（默认使用输入字段名）' }],
};
export class ConfigPanel {
    graph;
    tools;
    changed;
    importFile;
    changeSheet;
    body = byId('configBody');
    serial = 0;
    constructor(graph, tools, changed, importFile, changeSheet) {
        this.graph = graph;
        this.tools = tools;
        this.changed = changed;
        this.importFile = importFile;
        this.changeSheet = changeSheet;
    }
    render(node) {
        this.body.replaceChildren();
        byId('configPanel').classList.toggle('has-selection', !!node);
        byId('btnDeleteNode').hidden = !node;
        byId('configTitle').textContent = node ? labels[node.type] ?? node.type : '节点配置';
        const tool = this.tools().find(t => t.type === node?.type);
        byId('configCategory').textContent = tool ? (categories[tool.category] ?? tool.category) + ' / ' + tool.label + ' #' + node?.id : '工作流';
        if (!node) {
            const empty = el('div', 'config-empty');
            empty.append(el('span', '', '◇'), el('p', '', '未选择节点'));
            this.body.append(empty);
            return;
        }
        switch (node.type) {
            case 'TextInput':
                this.textInput(node);
                break;
            case 'DbFileInput':
                this.fileInput(node);
                break;
            case 'Formula':
                this.list(node, 'expressions', [{ key: 'field', label: '输出字段' }, { key: 'type', label: '类型', options: ['Double', 'Int64', 'String', 'Bool', 'Date', 'DateTime'] }, { key: 'size', label: '长度（可选）' }, { key: 'expression', label: '表达式', expression: true }], () => ({ field: 'NewField', type: 'Double', size: '', expression: '[' + (this.fields(node)[0] ?? 'Col1') + ']' }));
                break;
            case 'Sort':
                this.list(node, 'order', [{ key: 'field', label: '排序字段', field: true }, { key: 'order', label: '方向', options: order }], () => ({ field: this.fields(node)[0] ?? 'Col1', order: 'Ascending' }));
                break;
            case 'Summarize':
                this.list(node, 'actions', [{ key: 'field', label: '输入字段', field: true }, { key: 'action', label: '汇总方式', options: ['GroupBy', 'Sum', 'Avg', 'Min', 'Max', 'Count'] }, { key: 'rename', label: '输出名称（可选）' }], () => ({ field: this.fields(node)[0] ?? 'Col1', action: 'GroupBy', rename: '' }));
                break;
            case 'Select':
                this.selectFields(node);
                break;
            case 'Transpose':
                this.fieldChecks(node, 'keyFields', '保留字段');
                this.fieldChecks(node, 'dataFields', '转置字段');
                break;
            case 'Union':
                this.body.append(el('p', 'muted', '按字段名称合并全部输入。'));
                break;
            default: (specs[node.type] ?? []).forEach(spec => this.field(this.body, node.config, spec, this.fields(node, spec.key)));
        }
        this.connections(node);
    }
    fields(node, key) {
        const incoming = this.graph().edges.filter(e => e.to === node.id && (node.type !== 'Join' || !key || !['leftField', 'rightField'].includes(key) || e.toAnchor === (key === 'leftField' ? 'Left' : 'Right')));
        return [...new Set(incoming.flatMap(e => upstreamFields(this.graph(), e.from, new Set(), e.fromAnchor)))];
    }
    field(parent, config, spec, fields) {
        const label = el('label', 'config-field', spec.label);
        let input;
        if (spec.options) {
            input = el('select');
            const values = [...spec.options];
            if (config[spec.key] && !values.includes(String(config[spec.key])))
                values.unshift(String(config[spec.key]));
            values.forEach(value => { const option = el('option', '', value); option.value = value; input.append(option); });
        }
        else if (spec.expression)
            input = el('textarea');
        else {
            input = el('input');
            if (spec.numeric) {
                input.type = 'number';
                input.min = '0';
                input.step = '1';
            }
        }
        input.value = String(config[spec.key] ?? '');
        input.setAttribute('aria-label', spec.label);
        if (spec.field && input instanceof HTMLInputElement && fields.length) {
            const list = el('datalist');
            list.id = 'fields-' + this.serial++;
            fields.forEach(value => { const option = el('option'); option.value = value; list.append(option); });
            input.setAttribute('list', list.id);
            label.append(list);
        }
        input.addEventListener(input instanceof HTMLSelectElement ? 'change' : 'input', () => { config[spec.key] = input.value; this.changed(); });
        label.append(input);
        parent.append(label);
        if (spec.expression && fields.length) {
            const chips = el('div', 'field-list');
            fields.forEach(value => chips.append(button('[' + value + ']', () => {
                if (input instanceof HTMLTextAreaElement) {
                    const start = input.selectionStart, end = input.selectionEnd;
                    input.setRangeText('[' + value + ']', start, end, 'end');
                    config[spec.key] = input.value;
                    this.changed();
                    input.focus();
                }
            }, '', '插入字段 ' + value)));
            parent.append(chips);
        }
        return input;
    }
    list(node, key, fields, make) {
        const values = entries(node.config, key);
        node.config[key] = values;
        values.forEach((value, index) => {
            const group = el('div', 'config-entry'), head = el('div', 'entry-heading');
            head.append(el('span', '', '#' + (index + 1)), button('×', () => { values.splice(index, 1); this.changed(); this.render(node); }, 'danger', '移除配置 ' + (index + 1)));
            group.append(head);
            fields.forEach(spec => this.field(group, value, spec, this.fields(node)));
            this.body.append(group);
        });
        this.body.append(button('+ 添加', () => { values.push(make()); this.changed(); this.render(node); }, 'secondary'));
    }
    textInput(node) {
        const header = el('div', 'section-label');
        header.append(el('span', '', '输入数据'), button('⛶', () => {
            const wide = byId('configPanel').getBoundingClientRect().width > 500;
            document.documentElement.style.setProperty('--config-width', wide ? '370px' : Math.min(650, innerWidth - 350) + 'px');
        }, 'icon-button', '展开或收起数据表'));
        this.body.append(header);
        const grid = el('div');
        this.body.append(grid);
        editGrid(grid, node.config, this.changed);
        const fields = strings(node.config, 'fields');
        if (fields.some(f => !f.trim()) || new Set(fields).size !== fields.length)
            this.body.prepend(el('div', 'inline-error', '字段名不能为空或重复。'));
    }
    fileInput(node) {
        const c = node.config;
        const zone = button('', () => this.importFile(node.id), 'upload-zone', '选择或拖入 CSV、TSV、XLSX 文件');
        zone.append(el('span', '', '↥'), el('span', '', c.file ? '替换数据文件' : '选择或拖入文件'), el('small', '', 'CSV · TSV · XLSX / 最大 20 MB'));
        zone.dataset.fileTarget = node.id;
        this.body.append(zone);
        if (!c.file)
            return;
        const info = el('div', 'file-info'), detail = el('div');
        detail.append(el('strong', '', text(c, 'name')), el('small', '', text(c, 'rowCount') + ' 行 · ' + strings(c, 'fields').length + ' 列'));
        info.append(el('span', 'tool-icon', '▤'), detail);
        this.body.append(info);
        const sheets = strings(c, 'sheets');
        if (sheets.length) {
            const label = el('label', 'config-field', '工作表'), select = el('select');
            select.setAttribute('aria-label', '工作表');
            sheets.forEach(sheet => { const option = el('option', '', sheet); option.value = sheet; select.append(option); });
            select.value = text(c, 'sheet');
            select.addEventListener('change', () => this.changeSheet(node, select.value));
            label.append(select);
            this.body.append(label);
        }
        const head = el('div', 'section-label');
        head.append(el('span', '', '数据预览'), el('small', '', '前 ' + rows(c).length + ' 行'));
        this.body.append(head);
        const wrap = el('div', 'table-wrap');
        wrap.append(readTable(strings(c, 'fields'), rows(c)));
        this.body.append(wrap);
    }
    check(parent, label, checked, change) {
        const wrap = el('label', 'check-label'), input = el('input');
        input.type = 'checkbox';
        input.checked = checked;
        input.addEventListener('change', () => { change(input.checked); this.changed(); });
        wrap.append(input, document.createTextNode(label));
        parent.append(wrap);
    }
    selectFields(node) {
        const values = entries(node.config, 'fields');
        node.config.fields = values;
        const fields = [...new Set([...this.fields(node), ...values.map(value => value.field ?? '')].filter(Boolean))];
        fields.forEach(name => this.check(this.body, name, values.find(e => e.field === name)?.selected !== 'False' && (!!node.config.includeUnknown || values.some(e => e.field === name)), selected => {
            let item = values.find(e => e.field === name);
            if (!item) {
                item = { field: name, selected: 'True' };
                values.push(item);
            }
            item.selected = selected ? 'True' : 'False';
        }));
        this.check(this.body, '保留未列出的字段', !!node.config.includeUnknown, checked => { node.config.includeUnknown = checked; this.render(node); });
        const group = el('div');
        this.field(group, { name: '' }, { key: 'name', label: '添加字段', field: true }, fields);
        const input = group.querySelector('input');
        group.append(button('+ 添加字段', () => { if (input.value.trim() && !values.some(e => e.field === input.value.trim())) {
            values.push({ field: input.value.trim(), selected: 'True' });
            this.changed();
            this.render(node);
        } }, 'secondary'));
        this.body.append(group);
    }
    fieldChecks(node, key, label) {
        this.body.append(el('div', 'section-label', label));
        const values = strings(node.config, key);
        node.config[key] = values;
        const fields = [...new Set([...this.fields(node), ...values])];
        fields.forEach(name => this.check(this.body, name, values.includes(name), checked => { if (checked)
            values.push(name);
        else
            values.splice(values.indexOf(name), 1); }));
        if (!fields.length)
            this.body.append(el('p', 'muted', '连接数据源后选择字段。'));
    }
    connections(node) {
        const section = el('div', 'config-section'), head = el('div', 'section-label', '连接');
        section.append(head);
        const edges = this.graph().edges.filter(e => e.from === node.id || e.to === node.id);
        edges.forEach(edge => {
            const source = this.graph().nodes.find(n => n.id === edge.from), target = this.graph().nodes.find(n => n.id === edge.to), row = el('div', 'connection-row');
            const title = (labels[source?.type ?? ''] ?? '') + ' #' + edge.from + ' · ' + edge.fromAnchor + ' → ' + (labels[target?.type ?? ''] ?? '') + ' #' + edge.to + ' · ' + edge.toAnchor;
            const label = el('span', '', title);
            label.title = title;
            row.append(label, button('×', () => { this.graph().edges.splice(this.graph().edges.indexOf(edge), 1); this.changed(); this.render(node); }, 'danger', '移除连线'));
            section.append(row);
        });
        if (!edges.length)
            section.append(el('p', 'muted', '暂无连接'));
        this.body.append(section);
    }
}

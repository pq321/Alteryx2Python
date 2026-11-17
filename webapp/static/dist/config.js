import { t, tr } from './i18n.js';
import { toolLabel, categoryLabel, strings, entries, rows, text, upstreamFields } from './model.js';
import { el, button, byId, editGrid, readTable } from './ui.js';
import { nodeAdvanced, parseXml } from './advanced.js';
const order = ['Ascending', 'Descending'];
const filterOperators = ['=', '!=', '>', '>=', '<', '<=', 'Contains', 'DoesNotContain', 'IsNull', 'IsNotNull', 'IsEmpty', 'IsNotEmpty'];
const unaryFilters = new Set(['IsNull', 'IsNotNull', 'IsEmpty', 'IsNotEmpty']);
function xmlElement(root, path, create = false) {
    let parent = root;
    for (const tag of path.split('/')) {
        let child = parent.querySelector(':scope > ' + tag);
        if (!child) {
            if (!create)
                return;
            child = root.ownerDocument.createElement(tag);
            parent.append(child);
        }
        parent = child;
    }
    return parent;
}
const specs = {
    DbFileOutput: [{ key: 'file', label: '输出文件名 (.csv)' }],
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
    functions;
    fieldSizes;
    previewFields;
    body = byId('configBody');
    serial = 0;
    refreshAdvanced() {
        const node = this.graph().nodes.find(item => item.id === this.body.dataset.node);
        if (!node)
            return;
        this.body.querySelectorAll('[data-config-key]').forEach(input => {
            const key = input.dataset.configKey;
            const value = key === 'configJson' ? JSON.stringify(node.config, null, 2) : text(node.config, key, key === 'configurationXml' ? '<Configuration />' : '<EngineSettings />');
            input.dispatchEvent(new CustomEvent('refresh-source', { detail: value }));
        });
    }
    constructor(graph, tools, changed, importFile, changeSheet, functions, fieldSizes, previewFields) {
        this.graph = graph;
        this.tools = tools;
        this.changed = changed;
        this.importFile = importFile;
        this.changeSheet = changeSheet;
        this.functions = functions;
        this.fieldSizes = fieldSizes;
        this.previewFields = previewFields;
    }
    render(node) {
        this.body.replaceChildren();
        this.body.dataset.node = node?.id ?? '';
        byId('configPanel').classList.toggle('has-selection', !!node);
        byId('btnDeleteNode').hidden = !node;
        byId('configTitle').textContent = node ? toolLabel(node) : tr('节点配置');
        const tool = this.tools().find(t => t.type === node?.type);
        byId('configCategory').textContent = tool ? categoryLabel(tool.category) + ' / ' + toolLabel(tool) + ' #' + node?.id : tr('工作流');
        if (!node) {
            const empty = el('div', 'config-empty');
            empty.append(el('span', '', '◇'), el('p', '', tr('未选择节点')));
            this.body.append(empty);
            return;
        }
        if (typeof tool?.configurationNote === 'string')
            this.body.append(el('p', 'muted', tr(tool.configurationNote)));
        if (typeof node.config.configurationXml === 'string') {
            this.nativeFields(node);
            nodeAdvanced(this.body, node.config, () => { this.changed(); this.render(node); });
            this.connections(node);
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
                this.list(node, 'expressions', [{ key: 'field', label: '输出字段', field: true }, { key: 'type', label: '类型', options: Object.keys(this.fieldSizes()) }, { key: 'size', label: '长度（可选）' }, { key: 'expression', label: '表达式', expression: true }], () => ({ field: 'NewField', type: 'Double', size: '', expression: '[' + (this.fields(node)[0] ?? 'Col1') + ']' }));
                break;
            case 'Filter':
                this.filter(node);
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
                this.fieldChecks(node, 'keyFields', tr('保留字段'));
                this.fieldChecks(node, 'dataFields', tr('转置字段'));
                break;
            case 'Union':
                this.body.append(el('p', 'muted', tr('按字段名称合并全部输入。')));
                break;
            default: (specs[node.type] ?? []).forEach(spec => this.field(this.body, node.config, spec, this.fields(node, spec.key)));
        }
        nodeAdvanced(this.body, node.config, () => { this.changed(); this.render(node); });
        this.connections(node);
    }
    fields(node, key, anchor) {
        const port = anchor ?? (node.type === 'Join' ? { leftField: 'Left', rightField: 'Right' }[key ?? ''] : undefined);
        const incoming = this.graph().edges.filter(e => e.to === node.id && (!port || e.toAnchor === port));
        return [...new Set(incoming.flatMap(e => this.previewFields(e.from, e.fromAnchor) ?? upstreamFields(this.graph(), e.from, new Set(), e.fromAnchor)))];
    }
    field(parent, config, spec, fields, apply = value => { config[spec.key] = value; this.changed(); }) {
        const label = el('label', 'config-field', tr(spec.label));
        let input;
        if (spec.options) {
            input = el('select');
            const values = [...spec.options];
            if (config[spec.key] && !values.includes(String(config[spec.key])))
                values.unshift(String(config[spec.key]));
            values.forEach(value => { const option = el('option', '', tr(value)); option.value = value; input.append(option); });
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
        input.setAttribute('aria-label', tr(spec.label));
        if (spec.field && input instanceof HTMLInputElement && fields.length) {
            const list = el('datalist');
            list.id = 'fields-' + this.serial++;
            fields.forEach(value => { const option = el('option'); option.value = value; list.append(option); });
            input.setAttribute('list', list.id);
            label.append(list);
        }
        input.addEventListener(input instanceof HTMLSelectElement ? 'change' : 'input', () => apply(input.value));
        label.append(input);
        parent.append(label);
        if (input instanceof HTMLTextAreaElement && spec.key !== 'pattern') {
            const insert = (value, cursorOffset = 0) => {
                input.setRangeText(value, input.selectionStart, input.selectionEnd, 'end');
                const cursor = input.selectionStart - cursorOffset;
                input.setSelectionRange(cursor, cursor);
                apply(input.value);
                input.focus();
            };
            const palette = el('div', 'expression-palette');
            for (const [label, choices, token, offset] of [
                ['插入字段', fields, (name) => '[' + name + ']', 0],
                ['插入函数', this.functions(), (name) => name + '()', 1],
            ]) {
                if (!choices.length)
                    continue;
                const select = el('select');
                const title = tr(label);
                select.setAttribute('aria-label', title);
                select.append(el('option', '', title));
                for (const value of choices) {
                    const option = el('option', '', value);
                    option.value = value;
                    select.append(option);
                }
                select.addEventListener('change', () => { if (select.selectedIndex)
                    insert(token(select.value), offset); select.selectedIndex = 0; });
                palette.append(select);
            }
            if (palette.childNodes.length)
                parent.append(palette);
        }
        return input;
    }
    filter(node, native) {
        const config = native ? { mode: native.mode, field: native.field, operator: native.operator, operand: native.operand, expression: native.expression } : node.config;
        const fields = this.fields(node);
        const update = (key, value) => {
            if (native)
                native.update(key, value);
            else {
                config[key] = value;
                this.changed();
            }
            if (key === 'mode' || key === 'operator')
                this.render(node);
        };
        const modes = [['Simple', '基本筛选'], ['Custom', '自定义筛选']];
        const group = el('div', 'filter-modes');
        for (const [mode, label] of modes) {
            const wrap = el('label', 'check-label'), input = el('input');
            input.type = 'radio';
            input.name = 'filter-mode';
            input.checked = (config.mode ?? 'Custom') === mode;
            input.addEventListener('change', () => update('mode', mode));
            wrap.append(input, document.createTextNode(tr(label)));
            group.append(wrap);
        }
        this.body.append(group);
        const settings = config.mode === 'Simple' ? [
            { key: 'field', label: '输入字段', field: true }, { key: 'operator', label: '运算符', options: filterOperators },
            ...(!unaryFilters.has(String(config.operator)) ? [
                ...(!native && !['Contains', 'DoesNotContain'].includes(String(config.operator)) ?
                    [{ key: 'operandType', label: '比较值类型', options: ['Text', 'Number'] }] : []),
                { key: 'operand', label: '比较值' },
            ] : []),
        ] : [{ key: 'expression', label: '筛选条件', expression: true }];
        for (const spec of settings)
            this.field(this.body, { operator: '=', operandType: 'Text', ...config }, spec, fields, value => update(spec.key, value));
    }
    list(node, key, fields, make) {
        const values = entries(node.config, key);
        node.config[key] = values;
        values.forEach((value, index) => {
            const group = el('div', 'config-entry'), head = el('div', 'entry-heading');
            head.append(el('span', '', '#' + (index + 1)), button('×', () => { values.splice(index, 1); this.changed(); this.render(node); }, 'danger', t('移除配置 {n}', { n: index + 1 })));
            group.append(head);
            const upstream = this.fields(node);
            if (node.type === 'Formula')
                upstream.push(...values.slice(0, index).map(item => item.field).filter(Boolean));
            fields.forEach(spec => this.field(group, value, spec, [...new Set(upstream)], next => {
                value[spec.key] = next;
                if (node.type === 'Formula' && spec.key === 'type')
                    value.size = String(this.fieldSizes()[next] ?? '');
                this.changed();
                if (node.type === 'Formula' && spec.key === 'type')
                    this.render(node);
            }));
            this.body.append(group);
        });
        this.body.append(button(tr('+ 添加'), () => { values.push(make()); this.changed(); this.render(node); }, 'secondary'));
    }
    textInput(node) {
        const header = el('div', 'section-label');
        header.append(el('span', '', tr('输入数据')), button('⛶', () => {
            const wide = byId('configPanel').getBoundingClientRect().width > 500;
            document.documentElement.style.setProperty('--config-width', wide ? '370px' : Math.min(650, innerWidth - 350) + 'px');
        }, 'icon-button', tr('展开或收起数据表')));
        this.body.append(header);
        const grid = el('div');
        this.body.append(grid);
        editGrid(grid, node.config, this.changed);
        const fields = strings(node.config, 'fields');
        if (fields.some(f => !f.trim()) || new Set(fields).size !== fields.length)
            this.body.prepend(el('div', 'inline-error', tr('字段名不能为空或重复。')));
    }
    fileInput(node) {
        const c = node.config;
        const zone = button('', () => this.importFile(node.id), 'upload-zone', tr('选择或拖入 CSV、TSV、XLSX 文件'));
        zone.append(el('span', '', '↥'), el('span', '', c.file ? tr('替换数据文件') : tr('选择或拖入文件')), el('small', '', tr('CSV · TSV · XLSX / 最大 20 MB')));
        zone.dataset.fileTarget = node.id;
        this.body.append(zone);
        if (!c.file)
            return;
        const info = el('div', 'file-info'), detail = el('div');
        detail.append(el('strong', '', text(c, 'name')), el('small', '', t('{rows} 行 · {columns} 列', { rows: text(c, 'rowCount'), columns: strings(c, 'fields').length })));
        info.append(el('span', 'tool-icon', '▤'), detail);
        this.body.append(info);
        const sheets = strings(c, 'sheets');
        if (sheets.length) {
            const label = el('label', 'config-field', tr('工作表')), select = el('select');
            select.setAttribute('aria-label', tr('工作表'));
            sheets.forEach(sheet => { const option = el('option', '', sheet); option.value = sheet; select.append(option); });
            select.value = text(c, 'sheet');
            select.addEventListener('change', () => this.changeSheet(node, select.value));
            label.append(select);
            this.body.append(label);
        }
        const head = el('div', 'section-label');
        head.append(el('span', '', tr('数据预览')), el('small', '', t('前 {n} 行', { n: rows(c).length })));
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
        this.check(this.body, tr('保留未列出的字段'), !!node.config.includeUnknown, checked => { node.config.includeUnknown = checked; this.render(node); });
        for (const name of fields) {
            const item = values.find(value => value.field === name) ?? { field: name, selected: node.config.includeUnknown ? 'True' : 'False' };
            const details = el('details', 'select-field');
            details.append(el('summary', '', item.field ?? ''));
            details.addEventListener('input', () => { if (!values.includes(item))
                values.push(item); }, { capture: true });
            details.addEventListener('change', () => { if (!values.includes(item))
                values.push(item); }, { capture: true });
            for (const spec of [{ key: 'rename', label: '重命名' }, { key: 'type', label: '类型', options: ['', 'Byte', 'Int16', 'Int32', 'Int64', 'FixedDecimal', 'Float', 'Double', 'String', 'V_String', 'WString', 'V_WString', 'Bool', 'Date', 'DateTime', 'Time'] }, { key: 'size', label: '长度（可选）', numeric: true }, { key: 'scale', label: '小数位', numeric: true }])
                this.field(details, item, spec, []);
            this.body.append(details);
        }
        const group = el('div');
        this.field(group, { name: '' }, { key: 'name', label: '添加字段', field: true }, fields);
        const input = group.querySelector('input');
        group.append(button(tr('+ 添加字段'), () => { if (input.value.trim() && !values.some(e => e.field === input.value.trim())) {
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
            this.body.append(el('p', 'muted', tr('连接数据源后选择字段。')));
    }
    connections(node) {
        const section = el('div', 'config-section'), head = el('div', 'section-label', tr('连接'));
        section.append(head);
        const edges = this.graph().edges.filter(e => e.from === node.id || e.to === node.id);
        edges.forEach(edge => {
            const source = this.graph().nodes.find(n => n.id === edge.from), target = this.graph().nodes.find(n => n.id === edge.to), row = el('div', 'connection-row');
            const title = toolLabel(source) + ' #' + edge.from + ' · ' + edge.fromAnchor + ' → ' + toolLabel(target) + ' #' + edge.to + ' · ' + edge.toAnchor;
            const label = el('span', '', title);
            label.title = title;
            row.append(label, button('×', () => { this.graph().edges.splice(this.graph().edges.indexOf(edge), 1); this.changed(); this.render(node); }, 'danger', tr('移除连线')));
            section.append(row);
        });
        if (!edges.length)
            section.append(el('p', 'muted', tr('暂无连接')));
        this.body.append(section);
    }
    nativeFormula(root, node, save) {
        const formulas = Array.from(xmlElement(root, 'FormulaFields')?.querySelectorAll(':scope > FormulaField') ?? []);
        const commit = () => { save(); this.render(node); };
        const fields = this.fields(node);
        for (const [index, element] of formulas.entries()) {
            const group = el('div', 'config-entry'), head = el('div', 'entry-heading');
            head.append(el('span', '', '#' + (index + 1)), button('×', () => { element.remove(); commit(); }, 'danger', t('移除配置 {n}', { n: index + 1 })));
            group.append(head);
            const previous = formulas[index - 1];
            if (previous)
                head.append(button('↑', () => { previous.before(element); commit(); }, 'secondary', tr('上移')));
            const available = [...new Set([...fields, ...formulas.slice(0, index).map(row => row.getAttribute('field') ?? '').filter(Boolean)])];
            const specs = [
                { key: 'field', label: '输出字段', field: true }, { key: 'type', label: '类型', options: ['', ...Object.keys(this.fieldSizes())] },
                { key: 'size', label: '长度（可选）' }, { key: 'scale', label: '小数位' }, { key: 'expression', label: '表达式', expression: true },
            ];
            for (const spec of specs)
                this.field(group, { [spec.key]: element.getAttribute(spec.key) }, spec, available, next => {
                    if (next || spec.key === 'expression')
                        element.setAttribute(spec.key, next);
                    else
                        element.removeAttribute(spec.key);
                    if (spec.key === 'type') {
                        const width = this.fieldSizes()[next];
                        if (width !== undefined)
                            element.setAttribute('size', String(width));
                        else
                            element.removeAttribute('size');
                        commit();
                    }
                    else
                        save();
                });
            this.body.append(group);
        }
        this.body.append(button(tr('+ 添加'), () => {
            const field = root.ownerDocument.createElement('FormulaField');
            field.setAttribute('field', 'NewField');
            field.setAttribute('type', 'Double');
            field.setAttribute('size', String(this.fieldSizes().Double ?? '8'));
            field.setAttribute('expression', fields.length ? '[' + fields[0] + ']' : '0');
            xmlElement(root, 'FormulaFields', true).append(field);
            commit();
        }, 'secondary'));
    }
    reportFields(root, path, node, label, save) {
        const group = el('div', 'config-entry');
        group.append(el('div', 'section-label', tr(label)));
        const fields = this.fields(node);
        for (const item of Array.from(xmlElement(root, path)?.querySelectorAll(':scope > Field') ?? [])) {
            const attr = item.hasAttribute('field') && !item.hasAttribute('name') ? 'field' : 'name';
            this.field(group, { field: item.getAttribute(attr) }, { key: 'field', label, field: true }, fields, next => { item.setAttribute(attr, next); save(); });
            if (path !== 'GroupingFields')
                this.check(group, tr('启用'), item.getAttribute('selected')?.toLowerCase() !== 'false', checked => { item.setAttribute('selected', checked ? 'True' : 'False'); save(); });
            group.append(button('×', () => { item.remove(); save(); this.render(node); }, 'danger', tr('删除')));
        }
        group.append(button(tr('+ 添加字段'), () => {
            const item = root.ownerDocument.createElement('Field');
            item.setAttribute('name', '');
            xmlElement(root, path, true).append(item);
            save();
            this.render(node);
        }, 'secondary'));
        this.body.append(group);
    }
    appendFields(root, node, save) {
        const path = 'SelectConfiguration/Configuration';
        const select = xmlElement(root, path);
        const existing = Array.from(select?.querySelectorAll('SelectFields > SelectField') ?? []);
        const references = [
            ...this.fields(node, undefined, 'Targets').map(name => 'Target_' + name),
            ...this.fields(node, undefined, 'Source').map(name => 'Source_' + name),
        ];
        const recorded = existing.map(field => field.getAttribute('field') ?? '');
        const names = [...new Set([...recorded.filter(Boolean), ...references, '*Unknown'])];
        const includeUnknown = !existing.length || existing.some(field => field.getAttribute('field') === '*Unknown' && field.getAttribute('selected')?.toLowerCase() !== 'false');
        const fieldNode = (name, selected) => {
            const field = root.ownerDocument.createElement('SelectField');
            field.setAttribute('field', name);
            field.setAttribute('selected', selected ? 'True' : 'False');
            return field;
        };
        for (const name of names) {
            const original = existing.find(field => field.getAttribute('field') === name);
            const details = el('details', 'select-field');
            const enabled = original ? original.getAttribute('selected')?.toLowerCase() !== 'false' : includeUnknown;
            const edit = () => {
                if (original)
                    return original;
                const list = xmlElement(root, path + '/SelectFields', true);
                const current = Array.from(list.children).find(field => field.getAttribute('field') === name);
                if (current)
                    return current;
                if (!existing.length && name !== '*Unknown' && !list.querySelector('[field="*Unknown"]'))
                    list.append(fieldNode('*Unknown', true));
                const entry = fieldNode(name, enabled);
                list.append(entry);
                return entry;
            };
            details.append(el('summary', '', name === '*Unknown' ? tr('保留未列出的字段') : name));
            this.check(details, tr('启用'), enabled, next => { edit().setAttribute('selected', next ? 'True' : 'False'); save(); if (name === '*Unknown')
                this.render(node); });
            const previous = original?.previousElementSibling;
            if (previous?.tagName === 'SelectField')
                details.append(button('↑', () => {
                    previous.before(original);
                    xmlElement(root, path + '/OrderChanged', true).setAttribute('value', 'True');
                    save();
                    this.render(node);
                }, 'secondary', tr('上移')));
            if (name !== '*Unknown') {
                for (const spec of [{ key: 'rename', label: '重命名' },
                    { key: 'type', label: '类型', options: ['', ...Object.keys(this.fieldSizes())] }, { key: 'size', label: '长度（可选）' }]) {
                    this.field(details, { [spec.key]: original?.getAttribute(spec.key) ?? '' }, spec, [], next => {
                        const field = edit();
                        if (next)
                            field.setAttribute(spec.key, next);
                        else
                            field.removeAttribute(spec.key);
                        if (spec.key === 'type') {
                            const width = this.fieldSizes()[next];
                            if (width !== undefined)
                                field.setAttribute('size', String(width));
                            else
                                field.removeAttribute('size');
                        }
                        save();
                        if (spec.key === 'type') {
                            this.render(node);
                        }
                    });
                }
            }
            this.body.append(details);
        }
    }
    nativeFields(node) {
        const config = node.config;
        let document;
        try {
            document = parseXml(String(config.configurationXml), 'Configuration');
        }
        catch {
            return;
        }
        const save = () => { config.configurationXml = new XMLSerializer().serializeToString(document); this.changed(); };
        const root = document.documentElement;
        const value = (path, fallback = '') => {
            const element = xmlElement(root, path);
            return element?.getAttribute('value') ?? element?.textContent ?? fallback;
        };
        const set = (path, value) => {
            const element = xmlElement(root, path, true);
            if (element.hasAttribute('value'))
                element.setAttribute('value', value);
            else
                element.textContent = value;
        };
        const setting = (path, label, spec = {}, fallback = '') => {
            this.field(this.body, { value: value(path, fallback) }, { key: 'value', label, ...spec }, this.fields(node), next => { set(path, next); save(); });
        };
        if (node.type === 'Filter') {
            const paths = { mode: 'Mode', field: 'Simple/Field', operator: 'Simple/Operator', operand: 'Simple/Operands/Operand', expression: 'Expression' };
            this.filter(node, { mode: value(paths.mode, 'Custom'), field: value(paths.field), operator: value(paths.operator, '='), operand: value(paths.operand), expression: value(paths.expression),
                update: (key, next) => { set(paths[key], next); if ((key === 'mode' ? next : value('Mode')) === 'Simple')
                    set('Expression', ''); save(); } });
        }
        if (node.type === 'DynamicInput') {
            setting('Mode', '动态输入模式', { options: ['ReadList'] }, 'ReadList');
            setting('ReadList_Field', '路径字段', { field: true });
            setting('ReadList_Type', '路径操作', { options: ['Path'] }, 'Path');
            setting('ErrorBehaviour', '跳过文件时', { options: ['Warning', 'Error'] }, 'Error');
            const filePath = 'InputConfiguration/Configuration/File';
            this.field(this.body, { file: value(filePath) }, { key: 'file', label: '数据源模板' }, [], next => {
                const file = xmlElement(root, filePath, true);
                file.setAttribute('FileFormat', /\.xlsx(?:\|\|\||$)/i.test(next) ? '25' : '0');
                file.textContent = next;
                save();
            });
        }
        if (node.type === 'PortfolioComposerLayout') {
            setting('GroupingMode', '布局方式', { options: ['', 'PerGroup'] });
            setting('Orientation', '布局方向', { options: ['', 'V', 'H'] });
            setting('Separator', '分隔方式', { options: ['', 'Breaking'] });
            setting('SectionNameForGroup', '分区名称字段', { field: true });
            this.reportFields(root, 'GroupingFields', node, '分组字段', save);
            this.reportFields(root, 'LayoutFields', node, '报表字段', save);
        }
        if (node.type === 'PortfolioComposerTable') {
            setting('TableMode', '表格模式', { options: ['Basic'] }, 'Basic');
            this.reportFields(root, 'GroupingFields', node, '分组字段', save);
            this.reportFields(root, 'TableFields', node, '报表字段', save);
        }
        if (node.type === 'PortfolioComposerRender') {
            setting('OutputFile', '输出文件');
            setting('DataField', '报表字段', { field: true });
            this.check(this.body, tr('按字段生成文件'), value('BatchMode').toLowerCase() === 'true', checked => {
                xmlElement(root, 'BatchMode', true).setAttribute('value', checked ? 'True' : 'False');
                save();
            });
            setting('GroupField', '分组字段', { field: true });
            setting('FilenameModifier', '文件名操作', { options: ['', 'Prepend', 'ReplacePath'] });
        }
        if (node.type === 'AppendFields') {
            setting('CartesianMode', '多对多追加', { options: ['Error', 'Warn', 'Allow'] }, 'Error');
            this.appendFields(root, node, save);
        }
        if (node.type === 'FuzzyMatch') {
            setting('RecordIdField', '记录 ID 字段名', { field: true });
            const list = el('div', 'config-entry'), fields = this.fields(node);
            for (const item of root.querySelectorAll('MatchFields > MatchField')) {
                const name = xmlElement(item, 'FieldName');
                this.field(list, { field: name?.textContent ?? '' }, { key: 'field', label: '匹配字段', field: true }, fields, next => { xmlElement(item, 'FieldName', true).textContent = next; save(); });
                list.append(button('×', () => { item.remove(); save(); this.render(node); }, 'danger', tr('删除')));
            }
            list.append(button(tr('+ 添加字段'), () => {
                const entry = root.ownerDocument.createElement('MatchField');
                xmlElement(entry, 'FieldName', true).textContent = fields[0] ?? '';
                xmlElement(entry, 'Style/KeyGeneration/KeyFunction', true).textContent = 'WholeField';
                xmlElement(entry, 'Style/Match/MatchFunction', true).textContent = 'None';
                xmlElement(root, 'MatchFields', true).append(entry);
                save();
                this.render(node);
            }, 'secondary'));
            this.body.append(list);
        }
        const common = node.type === 'JupyterCode' ? [['productionModeScript', 'Python 代码', true]] : node.type === 'RunCommand' ? [['ProgramName', '程序', false], ['Arguments', '命令参数', false], ['WorkingDir', '工作目录', false]] : node.type === 'Email' ? [['From', '发件人', false], ['To', '收件人', false], ['Subject', '主题', false], ['Body', '正文', true], ['SMTPServer', 'SMTP 服务器', false]] : [];
        for (const [tag, label, multiline] of common) {
            const wrap = el('label', 'config-field', tr(label)), input = multiline ? el('textarea', 'code-editor') : el('input');
            input.value = document.querySelector(tag)?.textContent ?? '';
            input.setAttribute('aria-label', tr(label));
            input.addEventListener('input', () => { let element = document.querySelector(tag); if (!element) {
                element = document.createElement(tag);
                document.documentElement.append(element);
            } element.textContent = input.value; save(); });
            wrap.append(input);
            this.body.append(wrap);
        }
        if (node.type === 'TextInput') {
            const record = document.querySelector('Fields') ?? document.querySelector('RecordInfo'), data = document.querySelector('Data');
            if (record && data) {
                const original = Array.from(record.querySelectorAll('Field'));
                const table = { fields: original.map(field => field.getAttribute('name') ?? ''), rows: Array.from(data.querySelectorAll('r')).map(row => Array.from(row.querySelectorAll('c')).map(cell => cell.textContent ?? '')) };
                editGrid(this.body, table, () => {
                    record.querySelectorAll(':scope > Field').forEach(field => field.remove());
                    record.append(...strings(table, 'fields').map((name, index) => { const field = (original.find(item => item.getAttribute('name') === name) ?? original[index])?.cloneNode(true) ?? document.createElement('Field'); field.setAttribute('name', name); if (!field.hasAttribute('type')) {
                        field.setAttribute('type', 'V_WString');
                        field.setAttribute('size', '254');
                    } return field; }));
                    data.querySelectorAll(':scope > r').forEach(row => row.remove());
                    data.append(...rows(table).map(row => { const item = document.createElement('r'); row.forEach(value => { const cell = document.createElement('c'); cell.textContent = String(value ?? ''); item.append(cell); }); return item; }));
                    document.querySelector('NumRows')?.setAttribute('value', String(rows(table).length));
                    save();
                });
            }
        }
        if (node.type === 'Formula') {
            this.nativeFormula(root, node, save);
        }
        if (node.type === 'Select') {
            for (const element of Array.from(document.querySelectorAll(node.type === 'Select' ? 'SelectField' : 'FormulaField'))) {
                const details = el('details', 'select-field'), name = element.getAttribute('field') ?? '';
                details.append(el('summary', '', name));
                const attrs = node.type === 'Select' ? ['selected', 'rename', 'type', 'size', 'scale'] : ['field', 'type', 'size', 'scale', 'expression'];
                const labels = { selected: '启用', rename: '重命名', type: '类型', size: '长度（可选）', scale: '小数位', field: '输出字段', expression: '表达式' };
                for (const attr of attrs) {
                    const label = tr(labels[attr] ?? attr), wrap = el('label', 'config-field', label), input = attr === 'expression' ? el('textarea') : el('input');
                    input.value = element.getAttribute(attr) ?? '';
                    input.setAttribute('aria-label', label);
                    if (attr === 'selected' && input instanceof HTMLInputElement) {
                        input.type = 'checkbox';
                        input.checked = input.value !== 'False';
                    }
                    input.addEventListener('input', () => { element.setAttribute(attr, input instanceof HTMLInputElement && input.type === 'checkbox' ? (input.checked ? 'True' : 'False') : input.value); save(); });
                    wrap.append(input);
                    details.append(wrap);
                }
                this.body.append(details);
            }
        }
        for (const [tag, label, multiline] of [['cmd_Program', '程序', false], ['Command', '程序', false], ['CommandArguments', '命令参数', false], ['Script', 'Python 代码', true], ['PythonCode', 'Python 代码', true]]) {
            const element = document.querySelector(tag);
            if (!element || element.children.length)
                continue;
            const wrap = el('label', 'config-field', tr(label)), input = multiline ? el('textarea', 'code-editor') : el('input');
            input.value = element.textContent ?? '';
            input.setAttribute('aria-label', tr(label));
            input.addEventListener('input', () => { element.textContent = input.value; save(); });
            wrap.append(input);
            this.body.append(wrap);
        }
        if (typeof config.engineSettingsXml === 'string') {
            try {
                const engine = parseXml(config.engineSettingsXml, 'EngineSettings'), path = engine.documentElement.getAttribute('Macro');
                if (path !== null) {
                    const wrap = el('label', 'config-field', t('宏路径')), input = el('input');
                    input.value = path;
                    input.setAttribute('aria-label', t('宏路径'));
                    input.addEventListener('input', () => { engine.documentElement.setAttribute('Macro', input.value); config.engineSettingsXml = new XMLSerializer().serializeToString(engine); this.changed(); });
                    wrap.append(input);
                    this.body.append(wrap);
                }
            }
            catch { /* The full XML editor displays invalid source without replacing it. */ }
        }
    }
}

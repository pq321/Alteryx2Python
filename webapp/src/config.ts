import {t, tr} from './i18n.js';
import {type Config, type Entry, type Graph, type WorkflowNode, type Tool, toolLabel, categoryLabel, strings, entries, rows, text, upstreamFields} from './model.js';
import {el, button, byId, editGrid, readTable} from './ui.js';
import {nodeAdvanced, parseXml} from './advanced.js';
type FieldSpec = {key: string; label: string; options?: string[]; expression?: boolean; numeric?: boolean; field?: boolean};
const order = ['Ascending', 'Descending'];
const specs: Record<string, FieldSpec[]> = {
  DbFileOutput: [{key: 'file', label: '输出文件名 (.csv)'}],
  Filter: [{key: 'expression', label: '筛选条件', expression: true}],
  Unique: [{key: 'field', label: '去重字段', field: true}],
  Join: [{key: 'leftField', label: '左侧关联字段', field: true}, {key: 'rightField', label: '右侧关联字段', field: true}],
  RegEx: [{key: 'field', label: '输入字段', field: true}, {key: 'pattern', label: '正则表达式', expression: true}, {key: 'outputField', label: '输出字段名'}],
  DateTime: [{key: 'inputField', label: '输入字段', field: true}, {key: 'outputField', label: '输出字段名'}, {key: 'format', label: '日期格式'}],
  MultiRowFormula: [{key: 'fieldName', label: '输出字段名'}, {key: 'expression', label: '表达式', expression: true}],
  Sample: [{key: 'mode', label: '抽样方式', options: ['First', 'Last']}, {key: 'n', label: '行数', numeric: true}],
  CrossTab: [{key: 'groupBy', label: '分组字段', field: true}, {key: 'header', label: '列标题字段', field: true}, {key: 'dataField', label: '值字段', field: true}, {key: 'method', label: '聚合方式', options: ['First']}],
  RecordID: [{key: 'fieldName', label: '记录 ID 字段名'}],
  RunningTotal: [{key: 'field', label: '累计字段', field: true}],
  Rank: [{key: 'field', label: '排名字段', field: true}, {key: 'order', label: '排名方向', options: order}],
  TextToColumns: [{key: 'field', label: '输入字段', field: true}, {key: 'delimiter', label: '分隔符'}, {key: 'numFields', label: '输出列数 (1–100)', numeric: true}, {key: 'rootName', label: '输出字段前缀（默认使用输入字段名）'}],
};
export class ConfigPanel {
  private body = byId('configBody');
  private serial = 0;
  refreshAdvanced(): void {
    const node = this.graph().nodes.find(item => item.id === this.body.dataset.node);
    if (!node) return;
    this.body.querySelectorAll<HTMLTextAreaElement>('[data-config-key]').forEach(input => {
      const key = input.dataset.configKey!;
      const value = key === 'configJson' ? JSON.stringify(node.config, null, 2) : text(node.config, key, key === 'configurationXml' ? '<Configuration />' : '<EngineSettings />');
      input.dispatchEvent(new CustomEvent('refresh-source', {detail: value}));
    });
  }
  constructor(private graph: () => Graph, private tools: () => Tool[], private changed: () => void, private importFile: (target: string) => void, private changeSheet: (node: WorkflowNode, sheet: string) => void) {}
  render(node: WorkflowNode | undefined): void {
    this.body.replaceChildren(); this.body.dataset.node = node?.id ?? ''; byId('configPanel').classList.toggle('has-selection', !!node); byId('btnDeleteNode').hidden = !node;
    byId('configTitle').textContent = node ? toolLabel(node) : tr('节点配置');
    const tool = this.tools().find(t => t.type === node?.type);
    byId('configCategory').textContent = tool ? categoryLabel(tool.category) + ' / ' + toolLabel(tool) + ' #' + node?.id : tr('工作流');
    if (!node) { const empty = el('div', 'config-empty'); empty.append(el('span', '', '◇'), el('p', '', tr('未选择节点'))); this.body.append(empty); return; }
    if (typeof node.config.configurationXml === 'string') {
      this.nativeFields(node); nodeAdvanced(this.body, node.config, () => { this.changed(); this.render(node); }); this.connections(node); return;
    }
    switch (node.type) {
      case 'TextInput': this.textInput(node); break;
      case 'DbFileInput': this.fileInput(node); break;
      case 'Formula': this.list(node, 'expressions', [{key: 'field', label: '输出字段'}, {key: 'type', label: '类型', options: ['Double', 'Int64', 'String', 'Bool', 'Date', 'DateTime']}, {key: 'size', label: '长度（可选）'}, {key: 'expression', label: '表达式', expression: true}], () => ({field: 'NewField', type: 'Double', size: '', expression: '[' + (this.fields(node)[0] ?? 'Col1') + ']'})); break;
      case 'Sort': this.list(node, 'order', [{key: 'field', label: '排序字段', field: true}, {key: 'order', label: '方向', options: order}], () => ({field: this.fields(node)[0] ?? 'Col1', order: 'Ascending'})); break;
      case 'Summarize': this.list(node, 'actions', [{key: 'field', label: '输入字段', field: true}, {key: 'action', label: '汇总方式', options: ['GroupBy', 'Sum', 'Avg', 'Min', 'Max', 'Count']}, {key: 'rename', label: '输出名称（可选）'}], () => ({field: this.fields(node)[0] ?? 'Col1', action: 'GroupBy', rename: ''})); break;
      case 'Select': this.selectFields(node); break;
      case 'Transpose': this.fieldChecks(node, 'keyFields', tr('保留字段')); this.fieldChecks(node, 'dataFields', tr('转置字段')); break;
      case 'Union': this.body.append(el('p', 'muted', tr('按字段名称合并全部输入。'))); break;
      default: (specs[node.type] ?? []).forEach(spec => this.field(this.body, node.config, spec, this.fields(node, spec.key)));
    }
    nodeAdvanced(this.body, node.config, () => { this.changed(); this.render(node); }); this.connections(node);
  }
  private fields(node: WorkflowNode, key?: string): string[] {
    const incoming = this.graph().edges.filter(e => e.to === node.id && (node.type !== 'Join' || !key || !['leftField', 'rightField'].includes(key) || e.toAnchor === (key === 'leftField' ? 'Left' : 'Right')));
    return [...new Set(incoming.flatMap(e => upstreamFields(this.graph(), e.from, new Set(), e.fromAnchor)))];
  }
  private field(parent: HTMLElement, config: Config | Entry, spec: FieldSpec, fields: string[]): HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement {
    const label = el('label', 'config-field', tr(spec.label)); let input: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
    if (spec.options) {
      input = el('select'); const values = [...spec.options]; if (config[spec.key] && !values.includes(String(config[spec.key]))) values.unshift(String(config[spec.key]));
      values.forEach(value => { const option = el('option', '', value); option.value = value; input.append(option); });
    } else if (spec.expression) input = el('textarea');
    else { input = el('input'); if (spec.numeric) { input.type = 'number'; input.min = '0'; input.step = '1'; } }
    input.value = String(config[spec.key] ?? ''); input.setAttribute('aria-label', tr(spec.label));
    if (spec.field && input instanceof HTMLInputElement && fields.length) {
      const list = el('datalist'); list.id = 'fields-' + this.serial++; fields.forEach(value => { const option = el('option'); option.value = value; list.append(option); }); input.setAttribute('list', list.id); label.append(list);
    }
    input.addEventListener(input instanceof HTMLSelectElement ? 'change' : 'input', () => { config[spec.key] = input.value; this.changed(); });
    label.append(input); parent.append(label);
    if (spec.expression && fields.length) {
      const chips = el('div', 'field-list'); fields.forEach(value => chips.append(button('[' + value + ']', () => {
        if (input instanceof HTMLTextAreaElement) { const start = input.selectionStart, end = input.selectionEnd; input.setRangeText('[' + value + ']', start, end, 'end'); config[spec.key] = input.value; this.changed(); input.focus(); }
      }, '', t('插入字段 {name}', {name: value})))); parent.append(chips);
    }
    return input;
  }
  private list(node: WorkflowNode, key: string, fields: FieldSpec[], make: () => Entry): void {
    const values = entries(node.config, key); node.config[key] = values;
    values.forEach((value, index) => {
      const group = el('div', 'config-entry'), head = el('div', 'entry-heading'); head.append(el('span', '', '#' + (index + 1)), button('×', () => { values.splice(index, 1); this.changed(); this.render(node); }, 'danger', t('移除配置 {n}', {n: index + 1}))); group.append(head);
      fields.forEach(spec => this.field(group, value, spec, this.fields(node))); this.body.append(group);
    });
    this.body.append(button(tr('+ 添加'), () => { values.push(make()); this.changed(); this.render(node); }, 'secondary'));
  }
  private textInput(node: WorkflowNode): void {
    const header = el('div', 'section-label'); header.append(el('span', '', tr('输入数据')), button('⛶', () => {
      const wide = byId('configPanel').getBoundingClientRect().width > 500;
      document.documentElement.style.setProperty('--config-width', wide ? '370px' : Math.min(650, innerWidth - 350) + 'px');
    }, 'icon-button', tr('展开或收起数据表'))); this.body.append(header);
    const grid = el('div'); this.body.append(grid); editGrid(grid, node.config, this.changed);
    const fields = strings(node.config, 'fields');
    if (fields.some(f => !f.trim()) || new Set(fields).size !== fields.length) this.body.prepend(el('div', 'inline-error', tr('字段名不能为空或重复。')));
  }
  private fileInput(node: WorkflowNode): void {
    const c = node.config;
    const zone = button('', () => this.importFile(node.id), 'upload-zone', tr('选择或拖入 CSV、TSV、XLSX 文件'));
    zone.append(el('span', '', '↥'), el('span', '', c.file ? tr('替换数据文件') : tr('选择或拖入文件')), el('small', '', tr('CSV · TSV · XLSX / 最大 20 MB')));
    zone.dataset.fileTarget = node.id; this.body.append(zone);
    if (!c.file) return;
    const info = el('div', 'file-info'), detail = el('div'); detail.append(el('strong', '', text(c, 'name')), el('small', '', t('{rows} 行 · {columns} 列', {rows: text(c, 'rowCount'), columns: strings(c, 'fields').length}))); info.append(el('span', 'tool-icon', '▤'), detail); this.body.append(info);
    const sheets = strings(c, 'sheets');
    if (sheets.length) {
      const label = el('label', 'config-field', tr('工作表')), select = el('select'); select.setAttribute('aria-label', tr('工作表')); sheets.forEach(sheet => { const option = el('option', '', sheet); option.value = sheet; select.append(option); }); select.value = text(c, 'sheet'); select.addEventListener('change', () => this.changeSheet(node, select.value)); label.append(select); this.body.append(label);
    }
    const head = el('div', 'section-label'); head.append(el('span', '', tr('数据预览')), el('small', '', t('前 {n} 行', {n: rows(c).length}))); this.body.append(head);
    const wrap = el('div', 'table-wrap'); wrap.append(readTable(strings(c, 'fields'), rows(c))); this.body.append(wrap);
  }
  private check(parent: HTMLElement, label: string, checked: boolean, change: (value: boolean) => void): void {
    const wrap = el('label', 'check-label'), input = el('input'); input.type = 'checkbox'; input.checked = checked; input.addEventListener('change', () => { change(input.checked); this.changed(); }); wrap.append(input, document.createTextNode(label)); parent.append(wrap);
  }
  private selectFields(node: WorkflowNode): void {
    const values = entries(node.config, 'fields'); node.config.fields = values;
    const fields = [...new Set([...this.fields(node), ...values.map(value => value.field ?? '')].filter(Boolean))];
    fields.forEach(name => this.check(this.body, name, values.find(e => e.field === name)?.selected !== 'False' && (!!node.config.includeUnknown || values.some(e => e.field === name)), selected => {
      let item = values.find(e => e.field === name); if (!item) { item = {field: name, selected: 'True'}; values.push(item); } item.selected = selected ? 'True' : 'False';
    }));
    this.check(this.body, tr('保留未列出的字段'), !!node.config.includeUnknown, checked => { node.config.includeUnknown = checked; this.render(node); });
    for (const name of fields) {
      const item = values.find(value => value.field === name) ?? {field: name, selected: node.config.includeUnknown ? 'True' : 'False'};
      const details = el('details', 'select-field'); details.append(el('summary', '', item.field ?? ''));
      details.addEventListener('input', () => { if (!values.includes(item)) values.push(item); }, {capture: true});
      details.addEventListener('change', () => { if (!values.includes(item)) values.push(item); }, {capture: true});
      for (const spec of [{key: 'rename', label: '重命名'}, {key: 'type', label: '类型', options: ['', 'Byte', 'Int16', 'Int32', 'Int64', 'FixedDecimal', 'Float', 'Double', 'String', 'V_String', 'WString', 'V_WString', 'Bool', 'Date', 'DateTime', 'Time']}, {key: 'size', label: '长度（可选）', numeric: true}, {key: 'scale', label: '小数位', numeric: true}]) this.field(details, item, spec, []);
      this.body.append(details);
    }
    const group = el('div'); this.field(group, {name: ''}, {key: 'name', label: '添加字段', field: true}, fields);
    const input = group.querySelector('input')!;
    group.append(button(tr('+ 添加字段'), () => { if (input.value.trim() && !values.some(e => e.field === input.value.trim())) { values.push({field: input.value.trim(), selected: 'True'}); this.changed(); this.render(node); } }, 'secondary')); this.body.append(group);
  }
  private fieldChecks(node: WorkflowNode, key: string, label: string): void {
    this.body.append(el('div', 'section-label', label)); const values = strings(node.config, key); node.config[key] = values;
    const fields = [...new Set([...this.fields(node), ...values])]; fields.forEach(name => this.check(this.body, name, values.includes(name), checked => { if (checked) values.push(name); else values.splice(values.indexOf(name), 1); }));
    if (!fields.length) this.body.append(el('p', 'muted', tr('连接数据源后选择字段。')));
  }
  private connections(node: WorkflowNode): void {
    const section = el('div', 'config-section'), head = el('div', 'section-label', tr('连接')); section.append(head);
    const edges = this.graph().edges.filter(e => e.from === node.id || e.to === node.id);
    edges.forEach(edge => {
      const source = this.graph().nodes.find(n => n.id === edge.from), target = this.graph().nodes.find(n => n.id === edge.to), row = el('div', 'connection-row');
      const title = toolLabel(source) + ' #' + edge.from + ' · ' + edge.fromAnchor + ' → ' + toolLabel(target) + ' #' + edge.to + ' · ' + edge.toAnchor;
      const label = el('span', '', title); label.title = title; row.append(label, button('×', () => { this.graph().edges.splice(this.graph().edges.indexOf(edge), 1); this.changed(); this.render(node); }, 'danger', tr('移除连线'))); section.append(row);
    });
    if (!edges.length) section.append(el('p', 'muted', tr('暂无连接')));
    this.body.append(section);
  }
  private nativeFields(node: WorkflowNode): void {
    const config = node.config;
    let document: Document;
    try { document = parseXml(String(config.configurationXml), 'Configuration'); }
    catch { return; }
    const save = (): void => { config.configurationXml = new XMLSerializer().serializeToString(document); this.changed(); };
    const common: [string, string, boolean][] = node.type === 'JupyterCode' ? [['productionModeScript', 'Python 代码', true]] : node.type === 'RunCommand' ? [['ProgramName', '程序', false], ['Arguments', '命令参数', false], ['WorkingDir', '工作目录', false]] : node.type === 'Email' ? [['From', '发件人', false], ['To', '收件人', false], ['Subject', '主题', false], ['Body', '正文', true], ['SMTPServer', 'SMTP 服务器', false]] : [];
    for (const [tag, label, multiline] of common) {
      const wrap = el('label', 'config-field', tr(label)), input = multiline ? el('textarea', 'code-editor') : el('input');
      input.value = document.querySelector(tag)?.textContent ?? ''; input.setAttribute('aria-label', tr(label));
      input.addEventListener('input', () => { let element = document.querySelector(tag); if (!element) { element = document.createElement(tag); document.documentElement.append(element); } element.textContent = input.value; save(); });
      wrap.append(input); this.body.append(wrap);
    }
    if (node.type === 'TextInput') {
      const record = document.querySelector('Fields') ?? document.querySelector('RecordInfo'), data = document.querySelector('Data');
      if (record && data) {
        const original = Array.from(record.querySelectorAll('Field'));
        const table: Config = {fields: original.map(field => field.getAttribute('name') ?? ''), rows: Array.from(data.querySelectorAll('r')).map(row => Array.from(row.querySelectorAll('c')).map(cell => cell.textContent ?? ''))};
        editGrid(this.body, table, () => {
          record.querySelectorAll(':scope > Field').forEach(field => field.remove());
          record.append(...strings(table, 'fields').map((name, index) => { const field = (original.find(item => item.getAttribute('name') === name) ?? original[index])?.cloneNode(true) as Element | undefined ?? document.createElement('Field'); field.setAttribute('name', name); if (!field.hasAttribute('type')) { field.setAttribute('type', 'V_WString'); field.setAttribute('size', '254'); } return field; }));
          data.querySelectorAll(':scope > r').forEach(row => row.remove());
          data.append(...rows(table).map(row => { const item = document.createElement('r'); row.forEach(value => { const cell = document.createElement('c'); cell.textContent = String(value ?? ''); item.append(cell); }); return item; }));
          document.querySelector('NumRows')?.setAttribute('value', String(rows(table).length)); save();
        });
      }
    }
    if (node.type === 'Select' || node.type === 'Formula') {
      for (const element of Array.from(document.querySelectorAll(node.type === 'Select' ? 'SelectField' : 'FormulaField'))) {
        const details = el('details', 'select-field'), name = element.getAttribute('field') ?? '';
        details.append(el('summary', '', name));
        const attrs = node.type === 'Select' ? ['selected', 'rename', 'type', 'size', 'scale'] : ['field', 'type', 'size', 'scale', 'expression'];
        const labels: Record<string, string> = {selected: '启用', rename: '重命名', type: '类型', size: '长度（可选）', scale: '小数位', field: '输出字段', expression: '表达式'};
        for (const attr of attrs) {
          const label = tr(labels[attr] ?? attr), wrap = el('label', 'config-field', label), input = attr === 'expression' ? el('textarea') : el('input');
          input.value = element.getAttribute(attr) ?? ''; input.setAttribute('aria-label', label);
          if (attr === 'selected' && input instanceof HTMLInputElement) { input.type = 'checkbox'; input.checked = input.value !== 'False'; }
          input.addEventListener('input', () => { element.setAttribute(attr, input instanceof HTMLInputElement && input.type === 'checkbox' ? (input.checked ? 'True' : 'False') : input.value); save(); });
          wrap.append(input); details.append(wrap);
        }
        this.body.append(details);
      }
    }
    for (const [tag, label, multiline] of [['cmd_Program', '程序', false], ['Command', '程序', false], ['CommandArguments', '命令参数', false], ['Script', 'Python 代码', true], ['PythonCode', 'Python 代码', true]] as const) {
      const element = document.querySelector(tag); if (!element || element.children.length) continue;
      const wrap = el('label', 'config-field', tr(label)), input = multiline ? el('textarea', 'code-editor') : el('input');
      input.value = element.textContent ?? ''; input.setAttribute('aria-label', tr(label));
      input.addEventListener('input', () => { element.textContent = input.value; save(); }); wrap.append(input); this.body.append(wrap);
    }
    if (typeof config.engineSettingsXml === 'string') {
      try {
        const engine = parseXml(config.engineSettingsXml, 'EngineSettings'), path = engine.documentElement.getAttribute('Macro');
        if (path !== null) { const wrap = el('label', 'config-field', t('宏路径')), input = el('input'); input.value = path; input.setAttribute('aria-label', t('宏路径')); input.addEventListener('input', () => { engine.documentElement.setAttribute('Macro', input.value); config.engineSettingsXml = new XMLSerializer().serializeToString(engine); this.changed(); }); wrap.append(input); this.body.append(wrap); }
      } catch { /* The full XML editor displays invalid source without replacing it. */ }
    }
  }
}


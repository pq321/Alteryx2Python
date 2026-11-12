import { t, tr } from './i18n.js';
import { pasteCells, rows, strings, uniqueField } from './model.js';
export function el(tag, className = '', text = '') {
    const node = document.createElement(tag);
    node.className = className;
    node.textContent = text;
    return node;
}
export function byId(id) {
    const node = document.getElementById(id);
    if (!node)
        throw new Error('Missing element: ' + id);
    return node;
}
export function button(label, action, className = '', title = label) {
    const node = el('button', className, label);
    node.type = 'button';
    node.title = title;
    node.addEventListener('click', action);
    return node;
}
export function readTable(fields, data) {
    const table = el('table'), head = el('thead'), header = el('tr');
    header.append(el('th', 'row-number', '#'), ...fields.map(field => el('th', '', field)));
    head.append(header);
    table.append(head);
    const body = el('tbody');
    data.forEach((row, index) => { const tr = el('tr'); tr.append(el('td', 'row-number', String(index + 1)), ...fields.map((_, c) => { const cell = el('td', '', String(row[c] ?? '')); cell.title = String(row[c] ?? ''); return cell; })); body.append(tr); });
    table.append(body);
    return table;
}
export function editGrid(parent, config, changed) {
    const fields = strings(config, 'fields'), data = rows(config);
    config.fields = fields;
    config.rows = data;
    const redraw = () => { parent.replaceChildren(); editGrid(parent, config, changed); };
    const wrap = el('div', 'table-wrap'), table = el('table', 'data-grid'), head = el('thead'), hr = el('tr');
    hr.append(el('th', 'row-number', '#'));
    fields.forEach((name, c) => {
        const th = el('th'), group = el('div', 'column-head'), input = el('input');
        input.value = name;
        input.setAttribute('aria-label', t('字段 {n}', { n: c + 1 }));
        input.addEventListener('input', () => { fields[c] = input.value; changed(); });
        const remove = button('×', () => { fields.splice(c, 1); data.forEach(row => row.splice(c, 1)); changed(); redraw(); }, '', t('删除字段 {n}', { n: c + 1 }));
        remove.disabled = fields.length === 1;
        group.append(input, remove);
        th.append(group);
        hr.append(th);
    });
    head.append(hr);
    table.append(head);
    const tbody = el('tbody');
    const focusCell = (r, c) => { parent.querySelector('[data-row="' + r + '"][data-col="' + c + '"]')?.focus(); };
    data.forEach((row, r) => {
        const tr = el('tr'), number = el('td', 'row-number');
        number.append(button(String(r + 1), () => { data.splice(r, 1); changed(); redraw(); }, '', t('删除第 {n} 行', { n: r + 1 })));
        tr.append(number);
        fields.forEach((_, c) => {
            const td = el('td'), input = el('textarea');
            input.rows = 1;
            input.value = String(row[c] ?? '');
            input.dataset.row = String(r);
            input.dataset.col = String(c);
            input.setAttribute('aria-label', t('第 {row} 行第 {column} 列', { row: r + 1, column: c + 1 }));
            const height = () => { input.style.height = Math.min(106, Math.max(34, input.value.split('\n').length * 18 + 16)) + 'px'; };
            height();
            input.addEventListener('input', () => { row[c] = input.value; height(); changed(); });
            input.addEventListener('paste', event => {
                const source = event.clipboardData?.getData('text/plain');
                if (!source || !/[\t\r\n]/.test(source))
                    return;
                event.preventDefault();
                pasteCells(config, source, r, c);
                changed();
                redraw();
                focusCell(r, c);
            });
            input.addEventListener('keydown', event => {
                const last = r === data.length - 1 && c === fields.length - 1;
                if ((event.key === 'Enter' && !event.shiftKey) || (event.key === 'Tab' && !event.shiftKey && last)) {
                    event.preventDefault();
                    const next = r + 1;
                    if (next < 0)
                        return;
                    if (next >= data.length) {
                        data.push(fields.map(() => ''));
                        changed();
                        redraw();
                    }
                    focusCell(next, event.key === 'Tab' ? 0 : c);
                }
            });
            td.append(input);
            tr.append(td);
        });
        tbody.append(tr);
    });
    table.append(tbody);
    wrap.append(table);
    parent.append(wrap);
    const actions = el('div', 'grid-actions');
    actions.append(button(tr('+ 行'), () => { data.push(fields.map(() => '')); changed(); redraw(); focusCell(data.length - 1, 0); }, '', tr('添加一行')), button(tr('+ 列'), () => { fields.push(uniqueField(fields)); data.forEach(row => row.push('')); changed(); redraw(); }, '', tr('添加一列')), el('span', 'grid-count', t('{rows} 行 · {columns} 列', { rows: data.length, columns: fields.length })));
    parent.append(actions);
}
export async function request(url, payload) {
    const response = await fetch(url, payload === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await response.json();
    if (!response.ok) {
        const error = new Error(typeof data === 'object' && data && 'error' in data ? String(data.error) : t('请求失败 ({status})', { status: response.status }));
        Object.assign(error, { details: typeof data === 'object' && data && 'details' in data ? data.details : undefined });
        throw error;
    }
    return data;
}
export function download(name, content, type = 'text/plain;charset=utf-8') {
    const url = URL.createObjectURL(content instanceof Blob ? content : new Blob([content], { type })), link = el('a');
    link.href = url;
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function confirmReplace(title) {
    const dialog = byId('confirmDialog');
    byId('confirmTitle').textContent = title;
    byId('confirmMessage').textContent = tr('当前工作流已自动保存在本地。替换后可使用撤销恢复，也可以先下载 JSON 保存。');
    return new Promise(resolve => { dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), { once: true }); dialog.showModal(); });
}

import { t, tr, getLanguage, setLanguage, localizeStatic } from './i18n.js';
import { NODE_W, NODE_H, labels, symbols, toolLabel, categoryLabel, decodeGraph, exampleGraph, connectError } from './model.js';
import { el, byId, button, request, download, confirmReplace } from './ui.js';
import { Canvas } from './canvas.js';
import { ConfigPanel } from './config.js';
import { readTable } from './ui.js';
import { WorkflowSettings } from './settings.js';
import { hasPendingEdits } from './advanced.js';
const STORAGE = 'alteryx2python.editor.v2';
let graph = { name: tr('未命名工作流'), nodes: [], edges: [] }, tools = [], selected = null;
let history = [], cursor = -1, compiled = null, result = null;
let compiledGraph = '', runGraph = '', activeTab = 'result', busy = false, importTarget = null;
let lastRunSeconds = null;
let saveTimer, brokenDraft = false;
const nameInput = byId('wfName'), dataInput = byId('dataFile');
const previewSelect = byId('previewSelect');
let statusMessage = '', statusError = false;
const status = (message, error = false) => { statusMessage = message; statusError = error; byId('status').textContent = tr(message); byId('status').classList.toggle('error', error); };
const guard = (action) => { void action().catch(error => status(error instanceof Error ? error.message : String(error), true)); };
const fingerprint = () => JSON.stringify(graph);
const currentNode = () => graph.nodes.find(n => n.id === selected);
const canvas = new Canvas(() => graph, () => tools, () => selected, select, changed, status);
const panel = new ConfigPanel(() => graph, () => tools, changed, pickFile, (node, sheet) => guard(async () => {
    const owner = graph;
    const imported = await request('/api/import', { sourceFile: node.config.sourceFile, name: node.config.name, sheet });
    if (graph !== owner || !graph.nodes.includes(node))
        return;
    node.config = { ...imported };
    changed();
    panel.render(node);
    status(tr('已切换工作表'));
}));
const settings = new WorkflowSettings(() => graph, changed);
let macroFiles = [];
function registerGraphTools() {
    if (!Array.isArray(graph.toolDefinitions))
        return;
    for (const item of graph.toolDefinitions) {
        if (typeof item.type === 'string' && typeof item.label === 'string' && typeof item.category === 'string' && Array.isArray(item.inputs) && item.inputs.every(port => typeof port === 'string') && Array.isArray(item.outputs) && item.outputs.every(port => typeof port === 'string') && item.defaults && typeof item.defaults === 'object' && !tools.some(tool => tool.type === item.type))
            tools.push(item);
    }
}
function refreshPreviewLabels() {
    const value = previewSelect.value;
    previewSelect.replaceChildren();
    result?.previews.forEach(preview => { const node = graph.nodes.find(n => n.id === preview.node), option = el('option', '', '#' + preview.node + ' ' + toolLabel(tools.find(tool => tool.type === node?.type) ?? node) + ' / ' + preview.anchor); option.value = previewKey(preview); previewSelect.append(option); });
    if (Array.from(previewSelect.options).some(option => option.value === value))
        previewSelect.value = value;
}
function showExecution(output = result?.stdout ?? '') {
    byId('executionOutput').textContent = output + (result?.diagnostics?.length ? '\n' + JSON.stringify(result.diagnostics, null, 2) : '');
    const list = byId('artifactList');
    list.replaceChildren();
    for (const artifact of result?.artifacts ?? []) {
        const row = el('div', 'artifact-row'), label = el('span', '', artifact.name + ' · ' + artifact.size.toLocaleString() + ' B');
        const save = button('↧', () => {
            if (!artifact.content)
                return;
            const bytes = Uint8Array.from(atob(artifact.content), char => char.charCodeAt(0));
            download(artifact.name, new Blob([bytes], { type: 'application/octet-stream' }));
        }, 'icon-button', artifact.available ? tr('下载当前结果') : tr('文件未包含在响应中'));
        save.disabled = !artifact.available || artifact.content === undefined || runGraph !== fingerprint();
        row.append(label, save);
        list.append(row);
    }
    byId('executionDetails').hidden = !output && !result?.diagnostics?.length && !result?.artifacts?.length;
}
async function importWorkflow(file) {
    if (file.size > 25 * 1024 * 1024)
        throw new Error(t('工作流文件超过 25 MB'));
    const owner = graph, source = await file.text();
    const response = /\.json$/i.test(file.name) ? JSON.parse(source) : await request('/api/workflow/import', { name: file.name, xml: source });
    if (graph !== owner) {
        status(t('工作流已切换，未添加导入节点'));
        return;
    }
    const next = typeof response.graph === 'object' ? response.graph : response;
    await replaceGraph(decodeGraph(next, tools));
}
function chooseMacros(files) {
    macroFiles = files.filter(file => /\.yxmc$/i.test(file.name));
    const root = byId('macroRoot');
    root.replaceChildren();
    macroFiles.forEach(file => { const option = el('option', '', file.webkitRelativePath || file.name); option.value = file.webkitRelativePath || file.name; root.append(option); });
    byId('btnImportMacroBundle').disabled = !macroFiles.length;
}
async function importMacro() {
    const owner = graph, root = byId('macroRoot').value;
    const files = await Promise.all(macroFiles.map(async (file) => { if (file.size > 25 * 1024 * 1024)
        throw new Error(t('工作流文件超过 25 MB')); return { name: file.webkitRelativePath || file.name, xml: await file.text() }; }));
    const main = files.find(file => file.name === root);
    if (!main)
        return;
    const response = await request('/api/macros/import', { ...main, files: files.filter(file => file !== main) });
    if (graph !== owner) {
        status(t('工作流已切换，未添加导入节点'));
        return;
    }
    tools = [...tools.filter(tool => tool.type !== response.tool.type), response.tool];
    graph.toolDefinitions = [...(Array.isArray(graph.toolDefinitions) ? graph.toolDefinitions.filter(tool => tool.type !== response.tool.type) : []), response.tool];
    palette();
    addNode(response.tool.type);
    byId('macroDialog').close();
    status(t('宏已导入'));
}
function refreshLanguage() {
    localizeStatic(document.body);
    byId('languageSelect').value = getLanguage();
    palette();
    canvas.render();
    panel.render(currentNode());
    if (byId('workflowSettingsDialog').open)
        settings.render();
    refreshPreviewLabels();
    if (result) {
        showPreview();
        showExecution();
    }
    else {
        byId('resultCount').textContent = t('{rows} 行 · {columns} 列', { rows: 0, columns: 0 });
        byId('tabResult').replaceChildren(el('div', 'result-empty', t('暂无运行结果')));
    }
    byId('saveState').textContent = t('已自动保存');
    status(statusMessage, statusError);
    updateNotice();
    if (lastRunSeconds !== null)
        byId('runTime').textContent = t('运行耗时 {seconds}s', { seconds: lastRunSeconds });
}
function persist() {
    if (brokenDraft)
        return;
    try {
        localStorage.setItem(STORAGE, fingerprint());
        byId('saveState').textContent = tr('已自动保存');
    }
    catch {
        byId('saveState').textContent = tr('自动保存失败');
        status(tr('本地存储不可用或空间不足，请下载 JSON 保存工作流'), true);
    }
}
function changed() {
    brokenDraft = false;
    const value = fingerprint();
    if (history[cursor] !== value) {
        history = history.slice(0, cursor + 1);
        history.push(value);
        if (history.length > 100)
            history.shift();
        cursor = history.length - 1;
    }
    byId('btnUndo').disabled = cursor <= 0;
    byId('btnRedo').disabled = cursor >= history.length - 1;
    byId('saveState').textContent = tr('保存中…');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(persist, 250);
    canvas.render();
    panel.refreshAdvanced();
    updateNotice();
    updateDownload();
    if (result)
        showExecution();
}
function select(id) {
    selected = id;
    canvas.render();
    panel.render(currentNode());
    if (result && runGraph === fingerprint()) {
        const preview = result.previews.find(p => p.node === id);
        if (preview) {
            previewSelect.value = previewKey(preview);
            showPreview();
        }
    }
}
function historyStep(delta) {
    const next = cursor + delta;
    if (next < 0 || next >= history.length)
        return;
    cursor = next;
    graph = decodeGraph(JSON.parse(history[cursor]), tools);
    nameInput.value = graph.name;
    selected = graph.nodes.some(n => n.id === selected) ? selected : null;
    changed();
    select(selected);
    status(delta < 0 ? tr('已撤销') : tr('已重做'));
}
function nextId() { let id = 1; while (graph.nodes.some(n => n.id === String(id)))
    id++; return String(id); }
function addNode(type, point, autoConnect = true) {
    const tool = tools.find(t => t.type === type);
    if (!tool)
        return;
    const source = currentNode(), center = point ?? (source && autoConnect ? { x: source.x + NODE_W + 75 + NODE_W / 2, y: source.y + NODE_H / 2 } : canvas.center());
    const node = { id: nextId(), type, x: Math.round(center.x - NODE_W / 2), y: Math.round(center.y - NODE_H / 2), inputs: [...tool.inputs], outputs: [...tool.outputs], config: structuredClone(tool.defaults) };
    graph.nodes.push(node);
    const sourceTool = tools.find(t => t.type === source?.type), sourceOutputs = source?.outputs ?? sourceTool?.outputs ?? [];
    if (source && autoConnect && sourceOutputs.length && tool.inputs.length) {
        const edge = { from: source.id, fromAnchor: sourceOutputs[0], to: node.id, toAnchor: tool.inputs[0] };
        if (!connectError(graph, edge, tools))
            graph.edges.push(edge);
    }
    byId('palettePanel').classList.remove('mobile-open');
    changed();
    select(node.id);
    if (!point)
        canvas.fit();
    return node;
}
function deleteNode() {
    if (!selected)
        return;
    graph.nodes = graph.nodes.filter(n => n.id !== selected);
    graph.edges = graph.edges.filter(e => e.from !== selected && e.to !== selected);
    changed();
    select(null);
    status(tr('已删除节点'));
}
function palette() {
    const container = byId('palette'), query = byId('toolSearch').value.toLowerCase();
    container.replaceChildren();
    const visible = tools.filter(t => [t.type, t.label, labels[t.type] ?? '', categoryLabel(t.category)].join(' ').toLowerCase().includes(query));
    for (const category of [...new Set(visible.map(t => t.category))]) {
        const group = el('section', 'palette-group');
        group.append(el('h3', '', categoryLabel(category)));
        visible.filter(t => t.category === category).forEach(tool => {
            const item = button('', () => addNode(tool.type), 'palette-item', tool.label);
            item.dataset.category = category;
            item.draggable = true;
            item.dataset.tool = tool.type;
            item.append(el('span', 'tool-icon', symbols[tool.type] ?? '◇'), el('span', '', toolLabel(tool)));
            item.addEventListener('dragstart', event => { event.dataTransfer?.setData('application/x-workflow-tool', tool.type); if (event.dataTransfer)
                event.dataTransfer.effectAllowed = 'copy'; });
            group.append(item);
        });
        container.append(group);
    }
    if (!visible.length)
        container.append(el('p', 'muted', tr('没有匹配的工具')));
}
function pickFile(target = null) { importTarget = target; dataInput.value = ''; dataInput.click(); }
async function fileData(file) {
    return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(new Error(tr('无法读取文件'))); reader.onload = () => resolve(String(reader.result).split(',')[1] ?? ''); reader.readAsDataURL(file); });
}
async function importFiles(files, target = null, point) {
    const owner = graph;
    for (const [index, file] of files.entries()) {
        if (/\.(json|yxmd|yxwz|yxmc)$/i.test(file.name)) {
            await importWorkflow(file);
            continue;
        }
        if (!/\.(csv|tsv|txt|xlsx)$/i.test(file.name))
            throw new Error(t('支持 CSV、TSV、TXT 和 XLSX 文件：{name}', { name: file.name }));
        if (file.size > 20 * 1024 * 1024)
            throw new Error(t('文件超过 20 MB：{name}', { name: file.name }));
        status(t('正在导入 {name}…', { name: file.name }));
        const data = await request('/api/import', { name: file.name, content: await fileData(file) });
        if (owner !== graph) {
            status(tr('工作流已切换，未添加导入节点'));
            return;
        }
        let node = index === 0 && target ? graph.nodes.find(n => n.id === target && n.type === 'DbFileInput') : undefined;
        if (index === 0 && target && !node) {
            status(tr('目标节点已移除，未添加文件'));
            return;
        }
        node ??= addNode('DbFileInput', point ? { x: point.x + index * 230, y: point.y } : undefined, false);
        if (!node)
            return;
        node.config = { ...node.config, ...data };
        changed();
        select(node.id);
        status(t('已导入 {name} · {rows} 行', { name: file.name, rows: data.rowCount }));
    }
}
function updateNotice() {
    const notice = byId('resultNotice'), notes = [];
    if ((result && runGraph !== fingerprint()) || (compiled && compiledGraph !== fingerprint()))
        notes.push(tr('工作流已修改，当前显示的是上一次结果。请重新运行或生成代码。'));
    if (compiled?.unsupported?.length)
        notes.push(t('独立 Python 导出存在限制：{details}', { details: compiled.unsupported.join('; ') }));
    if (result && runGraph === fingerprint() && result.warnings?.length)
        notes.push(...result.warnings);
    notice.textContent = notes.join(' ');
    notice.hidden = !notes.length;
}
function updateDownload() {
    const fresh = activeTab === 'result' ? !!result && runGraph === fingerprint() && !!previewSelect.value : !!compiled && compiledGraph === fingerprint() && !(activeTab === 'python' && compiled.unsupported.length);
    byId('btnDownload').disabled = !fresh;
    byId('downloadLabel').textContent = activeTab === 'result' ? 'CSV' : activeTab === 'python' ? '.py' : '.yxmd';
    byId('btnManifest').disabled = !compiled?.manifest || compiledGraph !== fingerprint();
    byId('btnManifest').hidden = !compiled?.manifest;
}
function tab(name) {
    activeTab = name;
    byId('bottomPanel').classList.remove('collapsed');
    document.querySelectorAll('[data-tab]').forEach(item => { const active = item.dataset.tab === name; item.classList.toggle('active', active); item.setAttribute('aria-selected', String(active)); item.tabIndex = active ? 0 : -1; });
    for (const [key, id] of Object.entries({ result: 'tabResult', python: 'tabPython', yxmd: 'tabYxmd' }))
        byId(id).classList.toggle('active', key === name);
    previewSelect.hidden = name !== 'result' || !result;
    updateDownload();
}
function previewKey(preview) { return JSON.stringify([preview.node, preview.anchor]); }
function showPreview() {
    const preview = result?.previews.find(p => previewKey(p) === previewSelect.value);
    if (!preview)
        return;
    const container = byId('tabResult');
    container.replaceChildren(readTable(preview.columns, preview.rows));
    byId('resultBadge').textContent = preview.rowCount.toLocaleString();
    byId('resultCount').textContent = t('{rows} 行 · {columns} 列', { rows: preview.rowCount.toLocaleString(), columns: preview.columns.length }) + (preview.rowCount > preview.rows.length ? ' · ' + t('预览前 {n} 行', { n: preview.rows.length }) : '');
    updateDownload();
}
async function execute(run) {
    if (busy)
        return;
    if (hasPendingEdits(graph)) {
        status(t('配置未应用'), true);
        return;
    }
    if (!graph.nodes.length) {
        status(tr('请先添加数据节点'), true);
        return;
    }
    busy = true;
    byId('btnRun').disabled = true;
    byId('btnCompile').disabled = true;
    const snapshot = fingerprint(), started = performance.now();
    status(run ? tr('正在运行…') : tr('正在生成代码…'));
    try {
        const response = await request(run ? '/api/run' : '/api/compile', JSON.parse(snapshot));
        response.unsupported ??= [];
        compiled = response;
        compiledGraph = snapshot;
        byId('tabPython').textContent = response.python ?? '';
        byId('tabYxmd').textContent = response.yxmd ?? '';
        if ('previews' in response) {
            result = response;
            runGraph = snapshot;
            previewSelect.replaceChildren();
            refreshPreviewLabels();
            const last = result.previews.at(-1);
            const final = [...result.previews].reverse().find(p => graph.nodes.find(n => n.id === p.node)?.type === 'DbFileOutput') ?? result.previews.find(p => p.node === last?.node);
            if (final)
                previewSelect.value = previewKey(final);
            lastRunSeconds = ((performance.now() - started) / 1000).toFixed(2);
            byId('runTime').textContent = t('运行耗时 {seconds}s', { seconds: lastRunSeconds });
            showPreview();
            tab('result');
        }
        else
            tab('python');
        if ('previews' in response)
            showExecution();
        updateNotice();
        status(run ? tr('运行完成') : response.unsupported.length ? t('独立 Python 导出存在限制：{details}', { details: response.unsupported.join('; ') }) : tr('代码已生成'), !run && !!response.unsupported.length);
    }
    catch (error) {
        if (run) {
            runGraph = '';
            byId('tabResult').replaceChildren(el('div', 'inline-error', error instanceof Error ? error.message : String(error)));
            tab('result');
        }
        if (error && typeof error === 'object' && 'details' in error && error.details && typeof error.details === 'object' && 'stdout' in error.details)
            showExecution(String(error.details.stdout));
        status(error instanceof Error ? error.message : String(error), true);
        updateNotice();
        updateDownload();
    }
    finally {
        busy = false;
        byId('btnRun').disabled = false;
        byId('btnCompile').disabled = false;
    }
}
function resetResults() {
    lastRunSeconds = null;
    compiled = null;
    result = null;
    runGraph = '';
    compiledGraph = '';
    previewSelect.replaceChildren();
    previewSelect.hidden = true;
    byId('tabPython').textContent = '';
    byId('tabYxmd').textContent = '';
    byId('tabResult').replaceChildren(el('div', 'result-empty', tr('暂无运行结果')));
    byId('resultBadge').textContent = '0';
    byId('resultCount').textContent = t('{rows} 行 · {columns} 列', { rows: 0, columns: 0 });
    byId('runTime').textContent = '';
    byId('executionDetails').hidden = true;
    byId('executionOutput').textContent = '';
    byId('artifactList').replaceChildren();
    updateNotice();
    updateDownload();
}
async function replaceGraph(next) {
    if (graph.nodes.length && !await confirmReplace(tr('替换当前工作流？')))
        return;
    graph = next;
    registerGraphTools();
    palette();
    nameInput.value = graph.name;
    resetResults();
    changed();
    select(graph.nodes[0]?.id ?? null);
    canvas.fit();
    status(tr('工作流已载入'));
}
function bind(id, action) { byId(id).addEventListener('click', action); }
bind('btnUndo', () => historyStep(-1));
bind('btnRedo', () => historyStep(1));
bind('btnDeleteNode', deleteNode);
bind('btnManifest', () => { if (compiled?.manifest && compiledGraph === fingerprint())
    download(graph.name.replace(/[<>:"/\\|?*]/g, '_') + '.manifest.json', JSON.stringify(compiled.manifest, null, 2), 'application/json'); });
bind('btnWorkflowSettings', () => settings.open());
bind('btnCloseSettings', () => byId('workflowSettingsDialog').close());
bind('btnMacro', () => byId('macroDialog').showModal());
bind('btnCloseMacro', () => byId('macroDialog').close());
bind('btnImportMacroBundle', () => guard(importMacro));
byId('macroFiles').addEventListener('change', event => chooseMacros(Array.from(event.target.files ?? [])));
byId('macroFolder').addEventListener('change', event => chooseMacros(Array.from(event.target.files ?? [])));
byId('languageSelect').addEventListener('change', event => { setLanguage(event.target.value); refreshLanguage(); });
bind('btnCloseConfig', () => select(null));
bind('btnToggleTools', () => { select(null); byId('palettePanel').hidden = false; byId('palettePanel').classList.toggle('mobile-open'); });
bind('btnCompile', () => guard(() => execute(false)));
bind('btnRun', () => guard(() => execute(true)));
bind('btnNew', () => guard(() => replaceGraph({ name: tr('未命名工作流'), nodes: [], edges: [] })));
for (const id of ['btnExample', 'btnStartExample'])
    bind(id, () => guard(() => replaceGraph(exampleGraph())));
bind('btnStartTable', () => { addNode('TextInput'); });
for (const id of ['btnImport', 'btnStartFile'])
    bind(id, () => pickFile());
bind('btnOpen', () => { const input = byId('workflowFile'); input.value = ''; input.click(); });
bind('btnSave', () => { persist(); download(graph.name + '.json', JSON.stringify(graph, null, 2), 'application/json'); status('工作流 JSON 已下载'); });
bind('btnDownload', () => {
    const name = graph.name.replace(/[<>:"/\\|?*]/g, '_') || 'workflow';
    if (activeTab === 'result') {
        const preview = result?.previews.find(p => previewKey(p) === previewSelect.value);
        if (preview)
            download(name + '.csv', '\ufeff' + preview.csv, 'text/csv;charset=utf-8');
    }
    else if (compiled)
        download(name + (activeTab === 'python' ? '.py' : '.yxmd'), activeTab === 'python' ? compiled.python : compiled.yxmd);
});
bind('btnPalette', () => { byId('palettePanel').hidden = true; byId('btnExpandPalette').hidden = false; });
bind('btnExpandPalette', () => { byId('palettePanel').hidden = false; byId('btnExpandPalette').hidden = true; });
bind('btnCollapseResult', () => { const collapsed = byId('bottomPanel').classList.toggle('collapsed'); byId('btnCollapseResult').textContent = collapsed ? '⌃' : '⌄'; });
nameInput.addEventListener('input', () => { graph.name = nameInput.value; changed(); });
byId('toolSearch').addEventListener('input', palette);
previewSelect.addEventListener('change', showPreview);
dataInput.addEventListener('change', () => { const target = importTarget; importTarget = null; guard(() => importFiles(Array.from(dataInput.files ?? []), target)); });
byId('workflowFile').addEventListener('change', event => guard(async () => {
    const file = event.target.files?.[0];
    if (file)
        await importWorkflow(file);
    event.target.value = '';
}));
document.querySelectorAll('[data-tab]').forEach(item => {
    item.addEventListener('click', () => tab(item.dataset.tab));
    item.addEventListener('keydown', event => { if (!['ArrowLeft', 'ArrowRight'].includes(event.key))
        return; event.preventDefault(); const all = Array.from(document.querySelectorAll('[data-tab]')), next = all[(all.indexOf(item) + (event.key === 'ArrowRight' ? 1 : 2)) % all.length]; tab(next.dataset.tab); next.focus(); });
});
let fileDragDepth = 0;
document.addEventListener('dragover', event => { if (event.dataTransfer?.types.includes('Files'))
    event.preventDefault(); });
document.addEventListener('drop', event => {
    if (!event.dataTransfer?.files.length)
        return;
    event.preventDefault();
    fileDragDepth = 0;
    byId('canvasWrap').classList.remove('file-over');
    const zone = event.target.closest('[data-file-target]');
    guard(() => importFiles(Array.from(event.dataTransfer.files), zone?.dataset.fileTarget ?? null, zone ? undefined : canvas.point({ x: event.clientX, y: event.clientY })));
});
byId('canvasWrap').addEventListener('dragenter', event => { if (event.dataTransfer?.types.includes('Files')) {
    fileDragDepth++;
    byId('canvasWrap').classList.add('file-over');
} });
byId('canvasWrap').addEventListener('dragleave', event => { if (event.dataTransfer?.types.includes('Files') && --fileDragDepth <= 0)
    byId('canvasWrap').classList.remove('file-over'); });
byId('canvasWrap').addEventListener('dragover', event => event.preventDefault());
byId('canvasWrap').addEventListener('drop', event => {
    event.preventDefault();
    const type = event.dataTransfer?.getData('application/x-workflow-tool');
    if (type)
        addNode(type, canvas.point({ x: event.clientX, y: event.clientY }), false);
});
document.addEventListener('keydown', event => {
    const target = event.target;
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable || byId('confirmDialog').open)
        return;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        historyStep(event.shiftKey ? 1 : -1);
    }
    if (event.key === 'Escape') {
        canvas.cancel();
        select(null);
    }
    if (event.key === 'Delete' || event.key === 'Backspace') {
        event.preventDefault();
        if (!canvas.deleteEdge())
            deleteNode();
    }
});
function resize(id, vertical) {
    const handle = byId(id);
    const apply = (client) => {
        if (vertical)
            document.documentElement.style.setProperty('--config-width', Math.max(270, Math.min(650, innerWidth - client.x, innerWidth - 220)) + 'px');
        else {
            byId('bottomPanel').classList.remove('collapsed');
            document.documentElement.style.setProperty('--result-height', Math.max(120, Math.min(innerHeight * .55, innerHeight - client.y - 27)) + 'px');
        }
    };
    handle.addEventListener('pointerdown', event => { event.preventDefault(); handle.setPointerCapture(event.pointerId); });
    handle.addEventListener('pointermove', event => { if (handle.hasPointerCapture(event.pointerId))
        apply({ x: event.clientX, y: event.clientY }); });
    handle.addEventListener('keydown', event => {
        if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key))
            return;
        event.preventDefault();
        const box = handle.getBoundingClientRect();
        apply({ x: box.left + (event.key === 'ArrowLeft' ? -20 : 20), y: box.top + (event.key === 'ArrowUp' ? -20 : 20) });
    });
}
resize('configResize', true);
resize('resultResize', false);
window.addEventListener('beforeunload', persist);
async function init() {
    try {
        tools = (await request('/api/tools')).tools;
        if (!Array.isArray(tools) || !tools.length)
            throw new Error(tr('工具列表为空'));
        let saved = null;
        try {
            saved = localStorage.getItem(STORAGE);
        }
        catch {
            status(tr('本地存储不可用'), true);
        }
        if (saved) {
            try {
                graph = decodeGraph(JSON.parse(saved), tools);
            }
            catch {
                brokenDraft = true;
                status(tr('本地草稿无法读取，已保留原草稿；请打开有效的工作流 JSON'), true);
                palette();
                canvas.render();
                panel.render(undefined);
                return;
            }
        }
        registerGraphTools();
        nameInput.value = graph.name;
        refreshLanguage();
        changed();
        select(null);
        canvas.fit();
        status(saved ? tr('已恢复本地草稿') : tr('就绪'));
    }
    catch (error) {
        status(t('连接失败：{message}', { message: error instanceof Error ? error.message : String(error) }), true);
        byId('connectionStatus').textContent = tr('服务未连接');
    }
}
localizeStatic(document.body);
byId('languageSelect').value = getLanguage();
void init();

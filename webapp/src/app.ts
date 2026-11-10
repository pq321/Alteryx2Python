import {type Graph, type Tool, type WorkflowNode, type Point, type CompileResult, type RunResult, type ImportedData, type Preview, NODE_W, NODE_H, labels, symbols, categories, decodeGraph, exampleGraph, connectError} from './model.js';
import {el, byId, button, request, download, confirmReplace} from './ui.js';
import {Canvas} from './canvas.js';
import {ConfigPanel} from './config.js';
import {readTable} from './ui.js';
const STORAGE = 'alteryx2python.editor.v2';
let graph: Graph = {name: '未命名工作流', nodes: [], edges: []}, tools: Tool[] = [], selected: string | null = null;
let history: string[] = [], cursor = -1, compiled: CompileResult | null = null, result: RunResult | null = null;
let compiledGraph = '', runGraph = '', activeTab = 'result', busy = false, importTarget: string | null = null;
let saveTimer: ReturnType<typeof setTimeout> | undefined, brokenDraft = false;
const nameInput = byId<HTMLInputElement>('wfName'), dataInput = byId<HTMLInputElement>('dataFile');
const previewSelect = byId<HTMLSelectElement>('previewSelect');
const status = (message: string, error = false): void => { byId('status').textContent = message; byId('status').classList.toggle('error', error); };
const guard = (action: () => Promise<void>): void => { void action().catch(error => status(error instanceof Error ? error.message : String(error), true)); };
const fingerprint = (): string => JSON.stringify(graph);
const currentNode = (): WorkflowNode | undefined => graph.nodes.find(n => n.id === selected);
const canvas = new Canvas(() => graph, () => tools, () => selected, select, changed, status);
const panel = new ConfigPanel(() => graph, () => tools, changed, pickFile, (node, sheet) => guard(async () => {
  const owner = graph;
  const imported = await request<ImportedData>('/api/import', {sourceFile: node.config.sourceFile, name: node.config.name, sheet});
  if (graph !== owner || !graph.nodes.includes(node)) return;
  node.config = {...imported}; changed(); panel.render(node); status('已切换工作表');
}));
function persist(): void {
  if (brokenDraft) return;
  try { localStorage.setItem(STORAGE, fingerprint()); byId('saveState').textContent = '已自动保存'; }
  catch { byId('saveState').textContent = '自动保存失败'; status('本地存储不可用或空间不足，请下载 JSON 保存工作流', true); }
}
function changed(): void {
  brokenDraft = false;
  const value = fingerprint();
  if (history[cursor] !== value) { history = history.slice(0, cursor + 1); history.push(value); if (history.length > 100) history.shift(); cursor = history.length - 1; }
  byId<HTMLButtonElement>('btnUndo').disabled = cursor <= 0; byId<HTMLButtonElement>('btnRedo').disabled = cursor >= history.length - 1;
  byId('saveState').textContent = '保存中…'; clearTimeout(saveTimer); saveTimer = setTimeout(persist, 250);
  canvas.render(); updateNotice(); updateDownload();
}
function select(id: string | null): void {
  selected = id; canvas.render(); panel.render(currentNode());
  if (result && runGraph === fingerprint()) {
    const preview = result.previews.find(p => p.node === id);
    if (preview) { previewSelect.value = previewKey(preview); showPreview(); }
  }
}
function historyStep(delta: number): void {
  const next = cursor + delta; if (next < 0 || next >= history.length) return;
  cursor = next; graph = decodeGraph(JSON.parse(history[cursor]!), tools); nameInput.value = graph.name; selected = graph.nodes.some(n => n.id === selected) ? selected : null;
  changed(); select(selected); status(delta < 0 ? '已撤销' : '已重做');
}
function nextId(): string { let id = 1; while (graph.nodes.some(n => n.id === String(id))) id++; return String(id); }
function addNode(type: string, point?: Point, autoConnect = true): WorkflowNode | undefined {
  const tool = tools.find(t => t.type === type); if (!tool) return;
  const source = currentNode(), center = point ?? (source && autoConnect ? {x: source.x + NODE_W + 75 + NODE_W / 2, y: source.y + NODE_H / 2} : canvas.center());
  const node: WorkflowNode = {id: nextId(), type, x: Math.round(center.x - NODE_W / 2), y: Math.round(center.y - NODE_H / 2), config: structuredClone(tool.defaults)};
  graph.nodes.push(node);
  const sourceTool = tools.find(t => t.type === source?.type);
  if (source && autoConnect && sourceTool?.outputs.length && tool.inputs.length) {
    const edge = {from: source.id, fromAnchor: sourceTool.outputs[0]!, to: node.id, toAnchor: tool.inputs[0]!};
    if (!connectError(graph, edge, tools)) graph.edges.push(edge);
  }
  byId('palettePanel').classList.remove('mobile-open'); changed(); select(node.id); if (!point) canvas.fit(); return node;
}
function deleteNode(): void {
  if (!selected) return;
  graph.nodes = graph.nodes.filter(n => n.id !== selected); graph.edges = graph.edges.filter(e => e.from !== selected && e.to !== selected); changed(); select(null); status('已删除节点');
}
function palette(): void {
  const container = byId('palette'), query = byId<HTMLInputElement>('toolSearch').value.toLowerCase(); container.replaceChildren();
  const visible = tools.filter(t => [t.type, t.label, labels[t.type] ?? '', categories[t.category] ?? ''].join(' ').toLowerCase().includes(query));
  for (const category of [...new Set(visible.map(t => t.category))]) {
    const group = el('section', 'palette-group'); group.append(el('h3', '', categories[category] ?? category));
    visible.filter(t => t.category === category).forEach(tool => {
      const item = button('', () => addNode(tool.type), 'palette-item', tool.label); item.dataset.category = category; item.draggable = true; item.dataset.tool = tool.type;
      item.append(el('span', 'tool-icon', symbols[tool.type] ?? '◇'), el('span', '', labels[tool.type] ?? tool.label));
      item.addEventListener('dragstart', event => { event.dataTransfer?.setData('application/x-workflow-tool', tool.type); if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy'; }); group.append(item);
    }); container.append(group);
  }
  if (!visible.length) container.append(el('p', 'muted', '没有匹配的工具'));
}
function pickFile(target: string | null = null): void { importTarget = target; dataInput.value = ''; dataInput.click(); }
async function fileData(file: File): Promise<string> {
  return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onerror = () => reject(new Error('无法读取文件')); reader.onload = () => resolve(String(reader.result).split(',')[1] ?? ''); reader.readAsDataURL(file); });
}
async function importFiles(files: File[], target: string | null = null, point?: Point): Promise<void> {
  const owner = graph;
  for (const [index, file] of files.entries()) {
    if (!/\.(csv|tsv|txt|xlsx)$/i.test(file.name)) throw new Error('支持 CSV、TSV、TXT 和 XLSX 文件：' + file.name);
    if (file.size > 20 * 1024 * 1024) throw new Error('文件超过 20 MB：' + file.name);
    status('正在导入 ' + file.name + '…');
    const data = await request<ImportedData>('/api/import', {name: file.name, content: await fileData(file)});
    if (owner !== graph) { status('工作流已切换，未添加导入节点'); return; }
    let node = index === 0 && target ? graph.nodes.find(n => n.id === target && n.type === 'DbFileInput') : undefined;
    if (index === 0 && target && !node) { status('目标节点已移除，未添加文件'); return; }
    node ??= addNode('DbFileInput', point ? {x: point.x + index * 230, y: point.y} : undefined, false);
    if (!node) return;
    node.config = {...data}; changed(); select(node.id); status('已导入 ' + file.name + ' · ' + data.rowCount + ' 行');
  }
}
function updateNotice(): void {
  const notice = byId('resultNotice'), notes: string[] = [];
  if ((result && runGraph !== fingerprint()) || (compiled && compiledGraph !== fingerprint())) notes.push('工作流已修改，当前显示的是上一次结果。请重新运行或生成代码。');
  if (compiled?.unsupported.length) notes.push('独立 Python 导出存在限制：' + compiled.unsupported.join('；'));
  notice.textContent = notes.join(' '); notice.hidden = !notes.length;
}
function updateDownload(): void {
  const fresh = activeTab === 'result' ? !!result && runGraph === fingerprint() && !!previewSelect.value : !!compiled && compiledGraph === fingerprint() && !(activeTab === 'python' && compiled.unsupported.length);
  byId<HTMLButtonElement>('btnDownload').disabled = !fresh; byId('downloadLabel').textContent = activeTab === 'result' ? 'CSV' : activeTab === 'python' ? '.py' : '.yxmd';
}
function tab(name: string): void {
  activeTab = name; byId('bottomPanel').classList.remove('collapsed');
  document.querySelectorAll<HTMLButtonElement>('[data-tab]').forEach(item => { const active = item.dataset.tab === name; item.classList.toggle('active', active); item.setAttribute('aria-selected', String(active)); item.tabIndex = active ? 0 : -1; });
  for (const [key, id] of Object.entries({result: 'tabResult', python: 'tabPython', yxmd: 'tabYxmd'})) byId(id).classList.toggle('active', key === name);
  previewSelect.hidden = name !== 'result' || !result; updateDownload();
}
function previewKey(preview: Preview): string { return JSON.stringify([preview.node, preview.anchor]); }
function showPreview(): void {
  const preview = result?.previews.find(p => previewKey(p) === previewSelect.value); if (!preview) return;
  const container = byId('tabResult'); container.replaceChildren(readTable(preview.columns, preview.rows));
  byId('resultBadge').textContent = preview.rowCount.toLocaleString();
  byId('resultCount').textContent = preview.rowCount.toLocaleString() + ' 行 · ' + preview.columns.length + ' 列' + (preview.rowCount > preview.rows.length ? ' · 预览前 ' + preview.rows.length + ' 行' : ''); updateDownload();
}
async function execute(run: boolean): Promise<void> {
  if (busy) return;
  if (!graph.nodes.length) { status('请先添加数据节点', true); return; }
  busy = true; byId<HTMLButtonElement>('btnRun').disabled = true; byId<HTMLButtonElement>('btnCompile').disabled = true;
  const snapshot = fingerprint(), started = performance.now(); status(run ? '正在运行…' : '正在生成代码…');
  try {
    const response = await request<RunResult | CompileResult>(run ? '/api/run' : '/api/compile', JSON.parse(snapshot));
    compiled = response; compiledGraph = snapshot; byId('tabPython').textContent = response.python; byId('tabYxmd').textContent = response.yxmd;
    if ('previews' in response) {
      result = response; runGraph = snapshot; previewSelect.replaceChildren();
      result.previews.forEach(preview => { const node = graph.nodes.find(n => n.id === preview.node), option = el('option', '', '#' + preview.node + ' ' + (labels[node?.type ?? ''] ?? '') + ' / ' + preview.anchor); option.value = previewKey(preview); previewSelect.append(option); });
      const last = result.previews.at(-1);
      const final = [...result.previews].reverse().find(p => graph.nodes.find(n => n.id === p.node)?.type === 'DbFileOutput') ?? result.previews.find(p => p.node === last?.node);
      if (final) previewSelect.value = previewKey(final);
      byId('runTime').textContent = '运行耗时 ' + ((performance.now() - started) / 1000).toFixed(2) + ' s'; showPreview(); tab('result');
    } else tab('python');
    updateNotice(); status(run ? '运行完成' : '代码已生成');
  } catch (error) {
    if (run) { runGraph = ''; byId('tabResult').replaceChildren(el('div', 'inline-error', error instanceof Error ? error.message : String(error))); tab('result'); }
    status(error instanceof Error ? error.message : String(error), true); updateNotice(); updateDownload();
  } finally { busy = false; byId<HTMLButtonElement>('btnRun').disabled = false; byId<HTMLButtonElement>('btnCompile').disabled = false; }
}
function resetResults(): void {
  compiled = null; result = null; runGraph = ''; compiledGraph = ''; previewSelect.replaceChildren(); previewSelect.hidden = true;
  byId('tabPython').textContent = ''; byId('tabYxmd').textContent = ''; byId('tabResult').replaceChildren(el('div', 'result-empty', '暂无运行结果'));
  byId('resultBadge').textContent = '0'; byId('resultCount').textContent = '0 行 · 0 列'; byId('runTime').textContent = ''; updateNotice(); updateDownload();
}
async function replaceGraph(next: Graph): Promise<void> {
  if (graph.nodes.length && !await confirmReplace('替换当前工作流？')) return;
  graph = next; nameInput.value = graph.name; resetResults(); changed(); select(graph.nodes[0]?.id ?? null); canvas.fit(); status('工作流已载入');
}
function bind(id: string, action: () => void): void { byId(id).addEventListener('click', action); }
bind('btnUndo', () => historyStep(-1)); bind('btnRedo', () => historyStep(1)); bind('btnDeleteNode', deleteNode);
bind('btnCloseConfig', () => select(null));
bind('btnToggleTools', () => { select(null); byId('palettePanel').hidden = false; byId('palettePanel').classList.toggle('mobile-open'); });
bind('btnCompile', () => guard(() => execute(false))); bind('btnRun', () => guard(() => execute(true)));
bind('btnNew', () => guard(() => replaceGraph({name: '未命名工作流', nodes: [], edges: []})));
for (const id of ['btnExample', 'btnStartExample']) bind(id, () => guard(() => replaceGraph(exampleGraph())));
bind('btnStartTable', () => { addNode('TextInput'); });
for (const id of ['btnImport', 'btnStartFile']) bind(id, () => pickFile());
bind('btnOpen', () => { const input = byId<HTMLInputElement>('workflowFile'); input.value = ''; input.click(); });
bind('btnSave', () => { persist(); download(graph.name + '.json', JSON.stringify(graph, null, 2), 'application/json'); status('工作流 JSON 已下载'); });
bind('btnDownload', () => {
  const name = graph.name.replace(/[<>:"/\\|?*]/g, '_') || 'workflow';
  if (activeTab === 'result') { const preview = result?.previews.find(p => previewKey(p) === previewSelect.value); if (preview) download(name + '.csv', '\ufeff' + preview.csv, 'text/csv;charset=utf-8'); }
  else if (compiled) download(name + (activeTab === 'python' ? '.py' : '.yxmd'), activeTab === 'python' ? compiled.python : compiled.yxmd);
});
bind('btnPalette', () => { byId('palettePanel').hidden = true; byId('btnExpandPalette').hidden = false; });
bind('btnExpandPalette', () => { byId('palettePanel').hidden = false; byId('btnExpandPalette').hidden = true; });
bind('btnCollapseResult', () => { const collapsed = byId('bottomPanel').classList.toggle('collapsed'); byId('btnCollapseResult').textContent = collapsed ? '⌃' : '⌄'; });
nameInput.addEventListener('input', () => { graph.name = nameInput.value; changed(); });
byId('toolSearch').addEventListener('input', palette); previewSelect.addEventListener('change', showPreview);
dataInput.addEventListener('change', () => { const target = importTarget; importTarget = null; guard(() => importFiles(Array.from(dataInput.files ?? []), target)); });
byId<HTMLInputElement>('workflowFile').addEventListener('change', event => guard(async () => {
  const file = (event.target as HTMLInputElement).files?.[0]; if (!file) return; if (file.size > 25 * 1024 * 1024) throw new Error('工作流文件超过 25 MB');
  await replaceGraph(decodeGraph(JSON.parse(await file.text()), tools));
}));
document.querySelectorAll<HTMLButtonElement>('[data-tab]').forEach(item => {
  item.addEventListener('click', () => tab(item.dataset.tab!));
  item.addEventListener('keydown', event => { if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return; event.preventDefault(); const all = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-tab]')), next = all[(all.indexOf(item) + (event.key === 'ArrowRight' ? 1 : 2)) % all.length]!; tab(next.dataset.tab!); next.focus(); });
});
let fileDragDepth = 0;
document.addEventListener('dragover', event => { if (event.dataTransfer?.types.includes('Files')) event.preventDefault(); });
document.addEventListener('drop', event => {
  if (!event.dataTransfer?.files.length) return;
  event.preventDefault(); fileDragDepth = 0; byId('canvasWrap').classList.remove('file-over');
  const zone = (event.target as Element).closest<HTMLElement>('[data-file-target]');
  guard(() => importFiles(Array.from(event.dataTransfer!.files), zone?.dataset.fileTarget ?? null, zone ? undefined : canvas.point({x: event.clientX, y: event.clientY})));
});
byId('canvasWrap').addEventListener('dragenter', event => { if (event.dataTransfer?.types.includes('Files')) { fileDragDepth++; byId('canvasWrap').classList.add('file-over'); } });
byId('canvasWrap').addEventListener('dragleave', event => { if (event.dataTransfer?.types.includes('Files') && --fileDragDepth <= 0) byId('canvasWrap').classList.remove('file-over'); });
byId('canvasWrap').addEventListener('dragover', event => event.preventDefault());
byId('canvasWrap').addEventListener('drop', event => {
  event.preventDefault(); const type = event.dataTransfer?.getData('application/x-workflow-tool');
  if (type) addNode(type, canvas.point({x: event.clientX, y: event.clientY}), false);
});
document.addEventListener('keydown', event => {
  const target = event.target as HTMLElement;
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable || byId<HTMLDialogElement>('confirmDialog').open) return;
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'z') { event.preventDefault(); historyStep(event.shiftKey ? 1 : -1); }
  if (event.key === 'Escape') { canvas.cancel(); select(null); }
  if (event.key === 'Delete' || event.key === 'Backspace') { event.preventDefault(); if (!canvas.deleteEdge()) deleteNode(); }
});
function resize(id: string, vertical: boolean): void {
  const handle = byId(id);
  const apply = (client: Point): void => {
    if (vertical) document.documentElement.style.setProperty('--config-width', Math.max(270, Math.min(650, innerWidth - client.x, innerWidth - 220)) + 'px');
    else { byId('bottomPanel').classList.remove('collapsed'); document.documentElement.style.setProperty('--result-height', Math.max(120, Math.min(innerHeight * .55, innerHeight - client.y - 27)) + 'px'); }
  };
  handle.addEventListener('pointerdown', event => { event.preventDefault(); handle.setPointerCapture(event.pointerId); });
  handle.addEventListener('pointermove', event => { if (handle.hasPointerCapture(event.pointerId)) apply({x: event.clientX, y: event.clientY}); });
  handle.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) return;
    event.preventDefault(); const box = handle.getBoundingClientRect(); apply({x: box.left + (event.key === 'ArrowLeft' ? -20 : 20), y: box.top + (event.key === 'ArrowUp' ? -20 : 20)});
  });
}
resize('configResize', true); resize('resultResize', false);
window.addEventListener('beforeunload', persist);
async function init(): Promise<void> {
  try {
    tools = (await request<{tools: Tool[]}>('/api/tools')).tools;
    if (!Array.isArray(tools) || !tools.length) throw new Error('工具列表为空');
    let saved: string | null = null;
    try { saved = localStorage.getItem(STORAGE); } catch { status('本地存储不可用', true); }
    if (saved) { try { graph = decodeGraph(JSON.parse(saved), tools); } catch { brokenDraft = true; status('本地草稿无法读取，已保留原草稿；请打开有效的工作流 JSON', true); palette(); canvas.render(); panel.render(undefined); return; } }
    nameInput.value = graph.name; palette(); changed(); select(null); canvas.fit(); status(saved ? '已恢复本地草稿' : '就绪');
  } catch (error) { status('连接失败：' + (error instanceof Error ? error.message : String(error)), true); byId('connectionStatus').textContent = '服务未连接'; }
}
void init();


import {t, tr} from './i18n.js';
import {type Graph, type WorkflowNode, type Tool, type Edge, type Point, NODE_W, NODE_H, toolLabel, ports as nodePorts, symbols, strings, rows, text, connectError} from './model.js';
import {byId} from './ui.js';
const NS = 'http://www.w3.org/2000/svg';
function svg<K extends keyof SVGElementTagNameMap>(tag: K, attributes: Record<string, string | number>, content = ''): SVGElementTagNameMap[K] {
  const node = document.createElementNS(NS, tag); for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value)); node.textContent = content; return node;
}
const curve = (a: Point, b: Point): string => { const d = Math.max(50, Math.abs(b.x - a.x) / 2); return 'M ' + a.x + ' ' + a.y + ' C ' + (a.x + d) + ' ' + a.y + ', ' + (b.x - d) + ' ' + b.y + ', ' + b.x + ' ' + b.y; };
export class Canvas {
  private svg = document.querySelector<SVGSVGElement>('#canvas')!;
  private scene = document.querySelector<SVGGElement>('#scene')!;
  private view = {x: 30, y: 30, scale: 1};
  private drag: {id: string | null; start: Point; origin: Point; moved: boolean} | null = null;
  private link: {from: string; fromAnchor: string; point: Point} | null = null;
  private edge: number | null = null;
  constructor(private graph: () => Graph, private tools: () => Tool[], private selected: () => string | null, private select: (id: string | null) => void, private changed: () => void, private status: (message: string, error?: boolean) => void) {
    this.svg.addEventListener('pointerdown', event => this.down(event));
    this.svg.addEventListener('pointermove', event => this.move(event));
    this.svg.addEventListener('pointerup', event => this.up(event));
    this.svg.addEventListener('pointercancel', () => { this.drag = null; this.link = null; this.render(); });
    this.svg.addEventListener('wheel', event => { event.preventDefault(); this.zoom(event.deltaY < 0 ? 1.1 : 1 / 1.1, {x: event.clientX, y: event.clientY}); }, {passive: false});
    byId('btnZoomIn').addEventListener('click', () => this.zoom(1.2)); byId('btnZoomOut').addEventListener('click', () => this.zoom(1 / 1.2)); byId('btnFit').addEventListener('click', () => this.fit());
  }
  point(client: Point): Point { const box = this.svg.getBoundingClientRect(); return {x: (client.x - box.left - this.view.x) / this.view.scale, y: (client.y - box.top - this.view.y) / this.view.scale}; }
  center(): Point { const box = this.svg.getBoundingClientRect(); return this.point({x: box.left + box.width / 2, y: box.top + box.height / 2}); }
  private anchor(node: WorkflowNode, name: string, input: boolean): Point {
    const ports = nodePorts(node, this.tools(), input);
    return {x: node.x + (input ? 0 : NODE_W), y: node.y + 20 + (ports.indexOf(name) + .5) * (NODE_H - 28) / Math.max(ports.length, 1)};
  }
  render(): void {
    this.scene.replaceChildren(); this.scene.setAttribute('transform', 'translate(' + this.view.x + ' ' + this.view.y + ') scale(' + this.view.scale + ')');
    const graph = this.graph();
    graph.edges.forEach((edge, index) => {
      const from = graph.nodes.find(n => n.id === edge.from), to = graph.nodes.find(n => n.id === edge.to); if (!from || !to) return;
      const a = this.anchor(from, edge.fromAnchor, false), b = this.anchor(to, edge.toAnchor, true), d = curve(a, b);
      const hit = svg('path', {d, class: 'edge-hit', 'data-edge': index}); const title = svg('title', {}, tr('双击移除连线')); hit.append(title);
      hit.addEventListener('dblclick', () => { graph.edges.splice(index, 1); this.edge = null; this.changed(); this.select(this.selected()); });
      this.scene.append(hit, svg('path', {d, class: 'edge' + (this.edge === index ? ' selected' : ''), 'pointer-events': 'none'}));
      if (edge.fromAnchor !== 'Output') this.scene.append(svg('text', {x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 - 8, class: 'edge-label', 'text-anchor': 'middle'}, edge.fromAnchor));
    });
    graph.nodes.forEach(node => {
      const group = svg('g', {transform: 'translate(' + node.x + ' ' + node.y + ')', class: 'node' + (this.selected() === node.id ? ' selected' : ''), 'data-node': node.id, tabindex: 0, role: 'button', 'aria-label': toolLabel(node) + ' #' + node.id});
      group.append(svg('rect', {width: NODE_W, height: NODE_H, rx: 6, class: 'body'}), svg('rect', {x: 13, y: 17, width: 31, height: 31, rx: 5, fill: '#eff6f0'}), svg('text', {x: 28, y: 39, class: 'node-symbol', 'text-anchor': 'middle'}, symbols[node.type] ?? '◇'));
      group.append(svg('text', {x: 54, y: 30, class: 'title', ...(toolLabel(node).length > 20 ? {textLength: 120, lengthAdjust: 'spacingAndGlyphs'} : {})}, toolLabel(node)), svg('text', {x: 54, y: 47, class: 'summary'}, this.summary(node).slice(0, 21)), svg('text', {x: 13, y: 66, class: 'summary'}, '#' + node.id));
      const title = svg('title', {}, toolLabel(node) + ' · ' + this.summary(node)); group.append(title);
      const ports = (names: string[], input: boolean): void => names.forEach(name => {
        const position = this.anchor(node, name, input), circle = svg('circle', {cx: position.x - node.x, cy: position.y - node.y, r: 5, class: 'anchor', 'data-port': name, 'data-direction': input ? 'input' : 'output', 'data-node': node.id}); circle.append(svg('title', {}, name));
        group.append(circle);
        if (names.length > 1) group.append(svg('text', {x: input ? 8 : NODE_W - 8, y: position.y - node.y + 3, 'text-anchor': input ? 'start' : 'end', class: 'anchor-label'}, name));
      });
      ports(nodePorts(node, this.tools(), true), true); ports(nodePorts(node, this.tools(), false), false);
      group.addEventListener('keydown', event => { if (event.key === 'Enter') this.select(node.id); });
      this.scene.append(group);
    });
    if (this.link) {
      const source = graph.nodes.find(n => n.id === this.link?.from);
      if (source) this.scene.append(svg('path', {d: curve(this.anchor(source, this.link.fromAnchor, false), this.link.point), class: 'link-preview'}));
    }
    byId('canvasEmpty').hidden = graph.nodes.length > 0;
    byId('graphCount').textContent = t('{count} 个节点', {count: graph.nodes.length}) + ' · ' + t('{count} 条连接', {count: graph.edges.length});
    byId('zoomValue').textContent = Math.round(this.view.scale * 100) + '%';
    byId('canvasMeta').textContent = this.graph().name;
  }
  private summary(node: WorkflowNode): string {
    const c = node.config;
    if (node.type === 'TextInput') return t('{rows} 行 · {columns} 列', {rows: rows(c).length, columns: strings(c, 'fields').length});
    if (node.type === 'DbFileInput') return text(c, 'name', tr('等待导入文件'));
    if (node.type === 'Filter') return text(c, 'expression');
    if (node.type === 'DbFileOutput') return text(c, 'file');
    return toolLabel(this.tools().find(t => t.type === node.type) ?? node);
  }
  private down(event: PointerEvent): void {
    if (event.button !== 0) return;
    const target = event.target as Element, port = target.closest<SVGElement>('[data-port]'), node = target.closest<SVGElement>('[data-node]');
    if (port?.dataset.direction === 'output') { this.link = {from: port.dataset.node!, fromAnchor: port.dataset.port!, point: this.point({x: event.clientX, y: event.clientY})}; this.status(tr('选择输入端口')); this.render(); return; }
    if (port?.dataset.direction === 'input' && this.link) { this.finish(port); return; }
    this.link = null;
    const edge = target.closest<SVGElement>('[data-edge]');
    if (edge) { this.edge = Number(edge.dataset.edge); this.select(null); this.render(); return; }
    this.edge = null;
    const id = node?.dataset.node ?? null, record = this.graph().nodes.find(n => n.id === id);
    this.drag = {id, start: {x: event.clientX, y: event.clientY}, origin: record ? {x: record.x, y: record.y} : {x: this.view.x, y: this.view.y}, moved: false};
    this.svg.setPointerCapture(event.pointerId); this.select(id);
  }
  private move(event: PointerEvent): void {
    if (this.link) { this.link.point = this.point({x: event.clientX, y: event.clientY}); this.render(); }
    if (!this.drag) return;
    const dx = event.clientX - this.drag.start.x, dy = event.clientY - this.drag.start.y;
    if (Math.abs(dx) + Math.abs(dy) < 3) return;
    this.drag.moved = true;
    if (this.drag.id) { const node = this.graph().nodes.find(n => n.id === this.drag?.id); if (node) { node.x = this.drag.origin.x + dx / this.view.scale; node.y = this.drag.origin.y + dy / this.view.scale; } }
    else { this.view.x = this.drag.origin.x + dx; this.view.y = this.drag.origin.y + dy; }
    this.render();
  }
  private up(event: PointerEvent): void {
    if (this.svg.hasPointerCapture(event.pointerId)) this.svg.releasePointerCapture(event.pointerId);
    if (this.link) { const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<SVGElement>('[data-port]'); if (target?.dataset.direction === 'input') this.finish(target); }
    if (this.drag?.moved && this.drag.id) this.changed();
    this.drag = null;
  }
  private finish(port: SVGElement): void {
    if (!this.link) return;
    const edge: Edge = {from: this.link.from, fromAnchor: this.link.fromAnchor, to: port.dataset.node!, toAnchor: port.dataset.port!}; this.link = null;
    const error = connectError(this.graph(), edge, this.tools());
    if (error) this.status(error, true); else { this.graph().edges.push(edge); this.changed(); this.select(edge.to); this.status(tr('已连接')); }
    this.render();
  }
  cancel(): void { this.link = null; this.edge = null; this.render(); }
  deleteEdge(): boolean {
    if (this.edge === null) return false; this.graph().edges.splice(this.edge, 1); this.edge = null; this.changed(); this.render(); return true;
  }
  zoom(factor: number, client?: Point): void {
    const box = this.svg.getBoundingClientRect(), position = client ?? {x: box.left + box.width / 2, y: box.top + box.height / 2}, before = this.point(position), next = Math.max(.3, Math.min(2, this.view.scale * factor));
    this.view = {x: position.x - box.left - before.x * next, y: position.y - box.top - before.y * next, scale: next}; this.render();
  }
  fit(): void {
    const nodes = this.graph().nodes; if (!nodes.length) { this.view = {x: 30, y: 30, scale: 1}; this.render(); return; }
    const box = this.svg.getBoundingClientRect(), minX = Math.min(...nodes.map(n => n.x)), minY = Math.min(...nodes.map(n => n.y)), width = Math.max(...nodes.map(n => n.x)) + NODE_W - minX, height = Math.max(...nodes.map(n => n.y)) + NODE_H - minY;
    const scale = Math.max(.3, Math.min(1, (box.width - 70) / width, (box.height - 100) / height));
    this.view = {scale, x: (box.width - width * scale) / 2 - minX * scale, y: (box.height - height * scale) / 2 - minY * scale - 15}; this.render();
  }
}


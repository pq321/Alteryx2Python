import { isJson } from './model.js';
import { t, tr } from './i18n.js';
import { el, button } from './ui.js';
const drafts = new WeakMap();
export function hasPendingEdits(graph) {
    return [graph, ...graph.nodes.map(node => node.config)].some(owner => !!drafts.get(owner)?.size);
}
export function parseXml(source, root) {
    const document = new DOMParser().parseFromString(source, 'application/xml');
    if (document.querySelector('parsererror'))
        throw new Error(t('无效 XML'));
    if (document.documentElement.tagName !== root)
        throw new Error(t('XML 根元素必须为 {name}', { name: root }));
    return document;
}
export function parseObject(source) {
    const value = JSON.parse(source);
    if (!value || Array.isArray(value) || typeof value !== 'object' || !isJson(value))
        throw new Error(t('JSON 对象'));
    return value;
}
export function codeEditor(parent, owner, key, label, value, validate, apply, current) {
    const section = el('div', 'advanced-field'), wrap = el('label', 'config-field', tr(label)), input = el('textarea', 'code-editor');
    const draft = drafts.get(owner)?.get(key);
    let baseline = draft?.baseline ?? value;
    input.value = draft?.value ?? value;
    input.spellcheck = false;
    input.setAttribute('aria-label', tr(label));
    input.dataset.configKey = key;
    const error = el('p', 'inline-error'), state = el('span', 'muted'), actions = el('div', 'editor-actions');
    const update = () => { state.textContent = input.value === baseline ? '' : t('配置未应用'); input.setAttribute('aria-invalid', 'false'); error.textContent = ''; };
    input.addEventListener('input', () => {
        const cache = drafts.get(owner) ?? new Map();
        if (input.value === baseline)
            cache.delete(key);
        else
            cache.set(key, { value: input.value, baseline });
        drafts.set(owner, cache);
        update();
    });
    input.addEventListener('refresh-source', event => {
        if (drafts.get(owner)?.has(key))
            return;
        baseline = String(event.detail);
        input.value = baseline;
        update();
    });
    const commit = button(t('应用'), () => {
        try {
            if (current && current() !== baseline)
                throw new Error(t('配置源已更新，请重置后重新编辑'));
            validate(input.value);
            baseline = input.value;
            drafts.get(owner)?.delete(key);
            apply(input.value);
            update();
            state.textContent = t('配置已应用');
        }
        catch (cause) {
            error.textContent = cause instanceof Error ? cause.message : String(cause);
            input.setAttribute('aria-invalid', 'true');
        }
    }, 'secondary');
    const reset = button('↶', () => { baseline = current?.() ?? value; input.value = baseline; drafts.get(owner)?.delete(key); update(); input.dispatchEvent(new Event('editor-reset')); }, 'icon-button', t('重置'));
    reset.setAttribute('aria-label', t('重置'));
    actions.append(commit, reset, state);
    wrap.append(input);
    section.append(wrap, actions, error);
    parent.append(section);
    update();
    return input;
}
export function nodeAdvanced(parent, config, changed) {
    const details = el('details', 'advanced-section');
    details.open = typeof config.configurationXml === 'string';
    details.append(el('summary', '', t('高级配置')));
    for (const [key, root, label] of [['configurationXml', 'Configuration', '配置 XML'], ['engineSettingsXml', 'EngineSettings', '引擎设置 XML']]) {
        const current = () => typeof config[key] === 'string' ? config[key] : '<' + root + ' />';
        codeEditor(details, config, key, label, current(), value => { parseXml(value, root); }, value => { config[key] = value; changed(); }, current);
    }
    const json = el('details');
    json.append(el('summary', '', t('配置 JSON')));
    codeEditor(json, config, 'configJson', '完整节点配置', JSON.stringify(config, null, 2), value => { parseObject(value); }, value => {
        const next = parseObject(value);
        Object.keys(config).forEach(key => { delete config[key]; });
        Object.assign(config, next);
        changed();
    }, () => JSON.stringify(config, null, 2));
    details.append(json);
    parent.append(details);
}
const workflowSections = { propertiesXml: 'Properties', runtimePropertiesXml: 'RuntimeProperties', eventsXml: 'Events', constantsXml: 'Constants' };
function effectiveProperties(graph) {
    const original = graph.workflowXml ? parseXml(graph.workflowXml, 'AlteryxDocument').documentElement.querySelector(':scope > Properties') : null;
    const document = parseXml(graph.propertiesXml ?? (original ? new XMLSerializer().serializeToString(original) : '<Properties/>'), 'Properties');
    for (const key of ['runtimePropertiesXml', 'eventsXml', 'constantsXml']) {
        if (graph[key] === undefined)
            continue;
        const child = document.importNode(parseXml(graph[key], workflowSections[key]).documentElement, true);
        const previous = document.documentElement.querySelector(':scope > ' + workflowSections[key]);
        if (previous)
            previous.replaceWith(child);
        else
            document.documentElement.append(child);
    }
    return document;
}
export function workflowXmlValue(graph, key) {
    const properties = effectiveProperties(graph).documentElement;
    const element = key === 'propertiesXml' ? properties : properties.querySelector(':scope > ' + workflowSections[key]);
    return element ? new XMLSerializer().serializeToString(element) : '<' + workflowSections[key] + '/>';
}
export function applyWorkflowXml(graph, key, source) {
    const next = parseXml(source, workflowSections[key]);
    const document = key === 'propertiesXml' ? next : effectiveProperties(graph);
    if (key !== 'propertiesXml') {
        const previous = document.documentElement.querySelector(':scope > ' + workflowSections[key]), child = document.importNode(next.documentElement, true);
        if (previous)
            previous.replaceWith(child);
        else
            document.documentElement.append(child);
    }
    graph.propertiesXml = new XMLSerializer().serializeToString(document);
    delete graph.runtimePropertiesXml;
    delete graph.eventsXml;
    delete graph.constantsXml;
}

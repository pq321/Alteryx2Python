import {type Graph, type JsonValue} from './model.js';
import {byId, el, button} from './ui.js';
import {t, tr} from './i18n.js';
import {codeEditor, parseObject, parseXml, workflowXmlValue, applyWorkflowXml} from './advanced.js';

export class WorkflowSettings {
  constructor(private graph: () => Graph, private changed: () => void, private deliveryProfiles: () => string[]) {}
  render(): void {
    const graph = this.graph(), body = byId('workflowSettingsBody'); body.replaceChildren();
    const runtime = (): {[key: string]: JsonValue} => graph.runtime ?? {};
    const select = (label: string, choices: [string, string][], value: string, change: (next: string) => void): void => {
      const wrap = el('label', 'config-field', tr(label)), input = el('select'); input.setAttribute('aria-label', tr(label));
      choices.forEach(([value, label]) => { const option = el('option', '', tr(label)); option.value = value; input.append(option); });
      input.value = value; input.addEventListener('change', () => { change(input.value); this.changed(); this.render(); }); wrap.append(input); body.append(wrap);
    };
    select('参数导出方式', [['dynamic', '动态参数'], ['specialized', '固定当前回答']], graph.parameterMode ?? 'dynamic', value => { graph.parameterMode = value as 'dynamic' | 'specialized'; });
    select('交付模式', this.deliveryProfiles().map(profile => [profile, profile]), String(runtime().delivery_profile ?? 'html-draft-v1'), value => { graph.runtime = {...runtime(), delivery_profile: value}; });
    const replay = el('label', 'config-field', tr('重放日期时间')), date = el('input');
    date.placeholder = '2026-10-13T09:00:00'; date.value = String(runtime().as_of ?? '');
    date.addEventListener('change', () => {
      const next = {...runtime()}, value = date.value.trim();
      if (value) next.as_of = value; else delete next.as_of;
      graph.runtime = next; this.changed(); this.render();
    });
    replay.append(date); body.append(replay);
    codeEditor(body, graph, 'runtimeJson', '完整运行参数 JSON', JSON.stringify(runtime(), null, 2), value => { parseObject(value); }, value => { graph.runtime = parseObject(value); this.changed(); this.render(); }, () => JSON.stringify(runtime(), null, 2));
    for (const [key, label] of [['answers', '用户回答 JSON'], ['constants', '变量覆盖 JSON'], ['input_bindings', '输入文件绑定 JSON'],
      ['allowed_commands', '允许的命令 JSON'], ['log_event_ids', 'Python 日志事件索引 JSON']] as const) {
      const array = key === 'allowed_commands' || key === 'log_event_ids';
      const current = (): string => JSON.stringify(runtime()[key] ?? (array ? [] : {}), null, 2);
      codeEditor(body, graph, 'runtime.' + key, label, current(), value => {
        if (!array) parseObject(value);
        else { const items: unknown = JSON.parse(value); if (!Array.isArray(items) || !items.every(item => typeof item === 'string')) throw new Error(t('JSON 字符串数组')); }
      }, value => { graph.runtime = {...runtime(), [key]: JSON.parse(value) as JsonValue}; this.changed(); this.render(); }, current);
    }
    const sections = [
      ['propertiesXml', 'Properties', '工作流属性 XML'],
      ['runtimePropertiesXml', 'RuntimeProperties', '运行属性 XML'],
      ['eventsXml', 'Events', '事件 XML'],
      ['constantsXml', 'Constants', '常量 XML'],
    ] as const;
    for (const [key, root, label] of sections) {
      const details = el('details', 'advanced-section'); details.append(el('summary', '', t(label)));
      const current = (): string => workflowXmlValue(graph, key);
      const input = codeEditor(details, graph, key, label, current(), value => { parseXml(value, root); }, value => { applyWorkflowXml(graph, key, value); this.changed(); this.render(); }, current);
      if (root === 'Properties') {
        const row = el('label', 'check-label'), cancel = el('input'); cancel.type = 'checkbox';
        const refresh = (): void => {
          try {
            const source = parseXml(input.value, root);
            const option = source.documentElement.querySelector(':scope > CancelOnError');
            cancel.disabled = false; cancel.checked = ['true', '1'].includes((option?.getAttribute('value') ?? option?.textContent ?? '').toLowerCase());
          } catch { cancel.disabled = true; }
        };
        cancel.addEventListener('change', () => {
          const source = parseXml(input.value, root);
          let option = source.documentElement.querySelector(':scope > CancelOnError');
          if (!option) { option = source.createElement('CancelOnError'); source.documentElement.append(option); }
          option.setAttribute('value', cancel.checked ? 'True' : 'False');
          input.value = new XMLSerializer().serializeToString(source);
          input.dispatchEvent(new Event('input'));
        });
        input.addEventListener('input', refresh); input.addEventListener('editor-reset', refresh);
        row.append(cancel, document.createTextNode(tr('出错时取消运行'))); details.insertBefore(row, details.children[1] ?? null); refresh();
      }
      if (root === 'Events') {
        const form = el('div'); details.append(form);
        let syncing = false;
        const renderEvents = (): void => {
          form.replaceChildren();
          let document: Document; try { document = parseXml(input.value, 'Events'); } catch { return; }
          const sync = (): void => { input.value = new XMLSerializer().serializeToString(document); syncing = true; try { input.dispatchEvent(new Event('input')); } finally { syncing = false; } };
          for (const [index, event] of Array.from(document.documentElement.querySelectorAll(':scope > Event')).entries()) {
            const section = el('details', 'select-field'); section.append(el('summary', '', t('事件') + ' #' + index));
            const aliases: Record<string, string[]> = {cmd_CommandArguments: ['cmd_CommandArguments', 'cmd_CommandLine'], email_SMTPServer: ['email_SMTPServer', 'email_SMTP']};
            const spelling = (name: string): string => (aliases[name] ?? [name]).find(key => event.querySelector(':scope > ' + key) || event.hasAttribute(key)) ?? name;
            const get = (name: string): string => { const key = spelling(name), child = event.querySelector(':scope > ' + key); return child?.getAttribute('value') ?? child?.textContent ?? event.getAttribute(key) ?? ''; };
            const set = (name: string, value: string): void => {
              name = spelling(name); const child = event.querySelector(':scope > ' + name);
              if (child?.hasAttribute('value')) child.setAttribute('value', value);
              else if (child) child.textContent = value;
              else if (event.hasAttribute(name)) event.setAttribute(name, value);
              else { const item = document.createElement(name); item.textContent = value; event.append(item); }
              sync();
            };
            const mail = get('SendMail').toLowerCase() === 'true' || ['sendemail', 'sendmail', 'email'].includes((get('EventType') || get('Type')).toLowerCase());
            const fields: [string, string, [string, string][]?][] = [
              ['Enabled', '启用', [['True', 'True'], ['False', 'False']]],
              ['When', '触发时机', [['Before', '运行前'], ['After', '运行后'], ['AfterError', '运行错误后'], ['AfterNoError', '运行成功后'], ['AfterRunWithWarnings', '运行警告后'], ['AfterRunWithoutErrorsOrWarnings', '运行无警告后'], ['AfterRunWithErrorsOrWarnings', '运行错误或警告后'], ['Disabled', 'Disabled']]],
              ['SendMail', '发送邮件', [['False', 'False'], ['True', 'True']]],
              ...(mail ? [['email_From', '发件人'], ['email_To', '收件人'], ['email_Subject', '主题'], ['email_Body', '正文'], ['email_SMTPServer', 'SMTP 服务器'], ['email_Port', '端口'], ['email_Encryption', '加密', [['None', 'None'], ['SSL', 'SSL'], ['TLS', 'TLS']]], ['email_Authentication', '认证', [['False', 'False'], ['True', 'True']]], ['email_Username', '用户名']] as [string, string, [string, string][]?][] : [['cmd_Program', '程序'], ['cmd_CommandArguments', '命令参数'], ['cmd_WorkingDir', '工作目录'], ['cmd_Timeout', '超时（秒）']] as [string, string][]),
            ];
            for (const [name, label, choices] of fields) {
              const wrap = el('label', 'config-field', tr(label)), field = choices ? el('select') : name.endsWith('Body') ? el('textarea') : el('input');
              if (choices) { const values = [...choices]; if (get(name) && !values.some(([value]) => value === get(name))) values.unshift([get(name), get(name)]); for (const [value, label] of values) { const option = el('option', '', tr(label)); option.value = value; field.append(option); } }
              field.value = get(name) || (name === 'Enabled' ? 'True' : name === 'SendMail' ? 'False' : ''); field.setAttribute('aria-label', tr(label));
              field.addEventListener(choices ? 'change' : 'input', () => { set(name, field.value); if (name === 'SendMail') { if (!get('Type') && !get('EventType')) set('Type', 'RunCommand'); if (field.value === 'False' && ['sendemail', 'sendmail', 'email'].includes((get('EventType') || get('Type')).toLowerCase())) set(get('EventType') ? 'EventType' : 'Type', 'RunCommand'); renderEvents(); } });
              wrap.append(field); section.append(wrap);
            }
            section.append(button(t('删除'), () => { event.remove(); sync(); renderEvents(); }, 'danger')); form.append(section);
          }
          form.append(button(t('添加事件'), () => {
            const event = document.createElement('Event'); event.setAttribute('Type', 'RunCommand'); event.setAttribute('Enabled', 'True');
            for (const [name, value] of [['When', 'Before'], ['cmd_Program', ''], ['cmd_CommandArguments', '']]) { const item = document.createElement(name!); item.textContent = value!; event.append(item); }
            document.documentElement.append(event); sync(); renderEvents();
          }, 'secondary'));
        };
        input.addEventListener('input', () => { if (!syncing) renderEvents(); });
        input.addEventListener('editor-reset', renderEvents); renderEvents();
      }
      body.append(details);
    }
  }
  open(): void { this.render(); byId<HTMLDialogElement>('workflowSettingsDialog').showModal(); }
}

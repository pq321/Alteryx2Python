import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({headless: true, ...(process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {})});
const page = await browser.newPage({viewport: {width: 1440, height: 960}});
const base = process.env.EDITOR_URL || 'http://127.0.0.1:18081';
const errors = [];
page.on('pageerror', error => errors.push(error.message));
const status = text => page.locator('#status').filter({hasText: text}).waitFor();
const snapshot = async () => { await page.waitForTimeout(300); return page.evaluate(() => localStorage.getItem('alteryx2python.editor.v2')); };
const editor = key => page.locator('[data-config-key="' + key + '"]');
const section = key => editor(key).locator('xpath=ancestor::div[contains(@class,"advanced-field")][1]');
async function openEditor(key) {
  await editor(key).evaluate(input => { for (let parent = input.parentElement; parent; parent = parent.parentElement) if (parent.tagName === 'DETAILS') parent.open = true; });
}
async function apply(key, value) {
  await openEditor(key); await editor(key).fill(value); await section(key).getByRole('button', {name: 'Apply', exact: true}).click();
}
async function loadGraph(graph) {
  await page.locator('#workflowFile').setInputFiles({name: 'workflow.json', mimeType: 'application/json', buffer: Buffer.from(JSON.stringify(graph))});
  if (await page.locator('#confirmDialog').isVisible()) await page.locator('#confirmDialog button[value="confirm"]').click();
  await status('Workflow loaded');
}
try {
  await page.goto(base); await status('就绪');
  await page.locator('#languageSelect').selectOption('en');
  assert.equal(await page.locator('html').getAttribute('lang'), 'en');
  assert.equal(await page.locator('#toolSearch').getAttribute('placeholder'), 'Search tools…');
  assert.equal(await page.locator('#wfName').getAttribute('aria-label'), 'Workflow name');
  assert.match(await page.locator('#tabResult').innerText(), /No results yet/);
  const toolsResponse = await page.request.get(base + '/api/tools'), catalogue = await toolsResponse.json();
  assert.equal(await page.locator('[data-tool]').count(), catalogue.tools.length);
  const graph = {name: '业务数据保持原文', nodes: [
    {id: '1', type: 'TextInput', x: 50, y: 100, config: {fields: ['amount', 'label'], rows: [['2', '筛选'], ['5', 'English']]}},
    {id: '2', type: 'DbFileOutput', x: 350, y: 100, config: {file: 'result.csv'}},
  ], edges: [{from: '1', fromAnchor: 'Output', to: '2', toAnchor: 'Input'}]};
  await loadGraph(graph);
  await page.locator('#btnCompile').click(); await status('Python generated');
  const manifestDownload = page.waitForEvent('download'); await page.locator('#btnManifest').click(); assert.match((await manifestDownload).suggestedFilename(), /\.manifest\.json$/);
  const python = await page.locator('#tabPython').textContent(), before = await snapshot();
  await page.locator('#languageSelect').selectOption('zh');
  await page.locator('#languageSelect').selectOption('en');
  assert.equal(await snapshot(), before);
  assert.equal(await page.locator('#tabPython').textContent(), python);
  assert.equal(await page.locator('#wfName').inputValue(), graph.name);
  await page.locator('#btnWorkflowSettings').click();
  await page.getByRole('combobox', {name: 'Export parameter mode', exact: true}).selectOption('specialized');
  assert.equal(await page.getByRole('combobox', {name: 'Delivery profile', exact: true}).locator('option[value="legacy-metadata-v1"]').count(), 0);
  await apply('runtimeJson', JSON.stringify({answers: {}, constants: {}, allowed_commands: [], allow_external_runtimes: false, delivery_profile: 'html-draft-v1', command_timeout: 5}));
  await apply('eventsXml', '<Events><Enabled value="False"/><Event Type="RunCommand" Enabled="False"><When>Before</When><cmd_Program>never.exe</cmd_Program><cmd_CommandLine value="original args"/><VendorEvent keep="yes"/></Event><Event Type="SendEmail" Enabled="False"><When>AfterNoError</When><SendMail>True</SendMail><email_SMTP value="original-smtp"/></Event></Events>');
  await openEditor('eventsXml');
  const nativeEvents = editor('eventsXml').locator('xpath=ancestor::details[1]');
  await nativeEvents.locator('.select-field summary').nth(0).click();
  assert.equal(await nativeEvents.getByRole('textbox', {name: 'Arguments', exact: true}).inputValue(), 'original args');
  await nativeEvents.getByRole('textbox', {name: 'Arguments', exact: true}).fill('updated args');
  await nativeEvents.locator('.select-field summary').nth(1).click();
  assert.equal(await nativeEvents.getByRole('textbox', {name: 'SMTP server', exact: true}).inputValue(), 'original-smtp');
  await nativeEvents.getByRole('textbox', {name: 'SMTP server', exact: true}).fill('updated-smtp');
  assert.match(await editor('eventsXml').inputValue(), /cmd_CommandLine value="updated args"/);
  assert.match(await editor('eventsXml').inputValue(), /email_SMTP value="updated-smtp"/);
  assert.match(await editor('eventsXml').inputValue(), /VendorEvent keep="yes"/);
  assert.doesNotMatch(await editor('eventsXml').inputValue(), /cmd_CommandArguments|email_SMTPServer/);
  await editor('eventsXml').fill((await editor('eventsXml').inputValue())
    .replace('<cmd_CommandLine', '<cmd_CommandArguments value="canonical args"/><cmd_CommandLine')
    .replace('<email_SMTP ', '<email_SMTPServer value="canonical-smtp"/><email_SMTP ')
    .replace('keep="yes"', 'keep="raw-edit"'));
  await nativeEvents.locator('.select-field summary').nth(0).click();
  assert.equal(await nativeEvents.getByRole('textbox', {name: 'Arguments', exact: true}).inputValue(), 'canonical args');
  await nativeEvents.getByRole('textbox', {name: 'Arguments', exact: true}).fill('edited canonical args');
  await nativeEvents.locator('.select-field summary').nth(1).click();
  assert.equal(await nativeEvents.getByRole('textbox', {name: 'SMTP server', exact: true}).inputValue(), 'canonical-smtp');
  await nativeEvents.getByRole('textbox', {name: 'SMTP server', exact: true}).fill('edited-canonical-smtp');
  assert.match(await editor('eventsXml').inputValue(), /cmd_CommandArguments value="edited canonical args"/);
  assert.match(await editor('eventsXml').inputValue(), /email_SMTPServer value="edited-canonical-smtp"/);
  assert.match(await editor('eventsXml').inputValue(), /cmd_CommandLine value="updated args"/);
  assert.match(await editor('eventsXml').inputValue(), /email_SMTP value="updated-smtp"/);
  assert.match(await editor('eventsXml').inputValue(), /VendorEvent keep="raw-edit"/);
  await section('eventsXml').getByRole('button', {name: 'Apply', exact: true}).click();
  assert.match(await editor('propertiesXml').inputValue(), /never.exe/);
  await apply('propertiesXml', (await editor('propertiesXml').inputValue()).replace('</Properties>', '<VendorProperties keep="yes">unknown</VendorProperties></Properties>'));
  assert.match(await editor('eventsXml').inputValue(), /never.exe/);
  await apply('constantsXml', '<Constants><Constant><Namespace>User</Namespace><Name>Label</Name><Value>keep</Value></Constant></Constants>');
  assert.match(await editor('propertiesXml').inputValue(), /VendorProperties/);
  assert.match(await editor('propertiesXml').inputValue(), /never.exe/);
  await openEditor('propertiesXml');
  await editor('propertiesXml').fill((await editor('propertiesXml').inputValue()).replace('unknown', 'stale draft'));
  await apply('eventsXml', '<Events><Enabled value="False"/></Events>');
  await openEditor('propertiesXml'); await section('propertiesXml').getByRole('button', {name: 'Apply', exact: true}).click();
  assert.match(await section('propertiesXml').textContent(), /Configuration changed/);
  await section('propertiesXml').getByRole('button', {name: 'Reset', exact: true}).click();
  assert.doesNotMatch(await editor('propertiesXml').inputValue(), /stale draft/);
  const persisted = JSON.parse(await snapshot());
  assert.equal(persisted.parameterMode, 'specialized');
  assert.equal(persisted.runtime.allow_external_runtimes, false);
  assert.match(persisted.propertiesXml, /VendorProperties/);
  assert.equal(persisted.eventsXml, undefined);
  await openEditor('eventsXml');
  const eventDetails = editor('eventsXml').locator('xpath=ancestor::details[1]');
  await eventDetails.getByRole('button', {name: 'Add event', exact: true}).click();
  await eventDetails.locator('.select-field summary').click();
  assert.equal(await eventDetails.getByRole('combobox', {name: 'When', exact: true}).count(), 1);
  assert.equal(await eventDetails.getByRole('textbox', {name: 'Program', exact: true}).count(), 1);
  await eventDetails.getByRole('combobox', {name: 'Send email', exact: true}).selectOption('True');
  await eventDetails.locator('.select-field summary').click();
  assert.equal(await eventDetails.getByRole('textbox', {name: 'SMTP server', exact: true}).count(), 1);
  await section('eventsXml').getByRole('button', {name: 'Reset', exact: true}).click();
  await page.locator('#btnCloseSettings').click();
  await page.locator('#btnCompile').click(); await status('Python generated');
  const xml = await page.locator('#tabYxmd').textContent();
  assert.match(xml, /VendorProperties/);
  await page.locator('#workflowFile').setInputFiles({name: 'imported.yxwz', mimeType: 'application/xml', buffer: Buffer.from(xml)});
  await page.locator('#confirmDialog').waitFor(); await page.locator('#confirmDialog button[value="confirm"]').click(); await status('Workflow loaded');
  await page.locator('.node[data-node="1"]').click();
  assert.equal(await page.locator('.data-grid').count(), 1);
  assert.equal(await page.getByRole('textbox', {name: 'Row 1 column 2', exact: true}).inputValue(), '筛选');
  await page.getByRole('textbox', {name: 'Row 1 column 1', exact: true}).fill('9');
  await page.locator('#btnRun').click(); await status('Run completed');
  assert.match(await page.locator('#runTime').textContent(), /Completed in/);
  assert.equal(await page.locator('#artifactList .artifact-row').count() > 0, true);
  const download = page.waitForEvent('download'); await page.locator('#executionDetails summary').click(); await page.locator('#artifactList button').first().click();
  assert.match((await download).suggestedFilename(), /result.csv/);
  await page.locator('#languageSelect').selectOption('zh'); assert.match(await page.locator('#runTime').textContent(), /运行耗时/);
  await page.locator('#languageSelect').selectOption('en');
  const importedBeforeLocale = await snapshot();
  await page.locator('#languageSelect').selectOption('zh'); await page.locator('#languageSelect').selectOption('en'); assert.equal(await snapshot(), importedBeforeLocale);
  await page.locator('.node[data-node="1"]').click(); await page.locator('[data-tool="JupyterCode"]').click();
  await page.getByRole('textbox', {name: 'Python code', exact: true}).fill('from ayx import Alteryx\nprint("frontend stdout")\nAlteryx.write(Alteryx.read("#1"), 1)');
  await page.locator('#btnRun').click(); await status('Run completed');
  assert.match(await page.locator('#executionOutput').textContent(), /frontend stdout/);
  const macro = '<AlteryxDocument><Nodes><Node ToolID="1"><GuiSettings Plugin="AlteryxBasePluginsGui.MacroInput.MacroInput"/><Properties><Configuration><Name>Input</Name></Configuration></Properties></Node><Node ToolID="2"><GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"/><Properties><Configuration><FormulaFields><FormulaField field="amount" type="Int64" size="8" expression="[amount] * 2"/></FormulaFields></Configuration></Properties></Node><Node ToolID="3"><GuiSettings Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput"/><Properties><Configuration><Name>Output</Name></Configuration></Properties></Node></Nodes><Connections><Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection><Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection></Connections><Properties><RuntimeProperties><ModuleType>Macro</ModuleType></RuntimeProperties></Properties></AlteryxDocument>';
  await page.locator('.node[data-node="1"]').click(); await page.locator('#btnMacro').click();
  await page.locator('#macroFiles').setInputFiles({name: 'times-two.yxmc', mimeType: 'application/xml', buffer: Buffer.from(macro)});
  await page.locator('#btnImportMacroBundle').click(); await status('Macro imported');
  const savedMacro = JSON.parse(await snapshot());
  const macroNode = savedMacro.nodes.find(node => node.type.startsWith('Macro_'));
  assert.ok(macroNode); assert.deepEqual(macroNode.inputs, ['Input']); assert.ok(savedMacro.edges.some(edge => edge.to === macroNode.id));
  await page.reload(); await status('Local draft restored');
  assert.equal(await page.locator('.node').count(), savedMacro.nodes.length);
  await page.locator('#btnRun').click(); await status('Run completed');
  await page.locator('#previewSelect').selectOption({label: '#' + macroNode.id + ' ' + savedMacro.toolDefinitions[0].label + ' / Output'});
  assert.match(await page.locator('#tabResult').textContent(), /18/);
  for (const viewport of [{width: 1440, height: 960}, {width: 1024, height: 768}, {width: 390, height: 844}, {width: 390, height: 568}]) {
    await page.setViewportSize(viewport);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.equal(await page.evaluate(() => document.querySelector('.statusbar').getBoundingClientRect().bottom <= innerHeight + 1), true);
    await page.locator('#btnWorkflowSettings').click();
    assert.equal(await page.locator('#workflowSettingsDialog').evaluate(dialog => { const rect = dialog.getBoundingClientRect(); return rect.left >= 0 && rect.right <= innerWidth && rect.top >= 0 && rect.bottom <= innerHeight; }), true);
    await page.locator('#btnCloseSettings').click();
  }
  assert.deepEqual(errors, []);
  console.log('Frontend acceptance passed: full palette, persistent bilingual UI, graph/code/data preservation, export modes, complete runtime, synchronized XML, conflict rejection, event/mail forms, imported table editing, artifacts, Python stdout, connected macros/reload and desktop/mobile layout.');
} finally { await browser.close(); }

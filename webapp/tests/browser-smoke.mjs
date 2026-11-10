// Uses an externally supplied Playwright installation; no project runtime dependency.
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdir} from 'node:fs/promises';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({headless: true, ...(process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {})});
const context = await browser.newContext({viewport: {width: 1440, height: 960}});
const page = await context.newPage();
const errors = [];
page.on('pageerror', error => errors.push(error.message));
page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
const base = process.env.EDITOR_URL || 'http://127.0.0.1:18081';
const waitStatus = text => page.getByRole('status').filter({hasText: text}).waitFor();
try {
  await page.goto(base);
  await waitStatus('就绪');
  await page.getByRole('button', {name: '新建数据表', exact: true}).click();
  await page.locator('.data-grid [data-row="0"][data-col="0"]').evaluate(input => {
    const clipboard = new DataTransfer();
    clipboard.setData('text/plain', 'Alice, Inc.\t2\t"line one\nline two"\nBob\t3\ttext');
    input.dispatchEvent(new ClipboardEvent('paste', {bubbles: true, cancelable: true, clipboardData: clipboard}));
  });
  assert.equal(await page.locator('.data-grid [data-row="0"][data-col="2"]').inputValue(), 'line one\nline two');
  assert.equal(await page.locator('.data-grid th input').count(), 3);
  await page.locator('[data-tool="Filter"]').click();
  await page.locator('[data-tool="DbFileOutput"]').click();
  assert.equal(await page.locator('.node').count(), 3);
  await page.locator('#btnRun').click();
  await waitStatus('运行完成');
  assert.equal(await page.locator('#tabResult tbody tr').count(), 2);
  assert.equal(await page.locator('#tabResult tbody tr').first().locator('td').nth(3).textContent(), 'line one\nline two');
  const csv = page.waitForEvent('download');
  await page.locator('#btnDownload').click();
  assert.match((await csv).suggestedFilename(), /\.csv$/);
  await page.locator('.node[data-node="1"]').click();
  await page.getByRole('textbox', {name: '第 1 行第 2 列', exact: true}).fill('9');
  assert.equal(await page.locator('#resultNotice').isVisible(), true);
  assert.equal(await page.locator('#btnDownload').isDisabled(), true);
  await page.locator('#btnUndo').click();
  assert.equal(await page.getByRole('textbox', {name: '第 1 行第 2 列', exact: true}).inputValue(), '2');
  await page.locator('#btnRedo').click();
  assert.equal(await page.getByRole('textbox', {name: '第 1 行第 2 列', exact: true}).inputValue(), '9');
  await page.locator('#btnUndo').click();
  await page.locator('#btnCloseConfig').click();
  assert.equal(await page.locator('.node').count(), 3);
  await page.locator('#canvasWrap').evaluate(wrap => {
    const transfer = new DataTransfer();
    transfer.items.add(new File(['Name,Qty\r\n"A, Ltd",7\r\n中文,9\r\n'], 'customers.csv', {type: 'text/csv'}));
    wrap.dispatchEvent(new DragEvent('drop', {bubbles: true, cancelable: true, clientX: 500, clientY: 240, dataTransfer: transfer}));
  });
  await waitStatus('已导入 customers.csv');
  assert.equal(await page.locator('#configTitle').textContent(), '文件输入');
  assert.equal(await page.locator('#configBody tbody tr').count(), 2);
  await page.locator('#btnRun').click();
  await waitStatus('运行完成');
  await page.locator('#previewSelect').selectOption({label: '#4 文件输入 / Output'});
  assert.match(await page.locator('#tabResult').innerText(), /A, Ltd/);
  const graphDownload = page.waitForEvent('download');
  await page.locator('#btnSave').click();
  assert.match((await graphDownload).suggestedFilename(), /\.json$/);
  await page.reload();
  await waitStatus('已恢复本地草稿');
  assert.equal(await page.locator('.node').count(), 4);
  await page.locator('#btnCompile').click();
  await waitStatus('代码已生成');
  assert.match(await page.locator('#tabPython').innerText(), /pd\.read_csv/);
  const python = page.waitForEvent('download');
  await page.locator('#btnDownload').click();
  assert.match((await python).suggestedFilename(), /\.py$/);
  await page.getByRole('tab', {name: 'Alteryx XML'}).click();
  const xml = page.waitForEvent('download');
  await page.locator('#btnDownload').click();
  assert.match((await xml).suggestedFilename(), /\.yxmd$/);
  await page.setViewportSize({width: 390, height: 844});
  await page.locator('#btnToggleTools').click();
  assert.equal(await page.locator('#palettePanel').isVisible(), true);
  await page.locator('[data-tool="Formula"]').click();
  assert.equal(await page.locator('#configPanel').isVisible(), true);
  await page.locator('#btnCloseConfig').click();
  assert.equal(await page.locator('#configPanel').isVisible(), false);
  for (const viewport of [{width: 390, height: 844}, {width: 390, height: 568}, {width: 1024, height: 768}]) {
    await page.setViewportSize(viewport);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.equal(await page.evaluate(() => document.querySelector('.statusbar').getBoundingClientRect().bottom <= innerHeight + 1), true);
  }
  await page.setViewportSize({width: 1440, height: 960});
  await page.getByRole('button', {name: '示例', exact: true}).click();
  await page.getByRole('button', {name: '确认', exact: true}).click();
  await page.locator('#btnRun').click();
  await waitStatus('运行完成');
  assert.equal(await page.locator('#tabResult tbody tr').count(), 3);
  if (process.env.SCREENSHOT_DIR) {
    await mkdir(process.env.SCREENSHOT_DIR, {recursive: true});
    await page.screenshot({path: process.env.SCREENSHOT_DIR + '/editor-desktop.png'});
    await page.setViewportSize({width: 390, height: 844});
    await page.locator('#btnCloseConfig').click();
    await page.screenshot({path: process.env.SCREENSHOT_DIR + '/editor-mobile.png'});
  }
  assert.deepEqual(errors, []);
  console.log('Browser smoke passed: grid paste, auto-connect, execution, stale results, undo/redo, file drop, downloads, autosave, mobile tools and responsive layout.');
} finally { await browser.close(); }


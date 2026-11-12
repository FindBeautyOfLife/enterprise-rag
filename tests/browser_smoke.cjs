// 可选的界面验收：先配置临时 RAG_DATA_DIR，再在 8765 端口启动后端。
// 使用 npm install --no-save playwright 安装依赖，或通过 NODE_PATH 指定包目录。
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('dialog', dialog => dialog.accept());
  try {
    await page.goto(process.env.RAG_TEST_URL || 'http://127.0.0.1:8765');
    await page.getByText('本地服务已连接').waitFor();
    await page.getByRole('button', { name: '新建知识库', exact: true }).click();
    await page.getByLabel('知识库名称').fill('浏览器验收资料');
    await page.getByRole('button', { name: '保存知识库' }).click();
    await page.getByRole('heading', { name: '浏览器验收资料', exact: true }).waitFor();
    await page.locator('#files').setInputFiles({ name: '审批说明.txt', mimeType: 'text/plain', buffer: Buffer.from('报销需要财务审批。\n\n合同需要法务审核。') });
    await page.getByRole('cell', { name: '审批说明.txt', exact: true }).waitFor();
    assert.equal(await page.locator('#doc-count').innerText(), '1');
    await page.getByRole('button', { name: '预览', exact: true }).click();
    await page.getByRole('dialog').getByText('报销需要财务审批。', { exact: true }).waitFor();
    await page.getByRole('dialog').getByRole('button', { name: '关闭', exact: true }).click();
    await page.getByRole('tab', { name: '检索测试', exact: true }).click();
    await page.getByLabel('检索内容').fill('报销审批');
    await page.getByRole('button', { name: '检索资料 →', exact: true }).click();
    await page.locator('#search-results .result').first().waitFor();
    assert.match(await page.locator('#search-results').innerText(), /财务审批/);
    await page.getByRole('tab', { name: '文档管理', exact: true }).click();
    fs.mkdirSync('tests/artifacts', { recursive: true });
    await page.screenshot({ path: 'tests/artifacts/workspace-desktop.png', fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
    await page.screenshot({ path: 'tests/artifacts/workspace-mobile.png', fullPage: true });
    await page.getByRole('button', { name: '替换', exact: true }).click();
    await page.locator('#replace-file').setInputFiles({ name: '更新说明.md', mimeType: 'text/markdown', buffer: Buffer.from('# 审批流程\n新版报销由财务主管审批。') });
    await page.getByRole('cell', { name: '更新说明.md', exact: true }).waitFor();
    await page.getByRole('button', { name: '删除', exact: true }).click();
    await page.getByText('文档已删除，请重建索引。', { exact: true }).waitFor();
    await page.getByRole('button', { name: '删除知识库', exact: true }).click();
    await page.getByText('知识库已删除。', { exact: true }).waitFor();
    assert.deepEqual(errors, []);
    console.log('PASS: create/upload/preview/search/replace/delete; desktop/mobile; no JS errors');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });

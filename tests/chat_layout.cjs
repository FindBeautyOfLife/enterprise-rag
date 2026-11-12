// 使用模拟回答验证问答布局，不调用付费大模型接口。
// 先在 8765 端口启动本地接口，再运行脚本；需确保可通过 NODE_PATH 等方式找到 Playwright。
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  let releaseAnswer = null;
  let delayNext = false;
  await page.route('**/health', route => route.fulfill({ json: { llm_configured: true, max_upload_bytes: 20971520 } }));
  await page.route('**/api/v1/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/knowledge-bases')) return route.fulfill({ json: [{ id: 'layout-test', name: '学校规章制度', description: '汇集学校章程、管理办法与日常办事依据。', document_count: 3, chunk_count: 81, index_status: 'ready', revision: 3, indexed_revision: 3 }] });
    if (path.endsWith('/documents')) return route.fulfill({ json: [] });
    if (path.endsWith('/ask')) {
      if (delayNext) {
        delayNext = false;
        await new Promise(resolve => { releaseAnswer = resolve; });
      }
      return route.fulfill({ json: { answer: ('学校坚持依法办学，相关申请应按规定提交材料并履行审核程序。[1]\n\n').repeat(12), evidence_sufficient: true, citation_valid: true, retry_count: 0, sources: [{ number: 1, source: '学校章程.docx', article: '第一条', content: '学校坚持依法办学。\n'.repeat(80) }] } });
    }
    return route.fulfill({ status: 404, json: { detail: 'Unexpected test route' } });
  });
  async function geometry() {
    return page.evaluate(() => {
      const panel = document.querySelector('#chat-panel');
      const list = document.querySelector('#chat-messages');
      const input = document.querySelector('#chat-question');
      const send = document.querySelector('#chat-form button');
      return { panel: panel.getBoundingClientRect().height, list: list.clientHeight, total: list.scrollHeight, top: list.scrollTop,
        inputBottom: input.getBoundingClientRect().bottom, sendBottom: send.getBoundingClientRect().bottom,
        pageHeight: document.documentElement.scrollHeight, viewport: innerHeight,
        overflowX: document.documentElement.scrollWidth > innerWidth };
    });
  }
  async function sendQuestion(text, shortcut = false) {
    await page.locator('#chat-question').fill(text);
    if (shortcut) await page.locator('#chat-question').press('Control+Enter');
    else await page.getByRole('button', { name: '发送问题 →', exact: true }).click();
    await page.waitForFunction(() => !document.querySelector('.pending') && !document.querySelector('#chat-form button').disabled);
  }
  try {
    await page.goto(process.env.RAG_TEST_URL || 'http://127.0.0.1:8765');
    await page.getByRole('heading', { name: '学校规章制度', exact: true }).waitFor();
    await page.getByRole('tab', { name: '知识问答', exact: true }).click();
    const initial = await geometry();
    for (let index = 0; index < 8; index++) await sendQuestion(`第 ${index + 1} 个问题：学校的办学宗旨是什么？`, index === 0);
    const full = await geometry();
    assert.ok(Math.abs(full.panel - initial.panel) < 2, JSON.stringify({ initial, full }));
    assert.ok(full.total > full.list * 5, 'Long history must overflow inside message area');
    assert.ok(full.sendBottom <= full.viewport, 'Send button stays in viewport');
    assert.ok(full.pageHeight <= full.viewport + 1, 'History must not increase page height');
    assert.ok(full.total - full.top - full.list < 3, 'New answers scroll to bottom');
    await page.locator('#chat-messages').evaluate(el => { el.scrollTop = 0; });
    await page.locator('#latest-message').waitFor({ state: 'visible' });
    await page.locator('#latest-message').click();
    await page.waitForFunction(() => document.querySelector('#latest-message').hidden);
    // 等待回答时向上滚动阅读历史，回答到达后应保留原有阅读位置。
    delayNext = true;
    await page.locator('#chat-question').fill('等待期间阅读旧消息');
    await page.getByRole('button', { name: '发送问题 →', exact: true }).click();
    await page.locator('.pending').waitFor();
    await page.waitForFunction(() => document.querySelector('#chat-status').textContent.includes('正在生成'));
    await page.locator('#chat-messages').evaluate(el => { el.scrollTop = 0; });
    while (!releaseAnswer) await new Promise(resolve => setTimeout(resolve, 20));
    releaseAnswer();
    await page.waitForFunction(() => !document.querySelector('.pending'));
    assert.equal((await geometry()).top, 0);
    await page.locator('#latest-message').click();
    await page.locator('.message details').last().evaluate(el => { el.open = true; });
    assert.ok(Math.abs((await geometry()).panel - initial.panel) < 2, 'Expanded citations cannot enlarge chat panel');
    fs.mkdirSync('tests/artifacts', { recursive: true });
    await page.screenshot({ path: 'tests/artifacts/chat-desktop.png', fullPage: true });
    for (const [width, height] of [[1024, 768], [390, 844], [390, 568], [844, 390]]) {
      await page.setViewportSize({ width, height });
      const layout = await geometry();
      assert.equal(layout.overflowX, false, JSON.stringify({ width, height, layout }));
      assert.ok(layout.sendBottom <= height, JSON.stringify({ width, height, layout }));
      assert.ok(layout.list >= 60, JSON.stringify({ width, height, layout }));
      assert.ok(layout.pageHeight <= height + 1, JSON.stringify({ width, height, layout }));
      if (width === 390 && height === 844) await page.screenshot({ path: 'tests/artifacts/chat-mobile.png', fullPage: true });
    }
    await page.getByRole('button', { name: '清空对话', exact: true }).click();
    assert.equal(await page.locator('.message').count(), 0);
    await page.getByText('你的资料，随问随查', { exact: true }).waitFor();
    assert.deepEqual(errors, []);
    console.log('PASS: fixed chat height, long-history scrolling, visible composer, citations, reader position, keyboard send, clear, 5 viewport sizes');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });

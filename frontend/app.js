const $ = (id) => document.getElementById(id);
const state = { bases: [], selected: null, busy: false, editing: false, preview: null, replacement: null };
const basePath = (id = state.selected) => `/api/v1/knowledge-bases/${encodeURIComponent(id)}`;
const current = () => state.bases.find(b => b.id === state.selected);
const make = (tag, text, className) => { const el = document.createElement(tag); if (text !== undefined) el.textContent = text; if (className) el.className = className; return el; };

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : (data.detail || []).map(e => e.msg).join('；') || '请求失败');
  return data;
}
function json(method, body) { return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }; }
function notice(message, error = false) { $('notice').textContent = message; $('notice').className = error ? 'error' : ''; $('notice').hidden = !message; }
function controls() {
  const disabled = state.busy || !state.selected;
  for (const id of ['edit-base', 'delete-base', 'reindex', 'files']) $(id).disabled = disabled;
  $('create-base').disabled = state.busy;
  document.querySelectorAll('nav button, td button, form button[type=submit]').forEach(b => b.disabled = state.busy);
  for (const form of ['search-form', 'chat-form']) $(form).querySelector('button').disabled = disabled;
  $('clear-chat').disabled = state.busy || !$('chat-messages').querySelector('.message');
}
function updateLatestButton() {
  const messages = $('chat-messages');
  $('latest-message').hidden = messages.scrollHeight - messages.clientHeight - messages.scrollTop < 80;
}
function scrollToLatest() {
  $('chat-messages').scrollTop = $('chat-messages').scrollHeight;
  updateLatestButton();
}
function resetChat() {
  const empty = make('div', undefined, 'empty chat-empty');
  empty.append(make('span', '知', 'empty-mark'), make('strong', '你的资料，随问随查'), make('span', '完成索引后开始提问，每次问题独立检索。'));
  $('chat-messages').replaceChildren(empty);
  $('chat-question').value = '';
  $('chat-status').textContent = 'Ctrl / ⌘ + Enter 发送 · Enter 换行';
  $('latest-message').hidden = true;
  controls();
}
$('chat-messages').addEventListener('scroll', updateLatestButton, { passive: true });
$('chat-messages').addEventListener('toggle', updateLatestButton, true);
new ResizeObserver(updateLatestButton).observe($('chat-messages'));
$('latest-message').onclick = scrollToLatest;
$('clear-chat').onclick = resetChat;
$('chat-question').onkeydown = e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey) && !e.isComposing) {
    e.preventDefault();
    if (!state.busy && state.selected) $('chat-form').requestSubmit();
  }
};
async function task(work) {
  if (state.busy) return;
  state.busy = true; controls();
  try { await work(); } catch (err) { notice(err.message, true); }
  finally { state.busy = false; controls(); }
}
async function refresh() {
  state.bases = await api('/api/v1/knowledge-bases');
  if (!current()) state.selected = state.bases[0]?.id || null;
  $('bases').replaceChildren();
  for (const base of state.bases) {
    const button = make('button', base.name, base.id === state.selected ? 'active' : '');
    button.append(make('small', `${base.document_count} 份文档 · ${base.chunk_count} 个片段`));
    button.onclick = () => task(async () => {
      if (state.selected !== base.id) {
        state.selected = base.id; $('search-results').replaceChildren(); resetChat(); notice('');
      }
      await refresh();
    });
    $('bases').append(button);
  }
  const base = current();
  $('base-title').textContent = base?.name || '企业知识库';
  $('base-description').textContent = base?.description || '让散落的文档，成为可追溯的答案。';
  $('doc-count').textContent = base?.document_count || 0;
  $('chunk-count').textContent = base?.chunk_count || 0;
  $('index-state').textContent = !base ? '未选择' : base.index_status === 'ready' ? '已就绪' : '待重建';
  $('revision').textContent = !base ? '选择一个知识库开始' : `资料版本 ${base.revision} / 索引版本 ${base.indexed_revision < 0 ? '尚未构建' : base.indexed_revision}`;
  if (base?.index_error) notice(base.index_error, true);
  $('documents').replaceChildren();
  const docs = base ? await api(`${basePath()}/documents`) : [];
  $('empty-docs').hidden = docs.length > 0;
  for (const doc of docs) {
    const row = make('tr');
    for (const value of [doc.filename, doc.size < 1024 ? `${doc.size} B` : `${(doc.size / 1024).toFixed(1)} KB`, `${doc.parent_count} / ${doc.chunk_count}`, new Date(doc.created_at).toLocaleString('zh-CN')]) row.append(make('td', value));
    const cell = make('td');
    const preview = make('button', '预览'); preview.onclick = () => task(() => showPreview(doc.id, 0));
    const download = make('a', '下载'); download.href = `${basePath()}/documents/${doc.id}/download`;
    const replace = make('button', '替换'); replace.onclick = () => { state.replacement = doc.id; $('replace-file').click(); };
    const remove = make('button', '删除', 'danger'); remove.onclick = () => {
      if (confirm(`删除“${doc.filename}”？删除后需要重建索引。`)) task(async () => {
        await api(`${basePath()}/documents/${doc.id}`, { method: 'DELETE' });
        notice('文档已删除，请重建索引。'); await refresh();
      });
    };
    cell.append(preview, download, replace, remove); row.append(cell); $('documents').append(row);
  }
  controls();
}

function baseDialog(editing) {
  state.editing = editing; $('base-name').value = editing ? current().name : '';
  $('base-desc').value = editing ? current().description : '';
  $('dialog-title').textContent = editing ? '编辑知识库' : '新建知识库';
  $('base-error').textContent = ''; $('base-dialog').showModal();
}
$('create-base').onclick = () => baseDialog(false);
$('edit-base').onclick = () => baseDialog(true);
document.querySelectorAll('[data-close]').forEach(b => b.onclick = () => $(b.dataset.close).close());
$('base-form').onsubmit = (event) => {
  event.preventDefault();
  task(async () => {
    try {
      const base = await api(state.editing ? basePath() : '/api/v1/knowledge-bases', json(state.editing ? 'PUT' : 'POST', { name: $('base-name').value.trim(), description: $('base-desc').value.trim() }));
      if (state.selected !== base.id) { $('search-results').replaceChildren(); resetChat(); }
      state.selected = base.id; $('base-dialog').close(); notice('知识库已保存。'); await refresh();
    } catch (err) { $('base-error').textContent = err.message; }
  });
};
$('delete-base').onclick = () => {
  if (confirm(`删除知识库“${current().name}”及其全部文档？此操作无法撤销。`)) task(async () => {
    await api(basePath(), { method: 'DELETE' }); state.selected = null;
    $('search-results').replaceChildren(); resetChat();
    notice('知识库已删除。'); await refresh();
  });
};
async function uploadFiles(files, replacement = null) {
  if (!state.selected) { notice('请先创建或选择知识库。', true); return; }
  await task(async () => {
    const errors = []; let success = 0;
    for (const file of files) {
      notice(`正在解析 ${file.name}…`);
      const body = new FormData(); body.append('file', file);
      try {
        await api(`${basePath()}/documents${replacement ? '/' + replacement : ''}`, { method: replacement ? 'PUT' : 'POST', body });
        success++;
      } catch (err) { errors.push(`${file.name}：${err.message}`); }
    }
    await refresh(); notice(`成功处理 ${success} 份文档。${success ? '请重建索引以启用混合检索和问答。' : ''}${errors.length ? '\n' + errors.join('\n') : ''}`, errors.length > 0);
  });
}
$('files').onchange = async e => { await uploadFiles([...e.target.files]); e.target.value = ''; };
$('replace-file').onchange = async e => { await uploadFiles([...e.target.files], state.replacement); e.target.value = ''; };
$('drop-zone').onkeydown = e => { if (['Enter', ' '].includes(e.key)) { e.preventDefault(); if (!state.busy) $('files').click(); } };
$('drop-zone').ondragover = e => { e.preventDefault(); $('drop-zone').classList.add('drag'); };
$('drop-zone').ondragleave = () => $('drop-zone').classList.remove('drag');
$('drop-zone').ondrop = e => { e.preventDefault(); $('drop-zone').classList.remove('drag'); uploadFiles([...e.dataTransfer.files]); };
$('reindex').onclick = () => task(async () => {
  notice('正在构建索引，首次加载模型可能需要较长时间，请稍候…');
  try { const result = await api(`${basePath()}/reindex`, { method: 'POST' }); notice(`索引构建完成，共 ${result.chunks} 个片段。`); }
  finally { await refresh(); }
});
async function showPreview(documentId, offset) {
  const data = await api(`${basePath()}/documents/${documentId}/chunks?offset=${offset}&limit=10`);
  state.preview = { id: documentId, offset, total: data.total };
  $('preview-title').textContent = data.filename;
  $('preview-meta').textContent = `共 ${data.total} 个片段 · 当前 ${offset + 1}–${Math.min(offset + 10, data.total)}`;
  $('preview-content').replaceChildren();
  for (const item of data.items) {
    const div = make('div', undefined, 'snippet');
    div.append(make('small', `${item.metadata.article} · ${item.metadata.chunk_id}`), make('div', item.page_content));
    $('preview-content').append(div);
  }
  $('preview-prev').disabled = offset === 0; $('preview-next').disabled = offset + 10 >= data.total;
  if (!$('preview-dialog').open) $('preview-dialog').showModal();
}
$('preview-prev').onclick = () => task(() => showPreview(state.preview.id, state.preview.offset - 10));
$('preview-next').onclick = () => task(() => showPreview(state.preview.id, state.preview.offset + 10));
document.querySelectorAll('[data-tab]').forEach(button => button.onclick = () => {
  document.querySelectorAll('[data-tab]').forEach(b => { const active = b === button; b.classList.toggle('active', active); b.setAttribute('aria-selected', String(active)); $(b.dataset.tab + '-panel').hidden = !active; });
  if (button.dataset.tab === 'chat') updateLatestButton();
});
$('search-form').onsubmit = e => {
  e.preventDefault(); if (!$('search-question').value.trim()) return;
  task(async () => {
    notice('正在检索…'); $('search-results').replaceChildren();
    const data = await api('/api/v1/search', json('POST', { knowledge_base_id: state.selected, question: $('search-question').value.trim(), mode: $('search-mode').value, top_k: Number($('top-k').value) }));
    for (const [index, item] of data.items.entries()) {
      const card = make('article', undefined, 'result');
      card.append(make('h3', `${index + 1}. ${item.metadata.source} · ${item.metadata.article}`), make('p', item.content), make('small', `${item.metadata.chapter} · 召回得分 ${item.score.toFixed(4)}${item.rerank_score == null ? '' : ' · 重排得分 ' + item.rerank_score.toFixed(4)}`));
      $('search-results').append(card);
    }
    notice(`检索完成，返回 ${data.items.length} 段依据。`);
  });
};
$('chat-form').onsubmit = e => {
  e.preventDefault(); const question = $('chat-question').value.trim(); if (!question) return;
  task(async () => {
    if ($('chat-messages').querySelector('.empty')) $('chat-messages').replaceChildren();
    const user = make('article', undefined, 'message user'); user.append(make('h3', '你'), make('p', question)); $('chat-messages').append(user);
    const pending = make('article', '正在检索资料并整理回答…', 'message pending');
    $('chat-messages').append(pending);
    $('chat-status').textContent = '正在生成回答，请稍候…';
    scrollToLatest();
    let followLatest = true;
    try {
      const data = await api('/api/v1/ask', json('POST', { knowledge_base_id: state.selected, question }));
      const messages = $('chat-messages');
      followLatest = messages.scrollHeight - messages.clientHeight - messages.scrollTop < 80;
      pending.remove();
      const answer = make('article', undefined, 'message');
      answer.append(make('h3', '知识库助手'), make('p', data.answer), make('small', `证据${data.evidence_sufficient ? '充分' : '不足'} · 引用${data.citation_valid ? '编号校验通过（不代表事实核验）' : '未通过编号校验'} · 重试 ${data.retry_count} 次`));
      for (const source of data.sources) {
        const detail = make('details'); detail.append(make('summary', `[${source.number}] ${source.source} · ${source.article}`), make('p', source.content || '未提供原文'));
        answer.append(detail);
      }
      $('chat-messages').append(answer); $('chat-question').value = ''; notice('');
    } catch (err) {
      const messages = $('chat-messages');
      followLatest = messages.scrollHeight - messages.clientHeight - messages.scrollTop < 80;
      pending.remove();
      const failed = make('article', undefined, 'message'); failed.append(make('h3', '请求失败'), make('p', err.message)); $('chat-messages').append(failed); throw err;
    } finally {
      $('chat-status').textContent = 'Ctrl / ⌘ + Enter 发送 · Enter 换行';
      if (followLatest) scrollToLatest();
      else updateLatestButton();
    }
  });
};
task(async () => {
  const health = await api('/health'); $('connection').textContent = '本地服务已连接';
  $('upload-hint').textContent = `支持 DOCX、TXT、Markdown · 单文件最大 ${health.max_upload_bytes / 1024 / 1024} MB`;
  await refresh();
  if (!health.llm_configured) notice('大模型密钥尚未配置。可以先管理文档和测试关键词检索。');
});

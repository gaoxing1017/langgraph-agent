/* =====================================================
   供应链 Agent — Frontend App
   agent_type: "logistics"
   ===================================================== */

const $ = (sel, ctx = document) => ctx.querySelector(sel);

// ── Agent meta ─────────────────────────────────────────────────────────────────
const AGENT_META = {
  place_order_agent:     { icon: '🛒', label: '下单 Agent' },
  review_order_agent:    { icon: '✅', label: '审单 Agent' },
  exception_order_agent: { icon: '⚠️', label: '异常单处理 Agent' },
  order_query_agent:     { icon: '🔍', label: '订单查询 Agent' },
  customer_query_agent:  { icon: '👤', label: '客户查询 Agent' },
  product_query_agent:   { icon: '📦', label: '商品查询 Agent' },
};

const STATUS_LABEL = {
  completed: '完成', failed: '失败', running: '运行中', pending: '等待',
};

// ── State ──────────────────────────────────────────────────────────────────────
let threads = [];
let activeThreadId = null;
let isLoading = false;
let chatStarted = false;

// ── Message history persistence ────────────────────────────────────────────────
function historyKey(id) { return `logistics_history_${id}`; }

function saveHistory(threadId, msgs) {
  try { localStorage.setItem(historyKey(threadId), JSON.stringify(msgs)); }
  catch { /* quota exceeded – ignore */ }
}

function loadHistory(threadId) {
  try { return JSON.parse(localStorage.getItem(historyKey(threadId)) || '[]'); }
  catch { return []; }
}

function deleteHistory(threadId) {
  localStorage.removeItem(historyKey(threadId));
}

// Append a message record to persisted history
function pushHistory(threadId, role, content) {
  const hist = loadHistory(threadId);
  hist.push({ role, content });
  saveHistory(threadId, hist);
}

// ── DOM refs ───────────────────────────────────────────────────────────────────
const messagesEl     = $('#messages');
const heroEl         = $('#hero');
const inputBarEl     = $('#input-bar');
const inputEl        = $('#user-input');
const heroInputEl    = $('#user-input-hero');
const sendBtn        = $('#btn-send');
const heroBtnSend    = $('#btn-hero-send');
const sidebarThreadListEl = $('#sidebar-thread-list');
const healthDot      = $('#health-dot');
const taskPanelBody  = $('#task-panel-body');
const turnBadge      = $('#turn-badge');
const entityTagsEl   = $('#active-entities');
const settingsDrawer = $('#settings-drawer');

// ── Settings ───────────────────────────────────────────────────────────────────
const apiBase       = () => $('#api-base').value.replace(/\/$/, '');
const memoryEnabled = () => $('#memory-enabled').checked;
const streamEnabled = () => $('#stream-enabled').checked;

// ══════════════════════════════════════════════════════════════════════════════
//  Health
// ══════════════════════════════════════════════════════════════════════════════
async function checkHealth() {
  try {
    const res = await fetch(`${apiBase()}/health`);
    healthDot.className = 'health-dot ' + (res.ok ? 'ok' : 'err');
    healthDot.title = res.ok ? '服务正常' : `服务异常 (${res.status})`;
  } catch {
    healthDot.className = 'health-dot err';
    healthDot.title = '无法连接到服务';
  }
}

// ══════════════════════════════════════════════════════════════════════════════
//  Thread management
// ══════════════════════════════════════════════════════════════════════════════
function saveThreads() { localStorage.setItem('logistics_threads', JSON.stringify(threads)); }

function loadThreads() {
  try { threads = JSON.parse(localStorage.getItem('logistics_threads') || '[]'); }
  catch { threads = []; }
  renderNavThreads();
}

function renderNavThreads() {
  sidebarThreadListEl.innerHTML = '';
  threads.forEach(t => {
    const li = document.createElement('li');
    li.textContent = t.title;
    li.title = t.id + '\n右键删除';
    if (t.id === activeThreadId) li.classList.add('active');
    li.addEventListener('click', () => switchThread(t.id));
    li.addEventListener('contextmenu', e => { e.preventDefault(); deleteThread(t.id); });
    sidebarThreadListEl.appendChild(li);
  });
}

async function createNewThread() {
  try {
    const res = await fetch(`${apiBase()}/api/v1/threads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'logistics-user' }),
    });
    const data = await res.json();
    const thread = { id: data.thread_id, title: '新建对话', createdAt: Date.now() };
    threads.unshift(thread);
    saveThreads();
    switchThread(thread.id);
  } catch (err) {
    appendError('创建对话失败：' + err.message);
  }
}

function switchThread(id) {
  activeThreadId = id;
  renderNavThreads();

  // Clear existing chat area
  chatStarted = false;
  const prev = messagesEl.querySelector('.chat-messages-area');
  if (prev) prev.remove();
  clearTaskPanel();
  entityTagsEl.innerHTML = '';
  turnBadge.textContent = '';

  // Restore history if exists, otherwise show hero
  const hist = id ? loadHistory(id) : [];
  if (hist.length > 0) {
    heroEl.style.display = 'none';
    inputBarEl.classList.remove('hidden');
    chatStarted = true;
    const area = document.createElement('div');
    area.className = 'chat-messages-area';
    messagesEl.appendChild(area);
    hist.forEach(({ role, content }) => {
      const avatarChar = role === 'user' ? '您' : '◈';
      const div = document.createElement('div');
      div.className = `msg ${role}`;
      div.innerHTML = `<div class="avatar">${avatarChar}</div><div class="bubble">${escapeHtml(content)}</div>`;
      area.appendChild(div);
    });
    messagesEl.scrollTop = messagesEl.scrollHeight;
  } else {
    heroEl.style.display = '';
    inputBarEl.classList.add('hidden');
  }
}

async function deleteThread(id) {
  if (!confirm('确认删除该对话？')) return;
  try { await fetch(`${apiBase()}/api/v1/threads/${id}`, { method: 'DELETE' }); }
  catch { /* best-effort */ }
  threads = threads.filter(t => t.id !== id);
  deleteHistory(id);
  saveThreads();
  if (activeThreadId === id) {
    activeThreadId = null;
    switchThread(null);
  }
  renderNavThreads();
}

// ══════════════════════════════════════════════════════════════════════════════
//  Chat area management
// ══════════════════════════════════════════════════════════════════════════════
function ensureChatArea() {
  if (chatStarted) return getChatArea();

  chatStarted = true;
  // Hide hero, show input bar
  heroEl.style.display = 'none';
  inputBarEl.classList.remove('hidden');

  const area = document.createElement('div');
  area.className = 'chat-messages-area';
  messagesEl.appendChild(area);
  return area;
}

function getChatArea() {
  return messagesEl.querySelector('.chat-messages-area');
}

// ══════════════════════════════════════════════════════════════════════════════
//  Task panel
// ══════════════════════════════════════════════════════════════════════════════
function clearTaskPanel() {
  taskPanelBody.innerHTML = '<div class="task-placeholder">发送消息后，子任务执行情况将在此显示。</div>';
  turnBadge.textContent = '';
}

function renderTaskPanel(data) {
  taskPanelBody.innerHTML = '';

  if (data.turn_count) turnBadge.textContent = `第 ${data.turn_count} 轮`;

  if (data.intent) {
    const el = document.createElement('div');
    el.className = 'intent-tag';
    el.innerHTML = `意图：<strong>${escapeHtml(data.intent)}</strong>`;
    taskPanelBody.appendChild(el);
  }

  const tasks = data.sub_tasks || [];
  if (!tasks.length) {
    const p = document.createElement('div');
    p.className = 'task-placeholder';
    p.textContent = '无子任务';
    taskPanelBody.appendChild(p);
    return;
  }

  tasks.forEach(t => {
    const meta = AGENT_META[t.agent_type] || { icon: '🤖', label: t.agent_type };
    const card = document.createElement('div');
    card.className = `subtask-card status-${t.status}`;
    card.innerHTML = `
      <div class="subtask-agent">
        <span class="subtask-agent-icon">${meta.icon}</span>
        <span class="subtask-agent-name">${meta.label}</span>
        <span class="subtask-status-dot">${STATUS_LABEL[t.status] || t.status}</span>
      </div>
      <div class="subtask-instruction">${escapeHtml(t.instruction)}</div>
      ${t.result ? `<div class="subtask-result">${escapeHtml(t.result)}</div>` : ''}
      ${t.error  ? `<div class="subtask-error">错误：${escapeHtml(t.error)}</div>` : ''}
    `;
    taskPanelBody.appendChild(card);
  });
}

// ══════════════════════════════════════════════════════════════════════════════
//  Message rendering
// ══════════════════════════════════════════════════════════════════════════════
function appendMessage(role, content = '') {
  const area = ensureChatArea();
  const avatarChar = role === 'user' ? '您' : '◈';
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.innerHTML = `
    <div class="avatar">${avatarChar}</div>
    <div class="bubble">${escapeHtml(content)}</div>
  `;
  area.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div.querySelector('.bubble');
}

function appendStreamingBubble() {
  const area = ensureChatArea();
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = `<div class="avatar">◈</div><div class="bubble streaming"></div>`;
  area.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div.querySelector('.bubble');
}

function appendError(text) {
  const area = ensureChatArea();
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = `<div class="avatar">!</div><div class="bubble error">${escapeHtml(text)}</div>`;
  area.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function updateEntityTags(data) {
  entityTagsEl.innerHTML = '';
  (data.active_orders || []).forEach(id => {
    const t = document.createElement('span');
    t.className = 'entity-tag order'; t.textContent = id;
    entityTagsEl.appendChild(t);
  });
  (data.active_shipments || []).forEach(id => {
    const t = document.createElement('span');
    t.className = 'entity-tag shipment'; t.textContent = id;
    entityTagsEl.appendChild(t);
  });
}

// ══════════════════════════════════════════════════════════════════════════════
//  Send message
// ══════════════════════════════════════════════════════════════════════════════
async function sendMessage(text) {
  text = (text || '').trim();
  if (!text || isLoading) return;

  if (!activeThreadId) await createNewThread();

  // Update thread title
  const thread = threads.find(t => t.id === activeThreadId);
  if (thread && thread.title === '新建对话') {
    thread.title = text.slice(0, 28) + (text.length > 28 ? '…' : '');
    saveThreads();
    renderNavThreads();
  }

  // Clear hero inputs
  if (heroInputEl) heroInputEl.value = '';
  if (inputEl) { inputEl.value = ''; inputEl.style.height = 'auto'; }

  setLoading(true);
  appendMessage('user', text);
  pushHistory(activeThreadId, 'user', text);

  const payload = {
    thread_id: activeThreadId,
    user_id: 'logistics-user',
    messages: [{ role: 'user', content: text }],
    agent_type: 'logistics',
    stream: streamEnabled(),
    memory_enabled: memoryEnabled(),
  };

  try {
    if (payload.stream) {
      await sendStreaming(payload);
    } else {
      await sendSync(payload);
    }
  } catch (err) {
    appendError('请求失败：' + err.message);
  } finally {
    setLoading(false);
  }
}

async function sendSync(payload) {
  taskPanelBody.innerHTML = '<div class="task-placeholder">Agent 处理中…</div>';

  const res = await fetch(`${apiBase()}/api/v1/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();

  if (!res.ok) { appendError(`服务错误 (${res.status}): ${data.detail || ''}`); clearTaskPanel(); return; }
  if (data.status === 'error') { appendError((data.errors || []).join('; ')); clearTaskPanel(); return; }

  renderTaskPanel(data);
  updateEntityTags(data);

  const answer = data.final_answer || (data.messages || []).slice(-1)[0]?.content;
  if (answer) {
    appendMessage('assistant', answer);
    pushHistory(activeThreadId, 'assistant', answer);
  } else {
    appendError('未收到有效回复');
  }
}

async function sendStreaming(payload) {
  const bubble = appendStreamingBubble();
  taskPanelBody.innerHTML = '<div class="task-placeholder">Agent 处理中…</div>';

  const res = await fetch(`${apiBase()}/api/v1/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    bubble.closest('.msg').remove();
    appendError(`服务错误 (${res.status}): ${data.detail || ''}`);
    clearTaskPanel(); return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '', fullText = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const content = line.slice(6);
      if (content === '[DONE]') break;
      fullText += content;
      bubble.textContent = fullText;
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  bubble.classList.remove('streaming');
  if (fullText) pushHistory(activeThreadId, 'assistant', fullText);
  taskPanelBody.innerHTML = '<div class="task-placeholder">流式模式下不返回子任务详情。<br/>关闭"流式"开关可查看执行明细。</div>';
}

// ══════════════════════════════════════════════════════════════════════════════
//  UI helpers
// ══════════════════════════════════════════════════════════════════════════════
function setLoading(v) {
  isLoading = v;
  if (sendBtn)    { sendBtn.disabled = v; sendBtn.textContent = v ? '处理中…' : '发送'; }
  if (heroBtnSend){ heroBtnSend.disabled = v; heroBtnSend.textContent = v ? '处理中…' : '发送'; }
  if (inputEl)    inputEl.disabled = v;
  if (heroInputEl) heroInputEl.disabled = v;
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 140) + 'px';
}

// ══════════════════════════════════════════════════════════════════════════════
//  Events
// ══════════════════════════════════════════════════════════════════════════════
$('#btn-new-thread').addEventListener('click', () => {
  activeThreadId = null;
  createNewThread();
});

$('#btn-settings-toggle').addEventListener('click', () => {
  settingsDrawer.classList.toggle('open');
});

// Close settings when clicking outside
document.addEventListener('click', e => {
  if (!settingsDrawer.contains(e.target) && e.target !== $('#btn-settings-toggle')) {
    settingsDrawer.classList.remove('open');
  }
});

// Hero send button
heroBtnSend.addEventListener('click', () => sendMessage(heroInputEl.value));
heroInputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(heroInputEl.value); }
});
heroInputEl.addEventListener('input', () => autoResize(heroInputEl));

// Bottom input bar
sendBtn.addEventListener('click', () => sendMessage(inputEl.value));
inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(inputEl.value); }
});
inputEl.addEventListener('input', () => autoResize(inputEl));

// Quick chips (delegated from messages area)
messagesEl.addEventListener('click', e => {
  if (e.target.classList.contains('chip')) {
    sendMessage(e.target.dataset.prompt);
  }
});

// API base change → recheck health
$('#api-base').addEventListener('change', checkHealth);

// ══════════════════════════════════════════════════════════════════════════════
//  Init
// ══════════════════════════════════════════════════════════════════════════════
loadThreads();
checkHealth();
setInterval(checkHealth, 30_000);

/* =====================================================
   Agent Framework — Frontend App
   API endpoints used:
     GET  /health
     POST /api/v1/threads
     DELETE /api/v1/threads/:id
     POST /api/v1/runs  (sync & streaming)
   ===================================================== */

const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

// ── State ──────────────────────────────────────────────
let threads = [];        // [{ id, title, createdAt }]
let activeThreadId = null;
let isLoading = false;

// ── DOM refs ───────────────────────────────────────────
const messagesEl   = $('#messages');
const inputEl      = $('#user-input');
const sendBtn      = $('#btn-send');
const threadListEl = $('#thread-list');
const threadTitle  = $('#thread-title');
const healthDot    = $('#health-dot');

// ── Settings helpers ───────────────────────────────────
const apiBase       = () => $('#api-base').value.replace(/\/$/, '');
const llmProvider   = () => $('#llm-provider').value;
const toolsEnabled  = () => $('#tools-enabled').checked;
const memoryEnabled = () => $('#memory-enabled').checked;
const streamEnabled = () => $('#stream-enabled').checked;

// ══════════════════════════════════════════════════════
//  Health check
// ══════════════════════════════════════════════════════
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

// ══════════════════════════════════════════════════════
//  Thread management
// ══════════════════════════════════════════════════════
function saveThreads() {
  localStorage.setItem('agent_threads', JSON.stringify(threads));
}

function loadThreads() {
  try {
    threads = JSON.parse(localStorage.getItem('agent_threads') || '[]');
  } catch {
    threads = [];
  }
  renderThreadList();
}

function renderThreadList() {
  threadListEl.innerHTML = '';
  threads.forEach(t => {
    const li = document.createElement('li');
    li.textContent = t.title;
    li.title = t.id;
    li.dataset.id = t.id;
    if (t.id === activeThreadId) li.classList.add('active');
    li.addEventListener('click', () => switchThread(t.id));
    threadListEl.appendChild(li);
  });
}

async function createNewThread() {
  try {
    const res = await fetch(`${apiBase()}/api/v1/threads`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 'frontend-user' }),
    });
    const data = await res.json();
    const thread = { id: data.thread_id, title: '新建对话', createdAt: Date.now() };
    threads.unshift(thread);
    saveThreads();
    switchThread(thread.id);
  } catch (err) {
    showError('创建对话失败：' + err.message);
  }
}

function switchThread(id) {
  activeThreadId = id;
  const t = threads.find(x => x.id === id);
  threadTitle.textContent = t ? t.title : id;
  renderThreadList();
  // Clear messages and show a placeholder
  messagesEl.innerHTML = '';
}

async function deleteActiveThread() {
  if (!activeThreadId) return;
  if (!confirm('确认删除当前对话？')) return;
  try {
    await fetch(`${apiBase()}/api/v1/threads/${activeThreadId}`, { method: 'DELETE' });
  } catch { /* best-effort */ }
  threads = threads.filter(t => t.id !== activeThreadId);
  saveThreads();
  activeThreadId = null;
  threadTitle.textContent = '新建对话';
  renderThreadList();
  messagesEl.innerHTML = buildWelcome();
}

// ══════════════════════════════════════════════════════
//  Message rendering
// ══════════════════════════════════════════════════════
function buildWelcome() {
  return `<div class="welcome">
    <h2>你好，我是 Agent</h2>
    <p>基于 LangGraph ReAct 框架，支持工具调用与多步推理。</p>
    <div class="quick-prompts">
      <button class="chip" data-prompt="你能做什么？">你能做什么？</button>
      <button class="chip" data-prompt="帮我查询天气">帮我查询天气</button>
      <button class="chip" data-prompt="解释一下 ReAct 框架">解释 ReAct 框架</button>
    </div>
  </div>`;
}

function appendMessage(role, content = '', streaming = false) {
  // Remove welcome screen on first message
  const welcome = messagesEl.querySelector('.welcome');
  if (welcome) welcome.remove();

  const avatarChar = role === 'user' ? '你' : 'AI';
  const div = document.createElement('div');
  div.className = `msg ${role}`;
  div.innerHTML = `
    <div class="avatar">${avatarChar}</div>
    <div class="bubble${streaming ? ' streaming' : ''}">${escapeHtml(content)}</div>
  `;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div.querySelector('.bubble');
}

function appendError(text) {
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = `<div class="avatar">!</div><div class="bubble error">${escapeHtml(text)}</div>`;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ══════════════════════════════════════════════════════
//  Send message
// ══════════════════════════════════════════════════════
async function sendMessage() {
  const text = inputEl.value.trim();
  if (!text || isLoading) return;

  // Auto-create thread if none active
  if (!activeThreadId) {
    await createNewThread();
  }

  // Update thread title from first message
  const thread = threads.find(t => t.id === activeThreadId);
  if (thread && thread.title === '新建对话') {
    thread.title = text.slice(0, 32) + (text.length > 32 ? '…' : '');
    saveThreads();
    threadTitle.textContent = thread.title;
    renderThreadList();
  }

  inputEl.value = '';
  inputEl.style.height = 'auto';
  setLoading(true);
  appendMessage('user', text);

  const payload = {
    thread_id: activeThreadId,
    user_id: 'frontend-user',
    messages: [{ role: 'user', content: text }],
    stream: streamEnabled(),
    llm_provider: llmProvider(),
    tools_enabled: toolsEnabled(),
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
  const res = await fetch(`${apiBase()}/api/v1/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    appendError(`服务错误 (${res.status}): ${data.detail || JSON.stringify(data)}`);
    return;
  }
  if (data.status === 'error') {
    appendError('Agent 执行错误：' + (data.errors || []).join('; '));
    return;
  }
  // Show the last assistant message
  const aiMsgs = (data.messages || []).filter(m => m.role === 'ai' || m.role === 'assistant');
  const last = aiMsgs[aiMsgs.length - 1];
  if (last) {
    appendMessage('assistant', last.content);
  } else if (data.final_answer) {
    appendMessage('assistant', data.final_answer);
  } else {
    appendError('未收到有效回复');
  }
}

async function sendStreaming(payload) {
  const res = await fetch(`${apiBase()}/api/v1/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    appendError(`服务错误 (${res.status}): ${data.detail || ''}`);
    return;
  }

  const bubble = appendMessage('assistant', '', true);
  let fullText = '';

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop(); // keep incomplete line

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
  if (!fullText) appendError('流式响应为空');
}

// ══════════════════════════════════════════════════════
//  UI helpers
// ══════════════════════════════════════════════════════
function setLoading(v) {
  isLoading = v;
  sendBtn.disabled = v;
  sendBtn.textContent = v ? '发送中…' : '发送';
  inputEl.disabled = v;
}

function autoResize() {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 160) + 'px';
}

function showError(msg) {
  appendError(msg);
}

// ══════════════════════════════════════════════════════
//  Event listeners
// ══════════════════════════════════════════════════════
$('#btn-new-thread').addEventListener('click', createNewThread);
$('#btn-delete-thread').addEventListener('click', deleteActiveThread);
$('#btn-send').addEventListener('click', sendMessage);
$('#api-base').addEventListener('change', checkHealth);

inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
inputEl.addEventListener('input', autoResize);

// Quick-prompt chips (delegated)
messagesEl.addEventListener('click', e => {
  if (e.target.classList.contains('chip')) {
    inputEl.value = e.target.dataset.prompt;
    inputEl.focus();
    sendMessage();
  }
});

// ══════════════════════════════════════════════════════
//  Init
// ══════════════════════════════════════════════════════
function init() {
  loadThreads();
  checkHealth();
  setInterval(checkHealth, 30_000);
}

init();

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
  skill_agent:           { icon: '⚡', label: 'Skill' },
};

const STATUS_LABEL = {
  completed: '完成', failed: '失败', running: '运行中', pending: '等待',
};

// 记录用户手动折叠的子任务 task_id，跨 re-render 持久化
const _collapsedTasks = new Set();

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

// Append a process-bubble snapshot (intent + final task list)
function pushProcessHistory(threadId, intent, taskMap) {
  if (!Object.keys(taskMap).length) return;
  const hist = loadHistory(threadId);
  hist.push({ role: 'process', intent, tasks: Object.values(taskMap) });
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
    hist.forEach(entry => {
      if (entry.role === 'process') {
        restoreProcessBubble(area, entry.intent || '', entry.tasks || []);
        return;
      }
      const { role, content } = entry;
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
  // Process bubble (thinking steps) + answer bubble rendered separately
  const processBubble = appendProcessBubble();
  let answerBubble = null;
  let fullAnswer = '';
  let streamFinished = false;

  // Task panel: live state map keyed by task_id
  const liveTaskMap = {};
  let liveIntent = '';
  taskPanelBody.innerHTML = '';
  turnBadge.textContent = '';

  const res = await fetch(`${apiBase()}/api/v1/runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    processBubble.closest('.msg').remove();
    appendError(`服务错误 (${res.status}): ${data.detail || ''}`);
    clearTaskPanel(); return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      let evt;
      try { evt = JSON.parse(line.slice(6)); } catch { continue; }

      switch (evt.type) {

        // ── 规划完成：渲染意图 + 待执行任务列表 ──────────────────────
        case 'plan': {
          liveIntent = evt.intent || '';
          (evt.tasks || []).forEach(t => { liveTaskMap[t.task_id] = t; });
          renderProcessBubble(processBubble, liveIntent, liveTaskMap);
          renderLiveTaskPanel(liveTaskMap);
          break;
        }

        // ── 单任务状态变更 ────────────────────────────────────────────
        case 'task_update': {
          (evt.tasks || []).forEach(t => { liveTaskMap[t.task_id] = t; });
          renderProcessBubble(processBubble, null, liveTaskMap);
          renderLiveTaskPanel(liveTaskMap);
          break;
        }

        // ── 最终回答 token ────────────────────────────────────────────
        case 'token': {
          if (!answerBubble) {
            answerBubble = appendAnswerBubble();
          }
          fullAnswer += evt.content;
          answerBubble.textContent = fullAnswer;
          messagesEl.scrollTop = messagesEl.scrollHeight;
          break;
        }

        case 'done': {
          streamFinished = true;
          finalizeProcessBubble(processBubble, liveTaskMap);
          if (answerBubble) answerBubble.classList.remove('streaming');
          if (fullAnswer)   pushHistory(activeThreadId, 'assistant', fullAnswer);
          pushProcessHistory(activeThreadId, liveIntent, liveTaskMap);
          break;
        }

        // ── HITL：缺少必要信息，等待用户补充 ──────────────────────────
        case 'interrupt': {
          streamFinished = true;
          finalizeProcessBubblePaused(processBubble);
          if (answerBubble) answerBubble.classList.remove('streaming');
          appendInterruptCard(evt.gaps || [], payload);
          break;
        }

        case 'error': {
          streamFinished = true;
          finalizeProcessBubbleError(processBubble, evt.message || '未知错误');
          if (answerBubble) answerBubble.classList.remove('streaming');
          appendError(evt.message || '未知错误');
          clearTaskPanel();
          break;
        }
      }
    }
  }

  // Stream closed without explicit done/error (e.g. server exception)
  if (!streamFinished) {
    finalizeProcessBubbleError(processBubble, '连接意外断开，请重试');
    if (!fullAnswer) appendError('服务未返回有效回复，请检查后端日志');
  }
  if (answerBubble) answerBubble.classList.remove('streaming');
}

// ── HITL interrupt card ────────────────────────────────────────────────────────
function appendInterruptCard(gaps, originalPayload) {
  const area = getChatArea();
  const div  = document.createElement('div');
  div.className = 'msg assistant';

  // Build gap rows from structured data
  const gapRows = gaps.map(g => {
    const agentLabel = escapeHtml(g.agent_label || g.agent_type);
    const chips = (g.missing_fields || []).map(f =>
      `<span class="interrupt-field-chip">${escapeHtml(f)}</span>`
    ).join('');
    return `
      <div class="interrupt-gap-item">
        <span class="interrupt-gap-agent">【${agentLabel}】</span>
        <span class="interrupt-gap-fields">${chips}</span>
      </div>`;
  }).join('');

  // Build placeholder from all missing field names
  const allFields = gaps.flatMap(g => g.missing_fields || []);
  const placeholder = allFields.length
    ? `请填写：${allFields.join('、')}`
    : '请输入补充信息';

  div.innerHTML = `
    <div class="avatar">◈</div>
    <div class="interrupt-card">
      <div class="interrupt-header">
        <span class="interrupt-icon">⚠</span>
        <span class="interrupt-title">执行前需补充以下信息</span>
      </div>
      <div class="interrupt-body">
        <div class="interrupt-gap-list">${gapRows}</div>
        <div class="interrupt-input-wrap">
          <label class="interrupt-input-label">请输入补充内容（多项用逗号分隔）：</label>
          <textarea class="interrupt-input" placeholder="${escapeHtml(placeholder)}" rows="2"></textarea>
          <div class="interrupt-input-actions">
            <span class="interrupt-hint">按 Enter 快速提交，Shift+Enter 换行</span>
            <button class="btn-interrupt-submit">确认提交</button>
          </div>
        </div>
      </div>
    </div>
  `;

  const textarea = div.querySelector('.interrupt-input');
  const btn      = div.querySelector('.btn-interrupt-submit');

  btn.addEventListener('click', async () => {
    const supplement = textarea.value.trim();
    if (!supplement) { textarea.focus(); return; }

    btn.disabled = true;
    btn.textContent = '提交中…';
    textarea.disabled = true;

    const resumePayload = { ...originalPayload, resume: supplement };
    setLoading(true);
    try {
      if (resumePayload.stream) {
        await sendStreaming(resumePayload);
      } else {
        await sendSync(resumePayload);
      }
      _markInterruptSubmitted(div, supplement, gaps);
    } catch (err) {
      btn.disabled = false;
      btn.textContent = '确认提交';
      textarea.disabled = false;
      appendError('补充信息提交失败：' + err.message);
    } finally {
      setLoading(false);
    }
  });

  textarea.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); btn.click(); }
  });

  area.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  requestAnimationFrame(() => textarea.focus());
}

function _markInterruptSubmitted(msgDiv, supplement, gaps) {
  const card = msgDiv.querySelector('.interrupt-card');
  if (!card) return;

  const fieldLabel = (gaps || []).flatMap(g => g.missing_fields || []).join(' / ') || '补充信息';

  card.innerHTML = `
    <div class="interrupt-header interrupt-header-done">
      <span class="interrupt-icon-done">✓</span>
      <span class="interrupt-title-done">已提交：${escapeHtml(fieldLabel)}</span>
    </div>
    <div class="interrupt-submitted-body">
      <span class="interrupt-submitted-label">补充内容</span>
      <div class="interrupt-submitted-value">${escapeHtml(supplement)}</div>
    </div>
  `;
}

// ── Process bubble helpers ─────────────────────────────────────────────────────

/**
 * 从 history 快照恢复一个已折叠的 process bubble（切换会话时调用）。
 */
function restoreProcessBubble(area, intent, tasks) {
  const taskMap = {};
  tasks.forEach(t => { taskMap[t.task_id] = t; });

  const div = document.createElement('div');
  div.className = 'msg assistant process-msg';
  div.innerHTML = `
    <div class="avatar">◈</div>
    <div class="process-bubble collapsed">
      <div class="process-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <span class="process-done-icon">✓</span>
        <span class="process-title">${escapeHtml(intent ? `已完成：${intent}` : '执行完成')}</span>
        <span class="process-toggle">▼</span>
      </div>
      <div class="process-body"></div>
    </div>
  `;
  area.appendChild(div);

  const bubble = div.querySelector('.process-bubble');
  renderProcessBubble(bubble, intent, taskMap);
  // 恢复时保持折叠
  bubble.classList.add('collapsed');
}

function appendProcessBubble() {
  const area = ensureChatArea();
  const div = document.createElement('div');
  div.className = 'msg assistant process-msg';
  div.innerHTML = `
    <div class="avatar">◈</div>
    <div class="process-bubble">
      <div class="process-header" onclick="this.parentElement.classList.toggle('collapsed')">
        <span class="process-spinner"></span>
        <span class="process-title">思考中…</span>
        <span class="process-toggle">▾</span>
      </div>
      <div class="process-body"></div>
    </div>
  `;
  area.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div.querySelector('.process-bubble');
}

function appendAnswerBubble() {
  const area = getChatArea();
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.innerHTML = `<div class="avatar">◈</div><div class="bubble streaming"></div>`;
  area.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div.querySelector('.bubble');
}

function renderProcessBubble(bubble, intent, taskMap) {
  const titleEl  = bubble.querySelector('.process-title');
  const spinnerEl = bubble.querySelector('.process-spinner, .process-done-icon');
  const body      = bubble.querySelector('.process-body');

  const tasks   = Object.values(taskMap);
  const allDone = tasks.length > 0 && tasks.every(t => t.status === 'completed' || t.status === 'failed');

  // Update spinner & title in the header
  if (allDone && spinnerEl && spinnerEl.classList.contains('process-spinner')) {
    spinnerEl.className = 'process-done-icon';
    spinnerEl.textContent = '✓';
  }
  if (titleEl) {
    if (allDone) {
      titleEl.textContent = intent ? `已完成：${intent}` : '执行完成';
    } else if (intent) {
      titleEl.textContent = `意图：${intent}`;
    }
  }

  // Render task rows
  body.innerHTML = '';
  if (intent && !allDone) {
    const intentRow = document.createElement('div');
    intentRow.className = 'process-intent';
    intentRow.textContent = `📋 ${intent}`;
    body.appendChild(intentRow);
  }

  tasks.forEach(t => {
    const meta       = AGENT_META[t.agent_type] || { icon: '🤖', label: t.agent_type };
    const hasDetail  = (t.result && t.status === 'completed') || !!t.error;
    const isCollapsed = _collapsedTasks.has(t.task_id);
    const row        = document.createElement('div');
    row.className    = `process-task-row status-${t.status}${isCollapsed ? ' task-collapsed' : ''}`;

    const statusIcon = {
      pending:   '<span class="proc-spin"></span>',
      running:   '<span class="proc-spin"></span>',
      completed: '✅',
      failed:    '❌',
    }[t.status] || '⏳';

    row.innerHTML = `
      <div class="proc-row-header${hasDetail ? ' clickable' : ''}">
        <span class="proc-status">${statusIcon}</span>
        <span class="proc-agent">${meta.icon} ${meta.label}</span>
        <span class="proc-instruction">${escapeHtml(t.instruction)}</span>
        ${hasDetail ? '<span class="proc-toggle">▼</span>' : ''}
      </div>
      ${hasDetail ? `
        <div class="proc-detail">
          ${t.result && t.status === 'completed'
            ? `<div class="proc-result">${escapeHtml(t.result)}</div>`
            : ''}
          ${t.error ? `<div class="proc-error">${escapeHtml(t.error)}</div>` : ''}
        </div>
      ` : ''}
    `;

    if (hasDetail) {
      row.querySelector('.proc-row-header').addEventListener('click', () => {
        const collapsed = _collapsedTasks.has(t.task_id);
        collapsed ? _collapsedTasks.delete(t.task_id) : _collapsedTasks.add(t.task_id);
        row.classList.toggle('task-collapsed');
      });
    }

    body.appendChild(row);
  });

  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function finalizeProcessBubble(bubble, taskMap) {
  const spinner = bubble.querySelector('.process-spinner');
  const title   = bubble.querySelector('.process-title');
  if (spinner) {
    spinner.className = 'process-done-icon';
    spinner.textContent = '✓';
    if (title && (title.textContent === '思考中…' || title.textContent.startsWith('意图：'))) {
      const intent = title.textContent.replace(/^意图：/, '');
      title.textContent = Object.keys(taskMap).length
        ? `已完成：${intent}`
        : '执行完成';
    }
  }
  // 执行完成后延迟自动收起（先淡出，再折叠）
  const pb = bubble.querySelector('.process-bubble');
  if (pb && !pb.classList.contains('collapsed')) {
    setTimeout(() => {
      pb.classList.add('collapsing');
      setTimeout(() => {
        pb.classList.remove('collapsing');
        pb.classList.add('collapsed');
      }, 200);
    }, 1500);
  }
}

function finalizeProcessBubbleError(bubble, message) {
  const spinner = bubble.querySelector('.process-spinner, .process-done-icon');
  const title   = bubble.querySelector('.process-title');
  if (spinner) { spinner.className = 'process-done-icon'; spinner.textContent = '✕'; spinner.style.color = 'var(--danger)'; }
  if (title)   { title.textContent = `出错：${message.slice(0, 60)}`; title.style.color = 'var(--danger)'; }
}

function finalizeProcessBubblePaused(bubble) {
  const spinner = bubble.querySelector('.process-spinner, .process-done-icon');
  const title   = bubble.querySelector('.process-title');
  if (spinner) {
    spinner.classList.remove('proc-spin');
    spinner.className = 'proc-paused-icon';
    spinner.textContent = '⏸';
    spinner.style.color = '';
  }
  if (title) {
    title.textContent = '等待补充信息';
    title.style.color = '#d97706';
  }
}

function renderLiveTaskPanel(taskMap) {
  taskPanelBody.innerHTML = '';
  const tasks = Object.values(taskMap);
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

// TPL Recruiting CRM — Full App Logic

// ── State ──
let prospects = [];
let allTasks = [];
let currentProspect = null;
let authToken = null;
const API_BASE = 'https://mission.tplcollective.ai/api';
const STAGES = ['New', 'Contacted', 'Interested', 'Deciding', 'Joined'];

// ── DOM refs ──
const $ = id => document.getElementById(id);

// ════════════════════════════════════════
// AUTH
// ════════════════════════════════════════
function checkAuth() {
  authToken = localStorage.getItem('recruiting_token');
  if (authToken) {
    showApp();
  } else {
    $('loginScreen').style.display = 'flex';
    $('appShell').classList.remove('visible');
  }
}

async function handleLogin() {
  const email = $('loginEmail').value.trim();
  const password = $('loginPassword').value;
  if (!email || !password) return;

  $('loginBtn').textContent = 'Signing in...';
  $('loginBtn').disabled = true;

  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Invalid credentials');
    }

    const data = await res.json();
    authToken = data.token;
    localStorage.setItem('recruiting_token', authToken);
    showApp();
  } catch (e) {
    $('loginError').textContent = e.message;
    $('loginError').style.display = 'block';
  } finally {
    $('loginBtn').textContent = 'Sign In';
    $('loginBtn').disabled = false;
  }
}

function logout() {
  localStorage.removeItem('recruiting_token');
  authToken = null;
  $('loginScreen').style.display = 'flex';
  $('appShell').classList.remove('visible');
}

async function showApp() {
  $('loginScreen').style.display = 'none';
  $('appShell').classList.add('visible');
  await seedIfEmpty();
  await loadProspects();
  await loadAllTasks();
}

// ════════════════════════════════════════
// SEED
// ════════════════════════════════════════
async function seedIfEmpty() {
  const { data } = await supabase.from('prospects').select('id').limit(1);
  if (data && data.length > 0) return;

  await supabase.from('prospects').insert({
    full_name: 'Paul DaQuino',
    email: 'paul.daquino@gmail.com',
    phone: '239-994-6175',
    current_brokerage: 'Broker',
    market: 'Fort Myers',
    license_number: 'BK692239',
    license_status: 'Active',
    stage: 'Deciding',
    temperature: 'hot',
    est_gci: 95000,
    notes: 'Sent tplcollective.ai preview + join link. Ready to join ~1 week.'
  });
}

// ════════════════════════════════════════
// PROSPECTS CRUD
// ════════════════════════════════════════
async function loadProspects() {
  const { data, error } = await supabase
    .from('prospects')
    .select('*')
    .order('created_at', { ascending: false });

  if (error) {
    $('prospectList').innerHTML = `<li class="loading-row" style="color: var(--red);">Error: ${esc(error.message)}</li>`;
    return;
  }

  prospects = data || [];
  renderProspects(prospects, 'prospectList', 'prospectCount');
  renderProspects(prospects, 'prospectList2', 'prospectCount2');
  updateKPIs();
  renderKanban();
  populateProspectDropdown();
}

function renderProspects(list, listId, countId) {
  const el = $(listId);
  const countEl = $(countId);
  if (!el) return;

  if (list.length === 0) {
    el.innerHTML = '<li class="loading-row">No prospects yet</li>';
    if (countEl) countEl.textContent = '0';
    return;
  }

  if (countEl) countEl.textContent = list.length;

  el.innerHTML = list.map(p => {
    const initials = getInitials(p.full_name);
    const stageLower = (p.stage || 'new').toLowerCase();
    const temp = (p.temperature || 'warm').toLowerCase();
    const gci = p.est_gci ? `$${Number(p.est_gci).toLocaleString()}` : '-';

    return `
      <li class="prospect-row" data-id="${p.id}" onclick="openDetail('${p.id}')">
        <div class="avatar">${initials}</div>
        <div class="prospect-info">
          <div class="prospect-name">${esc(p.full_name)}</div>
          <div class="prospect-brokerage">${esc(p.current_brokerage || '-')} · ${esc(p.market || '-')}</div>
        </div>
        <span class="stage-badge ${stageLower}">${esc(p.stage || 'New')}</span>
        <div class="temp-dot ${temp}" title="${temp}"></div>
        <div class="prospect-gci">${gci}</div>
      </li>`;
  }).join('');
}

async function saveProspect() {
  const name = $('fName').value.trim();
  if (!name) { toast('Name is required', true); return; }

  const payload = {
    full_name: name,
    email: $('fEmail').value.trim() || null,
    phone: $('fPhone').value.trim() || null,
    current_brokerage: $('fBrokerage').value.trim() || null,
    market: $('fMarket').value.trim() || null,
    license_number: $('fLicense').value.trim() || null,
    license_status: $('fLicenseStatus').value,
    years_licensed: parseInt($('fYears').value) || null,
    stage: $('fStage').value,
    temperature: $('fTemp').value,
    est_gci: parseFloat($('fGci').value) || null,
    notes: $('fNotes').value.trim() || null
  };

  const editId = $('prospectEditId').value;
  let error;

  if (editId) {
    ({ error } = await supabase.from('prospects').update(payload).eq('id', editId));
  } else {
    ({ error } = await supabase.from('prospects').insert(payload));
  }

  if (error) { toast('Save failed: ' + error.message, true); return; }

  closeModal('prospectModal');
  toast(editId ? 'Prospect updated' : 'Prospect added');
  await loadProspects();
  if (editId && currentProspect) openDetail(editId);
}

async function deleteProspect() {
  const id = $('prospectEditId').value;
  if (!id) return;
  if (!confirm('Delete this prospect and all their activities/tasks?')) return;

  const { error } = await supabase.from('prospects').delete().eq('id', id);
  if (error) { toast('Delete failed: ' + error.message, true); return; }

  closeModal('prospectModal');
  closeDetail();
  toast('Prospect deleted');
  await loadProspects();
}

// ════════════════════════════════════════
// KPIs
// ════════════════════════════════════════
function updateKPIs() {
  $('kpiProspects').textContent = prospects.length;

  const joined = prospects.filter(p => (p.stage || '').toLowerCase() === 'joined');
  $('kpiJoined').textContent = joined.length;

  const hot = prospects.filter(p => (p.temperature || '').toLowerCase() === 'hot');
  $('hotBadge').textContent = `${hot.length} hot`;

  const totalGci = prospects.reduce((s, p) => s + (Number(p.est_gci) || 0), 0);
  $('kpiGci').textContent = `$${totalGci.toLocaleString()}`;

  updateFollowupCount();
}

async function updateFollowupCount() {
  const today = new Date();
  const start = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString();
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1).toISOString();

  const { count } = await supabase
    .from('recruiting_tasks')
    .select('*', { count: 'exact', head: true })
    .eq('completed', false)
    .gte('due_at', start)
    .lt('due_at', end);

  $('kpiFollowups').textContent = count || 0;
}

// ════════════════════════════════════════
// DETAIL PANEL
// ════════════════════════════════════════
async function openDetail(id) {
  const p = prospects.find(x => x.id === id);
  if (!p) return;
  currentProspect = p;

  $('detailName').textContent = p.full_name;
  $('detailSubtitle').textContent = `${p.current_brokerage || '-'} · ${p.market || '-'}`;
  $('detailNotes').textContent = p.notes || 'No notes';

  const metaFields = [
    { label: 'Email', value: p.email },
    { label: 'Phone', value: p.phone },
    { label: 'License', value: p.license_number },
    { label: 'Status', value: p.license_status },
    { label: 'Years', value: p.years_licensed },
    { label: 'Est. GCI', value: p.est_gci ? `$${Number(p.est_gci).toLocaleString()}` : '-' },
    { label: 'Stage', value: p.stage },
    { label: 'Temperature', value: p.temperature }
  ];

  $('detailMeta').innerHTML = metaFields.map(m =>
    `<div class="meta-item"><label>${m.label}</label><span>${esc(String(m.value || '-'))}</span></div>`
  ).join('');

  // Load activities
  const { data: acts } = await supabase
    .from('activities')
    .select('*')
    .eq('prospect_id', id)
    .order('logged_at', { ascending: false });

  const actIcons = { call: '\u{1F4DE}', text: '\u{1F4AC}', email: '\u{1F4E7}', meeting: '\u{1F91D}', dm: '\u{1F4F1}', note: '\u{1F4DD}' };

  if (acts && acts.length > 0) {
    $('detailTimeline').innerHTML = acts.map(a => `
      <li class="timeline-item">
        <div class="timeline-icon">${actIcons[a.type] || '\u{1F4CB}'}</div>
        <div class="timeline-content">
          <div class="tl-summary">${esc(a.summary || a.type)}</div>
          <div class="tl-meta">${timeAgo(a.logged_at)}${a.duration_min ? ' · ' + a.duration_min + ' min' : ''}</div>
        </div>
      </li>`).join('');
  } else {
    $('detailTimeline').innerHTML = '<div class="empty-state">No activities logged yet</div>';
  }

  // Load tasks
  const { data: tasks } = await supabase
    .from('recruiting_tasks')
    .select('*')
    .eq('prospect_id', id)
    .order('due_at', { ascending: true });

  renderTaskList(tasks || [], 'detailTasks');

  $('detailOverlay').classList.add('open');
  $('detailPanel').classList.add('open');
}

function closeDetail() {
  $('detailOverlay').classList.remove('open');
  $('detailPanel').classList.remove('open');
  currentProspect = null;
}

// ════════════════════════════════════════
// ACTIVITIES
// ════════════════════════════════════════
async function saveActivity() {
  const prospectId = $('actProspectId').value;
  const type = $('actType').value;
  const summary = $('actSummary').value.trim();
  const duration = parseInt($('actDuration').value) || null;

  if (!summary) { toast('Summary is required', true); return; }

  const { error } = await supabase.from('activities').insert({
    prospect_id: prospectId,
    type,
    summary,
    duration_min: duration
  });

  if (error) { toast('Failed to log activity: ' + error.message, true); return; }

  closeModal('activityModal');
  toast('Activity logged');
  if (currentProspect) openDetail(currentProspect.id);
}

// ════════════════════════════════════════
// TASKS
// ════════════════════════════════════════
async function loadAllTasks() {
  const { data } = await supabase
    .from('recruiting_tasks')
    .select('*, prospects(full_name)')
    .order('due_at', { ascending: true });

  allTasks = data || [];
  renderGlobalTasks('due');
}

async function saveTask() {
  const title = $('taskTitle').value.trim();
  if (!title) { toast('Title is required', true); return; }

  const prospectId = $('taskProspectId').value || $('taskProspectSelect').value || null;
  const dueVal = $('taskDue').value;

  const { error } = await supabase.from('recruiting_tasks').insert({
    title,
    type: $('taskType').value,
    priority: $('taskPriority').value,
    due_at: dueVal ? new Date(dueVal).toISOString() : null,
    prospect_id: prospectId || null
  });

  if (error) { toast('Failed to save task: ' + error.message, true); return; }

  closeModal('taskModal');
  toast('Task created');
  await loadAllTasks();
  updateFollowupCount();
  if (currentProspect) openDetail(currentProspect.id);
}

async function toggleTask(taskId, completed) {
  const update = { completed: !completed };
  if (!completed) update.completed_at = new Date().toISOString();
  else update.completed_at = null;

  await supabase.from('recruiting_tasks').update(update).eq('id', taskId);
  await loadAllTasks();
  updateFollowupCount();
  if (currentProspect) openDetail(currentProspect.id);
}

function renderTaskList(tasks, containerId) {
  const el = $(containerId);
  if (!el) return;

  if (tasks.length === 0) {
    el.innerHTML = '<div class="empty-state">No tasks</div>';
    return;
  }

  el.innerHTML = tasks.map(t => {
    const doneClass = t.completed ? 'done' : '';
    const dueStr = t.due_at ? formatDate(t.due_at) : '';
    const isOverdue = !t.completed && t.due_at && new Date(t.due_at) < new Date();

    return `
      <div class="task-item">
        <button class="task-check ${doneClass}" onclick="toggleTask('${t.id}', ${t.completed})">${t.completed ? '\u2713' : ''}</button>
        <div class="task-info">
          <div class="task-title ${doneClass}">${esc(t.title)}</div>
          ${dueStr ? `<div class="task-due ${isOverdue ? 'overdue' : ''}">${isOverdue ? 'Overdue - ' : ''}${dueStr}</div>` : ''}
        </div>
        <span class="task-priority ${t.priority || 'medium'}">${t.priority || 'medium'}</span>
      </div>`;
  }).join('');
}

function renderGlobalTasks(filter) {
  const now = new Date();
  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);

  let filtered;
  switch (filter) {
    case 'due':
      filtered = allTasks.filter(t => !t.completed && t.due_at &&
        new Date(t.due_at) >= startOfDay && new Date(t.due_at) < endOfDay);
      break;
    case 'upcoming':
      filtered = allTasks.filter(t => !t.completed && t.due_at && new Date(t.due_at) >= endOfDay);
      break;
    case 'completed':
      filtered = allTasks.filter(t => t.completed);
      break;
    default: // all open
      filtered = allTasks.filter(t => !t.completed);
  }

  // Add prospect name to display
  const el = $('taskListGlobal');
  if (filtered.length === 0) {
    el.innerHTML = '<div class="empty-state" style="padding: 30px;">No tasks in this view</div>';
    return;
  }

  el.innerHTML = filtered.map(t => {
    const doneClass = t.completed ? 'done' : '';
    const dueStr = t.due_at ? formatDate(t.due_at) : '';
    const isOverdue = !t.completed && t.due_at && new Date(t.due_at) < now;
    const pName = t.prospects ? t.prospects.full_name : '';

    return `
      <div class="task-item" style="padding: 12px 20px;">
        <button class="task-check ${doneClass}" onclick="toggleTask('${t.id}', ${t.completed})">${t.completed ? '\u2713' : ''}</button>
        <div class="task-info">
          <div class="task-title ${doneClass}">${esc(t.title)}</div>
          <div class="task-due ${isOverdue ? 'overdue' : ''}">${pName ? esc(pName) + ' · ' : ''}${dueStr}${isOverdue ? ' (overdue)' : ''}</div>
        </div>
        <span class="task-priority ${t.priority || 'medium'}">${t.priority || 'medium'}</span>
      </div>`;
  }).join('');
}

// ════════════════════════════════════════
// PIPELINE KANBAN
// ════════════════════════════════════════
function renderKanban() {
  const board = $('kanbanBoard');
  if (!board) return;

  board.innerHTML = STAGES.map(stage => {
    const stageProspects = prospects.filter(p => (p.stage || 'New') === stage);
    const stageLower = stage.toLowerCase();

    return `
      <div class="kanban-col" data-stage="${stage}">
        <div class="kanban-col-header">
          <span class="kanban-col-title" style="color: var(--${stageColor(stage)})">${stage}</span>
          <span class="kanban-col-count">${stageProspects.length}</span>
        </div>
        <div class="kanban-cards" data-stage="${stage}"
             ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)" ondrop="handleDrop(event, '${stage}')">
          ${stageProspects.map(p => `
            <div class="kanban-card" draggable="true" data-id="${p.id}"
                 ondragstart="handleDragStart(event, '${p.id}')" onclick="openDetail('${p.id}')">
              <div class="kc-name">${esc(p.full_name)}</div>
              <div class="kc-broker">${esc(p.current_brokerage || '-')} · ${esc(p.market || '-')}</div>
              <div class="kc-footer">
                <div class="kc-gci">${p.est_gci ? '$' + Number(p.est_gci).toLocaleString() : '-'}</div>
                <div class="temp-dot ${(p.temperature || 'warm').toLowerCase()}" title="${p.temperature || 'warm'}"></div>
              </div>
            </div>`).join('')}
        </div>
      </div>`;
  }).join('');
}

function stageColor(stage) {
  const map = { New: 'accent-hi', Contacted: 'muted', Interested: 'green', Deciding: 'gold', Joined: 'green' };
  return map[stage] || 'text';
}

let draggedId = null;

function handleDragStart(e, id) {
  draggedId = id;
  e.target.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
}

function handleDragOver(e) {
  e.preventDefault();
  e.currentTarget.classList.add('drag-over');
}

function handleDragLeave(e) {
  e.currentTarget.classList.remove('drag-over');
}

async function handleDrop(e, newStage) {
  e.preventDefault();
  e.currentTarget.classList.remove('drag-over');

  if (!draggedId) return;

  const { error } = await supabase
    .from('prospects')
    .update({ stage: newStage })
    .eq('id', draggedId);

  if (error) { toast('Failed to move prospect', true); return; }

  draggedId = null;
  toast(`Moved to ${newStage}`);
  await loadProspects();
}

// ════════════════════════════════════════
// MODALS
// ════════════════════════════════════════
function openAddProspect() {
  $('prospectModalTitle').textContent = 'Add Prospect';
  $('prospectEditId').value = '';
  $('fName').value = '';
  $('fEmail').value = '';
  $('fPhone').value = '';
  $('fBrokerage').value = '';
  $('fMarket').value = '';
  $('fLicense').value = '';
  $('fLicenseStatus').value = 'Active';
  $('fYears').value = '';
  $('fStage').value = 'New';
  $('fTemp').value = 'warm';
  $('fGci').value = '';
  $('fNotes').value = '';
  $('btnDeleteProspect').style.display = 'none';
  $('prospectModal').classList.add('open');
}

function openEditProspect() {
  if (!currentProspect) return;
  const p = currentProspect;

  $('prospectModalTitle').textContent = 'Edit Prospect';
  $('prospectEditId').value = p.id;
  $('fName').value = p.full_name || '';
  $('fEmail').value = p.email || '';
  $('fPhone').value = p.phone || '';
  $('fBrokerage').value = p.current_brokerage || '';
  $('fMarket').value = p.market || '';
  $('fLicense').value = p.license_number || '';
  $('fLicenseStatus').value = p.license_status || 'Active';
  $('fYears').value = p.years_licensed || '';
  $('fStage').value = p.stage || 'New';
  $('fTemp').value = p.temperature || 'warm';
  $('fGci').value = p.est_gci || '';
  $('fNotes').value = p.notes || '';
  $('btnDeleteProspect').style.display = 'block';
  $('prospectModal').classList.add('open');
}

function openActivityModal(prospectId) {
  $('actProspectId').value = prospectId;
  $('actType').value = 'call';
  $('actSummary').value = '';
  $('actDuration').value = '';
  $('activityModal').classList.add('open');
}

function openTaskModal(prospectId) {
  $('taskProspectId').value = prospectId || '';
  $('taskTitle').value = '';
  $('taskType').value = 'follow-up';
  $('taskPriority').value = 'medium';
  $('taskDue').value = '';
  if (prospectId) {
    $('taskProspectSelect').value = prospectId;
  } else {
    $('taskProspectSelect').value = '';
  }
  $('taskModal').classList.add('open');
}

function closeModal(id) {
  $(id).classList.remove('open');
}

function populateProspectDropdown() {
  const sel = $('taskProspectSelect');
  sel.innerHTML = '<option value="">-- None --</option>' +
    prospects.map(p => `<option value="${p.id}">${esc(p.full_name)}</option>`).join('');
}

// ════════════════════════════════════════
// NAVIGATION
// ════════════════════════════════════════
function switchView(view) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

  $(`view-${view}`).classList.add('active');
  document.querySelector(`[data-view="${view}"]`).classList.add('active');

  if (view === 'pipeline') renderKanban();
  if (view === 'tasks') renderGlobalTasks('due');
}

// ════════════════════════════════════════
// SEARCH
// ════════════════════════════════════════
$('searchInput').addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase().trim();
  const list = q
    ? prospects.filter(p =>
        (p.full_name || '').toLowerCase().includes(q) ||
        (p.current_brokerage || '').toLowerCase().includes(q) ||
        (p.market || '').toLowerCase().includes(q) ||
        (p.email || '').toLowerCase().includes(q))
    : prospects;

  renderProspects(list, 'prospectList', 'prospectCount');
  renderProspects(list, 'prospectList2', 'prospectCount2');
});

// ════════════════════════════════════════
// EVENT LISTENERS
// ════════════════════════════════════════
// Auth
$('loginBtn').addEventListener('click', handleLogin);
$('loginPassword').addEventListener('keydown', e => { if (e.key === 'Enter') handleLogin(); });
$('btnLogout').addEventListener('click', logout);

// Nav
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => switchView(btn.dataset.view));
});

// Prospect modal
$('btnAddProspect').addEventListener('click', openAddProspect);
$('btnSaveProspect').addEventListener('click', saveProspect);
$('btnCancelProspect').addEventListener('click', () => closeModal('prospectModal'));
$('btnDeleteProspect').addEventListener('click', deleteProspect);

// Detail panel
$('detailOverlay').addEventListener('click', closeDetail);
$('detailClose').addEventListener('click', closeDetail);
$('btnEditProspect').addEventListener('click', openEditProspect);
$('btnLogActivity').addEventListener('click', () => {
  if (currentProspect) openActivityModal(currentProspect.id);
});
$('btnAddTask').addEventListener('click', () => {
  if (currentProspect) openTaskModal(currentProspect.id);
});

// Activity modal
$('btnSaveActivity').addEventListener('click', saveActivity);
$('btnCancelActivity').addEventListener('click', () => closeModal('activityModal'));

// Task modal
$('btnSaveTask').addEventListener('click', saveTask);
$('btnCancelTask').addEventListener('click', () => closeModal('taskModal'));
$('btnAddTaskGlobal').addEventListener('click', () => openTaskModal());

// Task filters
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    renderGlobalTasks(btn.dataset.filter);
  });
});

// Close modals on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) overlay.classList.remove('open');
  });
});

// ════════════════════════════════════════
// HELPERS
// ════════════════════════════════════════
function getInitials(name) {
  if (!name) return '?';
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function esc(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function toast(msg, isError) {
  const t = $('toast');
  t.textContent = msg;
  t.className = 'toast show' + (isError ? ' error' : '');
  setTimeout(() => t.className = 'toast', 2500);
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return formatDate(dateStr);
}

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
}

// ════════════════════════════════════════
// INIT
// ════════════════════════════════════════
checkAuth();

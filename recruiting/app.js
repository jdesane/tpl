// TPL Recruiting CRM — App Logic

// ── State ──
let prospects = [];

// ── DOM refs ──
const prospectList = document.getElementById('prospectList');
const prospectCount = document.getElementById('prospectCount');
const hotBadge = document.getElementById('hotBadge');
const kpiProspects = document.getElementById('kpiProspects');
const kpiJoined = document.getElementById('kpiJoined');
const kpiFollowups = document.getElementById('kpiFollowups');
const kpiGci = document.getElementById('kpiGci');
const searchInput = document.getElementById('searchInput');

// ── Seed Data ──
async function seedIfEmpty() {
  const { data, error } = await supabase
    .from('prospects')
    .select('id')
    .limit(1);

  if (error) {
    console.error('Seed check failed:', error.message);
    return;
  }

  if (data && data.length > 0) return; // already has data

  const { error: insertErr } = await supabase.from('prospects').insert({
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

  if (insertErr) {
    console.error('Seed insert failed:', insertErr.message);
  } else {
    console.log('Seeded initial prospect: Paul DaQuino');
  }
}

// ── Fetch Prospects ──
async function loadProspects() {
  const { data, error } = await supabase
    .from('prospects')
    .select('*')
    .order('created_at', { ascending: false });

  if (error) {
    prospectList.innerHTML = `<li class="loading-row" style="color: #ef4444;">Error loading prospects: ${error.message}</li>`;
    return;
  }

  prospects = data || [];
  renderProspects(prospects);
  updateKPIs(prospects);
}

// ── Render Prospect List ──
function renderProspects(list) {
  if (list.length === 0) {
    prospectList.innerHTML = '<li class="loading-row">No prospects yet</li>';
    prospectCount.textContent = '0';
    return;
  }

  prospectCount.textContent = list.length;

  prospectList.innerHTML = list.map(p => {
    const initials = getInitials(p.full_name);
    const stageLower = (p.stage || 'new').toLowerCase();
    const temp = (p.temperature || 'warm').toLowerCase();
    const gci = p.est_gci ? `$${Number(p.est_gci).toLocaleString()}` : '-';

    return `
      <li class="prospect-row" data-id="${p.id}">
        <div class="avatar">${initials}</div>
        <div class="prospect-info">
          <div class="prospect-name">${escapeHtml(p.full_name)}</div>
          <div class="prospect-brokerage">${escapeHtml(p.current_brokerage || '-')} · ${escapeHtml(p.market || '-')}</div>
        </div>
        <span class="stage-badge ${stageLower}">${escapeHtml(p.stage || 'New')}</span>
        <div class="temp-dot ${temp}" title="${temp}"></div>
        <div class="prospect-gci">${gci}</div>
      </li>
    `;
  }).join('');
}

// ── Update KPIs ──
function updateKPIs(list) {
  kpiProspects.textContent = list.length;

  const joined = list.filter(p => (p.stage || '').toLowerCase() === 'joined');
  kpiJoined.textContent = joined.length;

  const hot = list.filter(p => (p.temperature || '').toLowerCase() === 'hot');
  hotBadge.textContent = `${hot.length} hot prospect${hot.length !== 1 ? 's' : ''}`;

  const totalGci = list.reduce((sum, p) => sum + (Number(p.est_gci) || 0), 0);
  kpiGci.textContent = `$${totalGci.toLocaleString()}`;

  // Follow-ups: count recruiting_tasks due today (placeholder for now)
  loadFollowupCount();
}

async function loadFollowupCount() {
  const today = new Date();
  const startOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString();
  const endOfDay = new Date(today.getFullYear(), today.getMonth(), today.getDate() + 1).toISOString();

  const { count, error } = await supabase
    .from('recruiting_tasks')
    .select('*', { count: 'exact', head: true })
    .eq('completed', false)
    .gte('due_at', startOfDay)
    .lt('due_at', endOfDay);

  kpiFollowups.textContent = error ? '0' : (count || 0);
}

// ── Search ──
searchInput.addEventListener('input', (e) => {
  const q = e.target.value.toLowerCase().trim();
  if (!q) {
    renderProspects(prospects);
    return;
  }
  const filtered = prospects.filter(p =>
    (p.full_name || '').toLowerCase().includes(q) ||
    (p.current_brokerage || '').toLowerCase().includes(q) ||
    (p.market || '').toLowerCase().includes(q) ||
    (p.email || '').toLowerCase().includes(q)
  );
  renderProspects(filtered);
});

// ── Nav ──
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
  });
});

// ── Helpers ──
function getInitials(name) {
  if (!name) return '?';
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ── Init ──
async function init() {
  await seedIfEmpty();
  await loadProspects();
}

init();

/* TPL Compare - vanilla JS. Client-side only.
   Implements calcTotalCost per SPEC v2.1 section 4.
   Per-txn brokerage fees (e.g. LPT $195) always count as brokerage cost. */

(function () {
  'use strict';

  const DATA_URL = '/data/brokerages.json';
  const MAX_SELECT = 5;
  const LPT_SLUG = 'lpt-realty';

  const state = {
    all: [],
    published: [],
    selected: [],
    category: 'all',
    search: '',
    gci: 250000,
    txns: 20,
    avgGci: 12500,
    avgGciEdited: false,
    lptPlus: false,
    lptPlan: 'both'
  };

  const $ = (id) => document.getElementById(id);

  /* ────────── CALC (SPEC v2.1 §4) ────────── */
  function parseSplitPct(structure) {
    if (!structure || typeof structure !== 'string') return null;
    const m = structure.match(/^(\d+)\/(\d+)$/);
    return m ? parseInt(m[1], 10) : null;
  }

  function calcTotalCost(brokerage, plan, gci, txns, avgGciPerTxn, includeLptPlus) {
    if (!plan) return null;

    let splitCost = 0;
    let txnBrokerageFees = 0;
    const monthly = (plan.monthly_fee || 0) * 12;
    const annual = plan.annual_fee || 0;
    const eo = plan.eo_insurance_annual || 0;
    let franchise = 0;
    let marketing = 0;

    if (plan.franchise_fee_pct && plan.franchise_fee_pct > 0) {
      franchise = gci * (plan.franchise_fee_pct / 100);
      if (plan.franchise_fee_cap_annual) {
        franchise = Math.min(franchise, plan.franchise_fee_cap_annual);
      }
    }

    if (plan.marketing_fee_pct) {
      marketing = gci * (plan.marketing_fee_pct / 100);
    }

    const splitPct = parseSplitPct(plan.split_structure);
    if (splitPct !== null && !plan.flat_fee_per_txn) {
      const brokerageShare = 1 - splitPct / 100;
      const preCapCost = gci * brokerageShare;
      splitCost = plan.annual_cap ? Math.min(preCapCost, plan.annual_cap) : preCapCost;
    }

    if (plan.flat_fee_per_txn) {
      const txnsToCap = Math.floor((plan.annual_cap || 0) / plan.flat_fee_per_txn);
      splitCost = Math.min(txns, txnsToCap > 0 ? txnsToCap : txns) * plan.flat_fee_per_txn;
    }

    // Per-txn brokerage fee - ALWAYS counted. LPT $195 default pass-through
    // is a cash-flow convenience, not a cost offset.
    if (plan.per_txn_brokerage_fee) {
      txnBrokerageFees = txns * plan.per_txn_brokerage_fee;
    }

    // eXp-style post-cap-only per-txn (first 20)
    if (plan.post_cap_per_txn_fee && plan.per_txn_fee_applies_to === 'post_cap_only_first_20') {
      const sp = splitPct !== null ? splitPct : 80;
      const brokerageShare = 1 - sp / 100;
      const capTxns = Math.ceil((plan.annual_cap || 0) / (brokerageShare * avgGciPerTxn));
      const postCapTxns = Math.max(0, Math.min(txns - capTxns, 20));
      txnBrokerageFees += postCapTxns * plan.post_cap_per_txn_fee;
    }

    let optional = 0;
    if (includeLptPlus && brokerage.slug === LPT_SLUG) {
      const isBB = (plan.plan_name || '').toLowerCase().includes('business builder');
      optional = (isBB ? 149 : 89) * 12;
    }

    const total = splitCost + txnBrokerageFees + monthly + annual + eo + franchise + marketing + optional;
    const net = gci - total;
    const retainedPct = gci > 0 ? (net / gci) * 100 : 0;

    return {
      total, net, retainedPct,
      breakdown: { splitCost, txnBrokerageFees, monthly, annual, eo, franchise, marketing, optional }
    };
  }

  /* ────────── FORMATTERS ────────── */
  const fmtMoney = (n) => {
    if (n == null || isNaN(n)) return '-';
    const rounded = Math.round(n);
    return '$' + rounded.toLocaleString('en-US');
  };
  const fmtMoneyShort = (n) => {
    if (n == null || isNaN(n)) return '-';
    if (n >= 1000000) return '$' + (n / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
    if (n >= 1000) return '$' + Math.round(n / 1000) + 'K';
    return '$' + Math.round(n);
  };
  const fmtPct = (n) => (n == null || isNaN(n)) ? '-' : n.toFixed(1) + '%';

  /* ────────── URL STATE ────────── */
  function readUrlState() {
    const params = new URLSearchParams(window.location.search);
    const slugs = (params.get('brokerages') || '').split(',').map(s => s.trim()).filter(Boolean);
    const gci = parseInt(params.get('gci'), 10);
    const txns = parseInt(params.get('txns'), 10);
    const plan = params.get('plan');
    const plus = params.get('plus') === '1';
    const cat = params.get('cat');
    return {
      slugs,
      gci: !isNaN(gci) ? gci : null,
      txns: !isNaN(txns) ? txns : null,
      plan: ['bp','bb','both'].includes(plan) ? plan : null,
      plus,
      cat: ['all','cloud','franchise','luxury','hybrid'].includes(cat) ? cat : null
    };
  }

  function writeUrlState() {
    const params = new URLSearchParams();
    if (state.selected.length) params.set('brokerages', state.selected.map(b => b.slug).join(','));
    if (state.gci !== 250000) params.set('gci', String(state.gci));
    if (state.txns !== 20) params.set('txns', String(state.txns));
    if (state.lptPlan !== 'both') params.set('plan', state.lptPlan);
    if (state.lptPlus) params.set('plus', '1');
    if (state.category !== 'all') params.set('cat', state.category);
    const qs = params.toString();
    const url = '/compare' + (qs ? '?' + qs : '');
    window.history.replaceState(null, '', url);
  }

  /* ────────── GA4 ────────── */
  function track(eventName, payload) {
    if (typeof gtag === 'function') {
      try { gtag('event', eventName, payload || {}); } catch (_) {}
    }
  }

  /* ────────── LOGO HELPER ────────── */
  function logoHtml(brokerage, variant) {
    // variant: 'chip' | 'selector' | 'matrix' | 'breakdown'
    if (!brokerage || !brokerage.logo) return '';
    const cls = 'brk-logo brk-logo-' + variant;
    const alt = escapeHtml((brokerage.short_name || brokerage.name) + ' logo');
    return '<img class="' + cls + '" src="' + escapeHtml(brokerage.logo) + '" alt="' + alt + '" loading="lazy" onerror="this.style.display=\'none\'">';
  }

  function sourceFootnoteHtml(b) {
    if (!b) return '';
    const parts = [];
    if (b.source_url) {
      let host = b.source_url;
      try { host = new URL(b.source_url).hostname.replace(/^www\./, ''); } catch (e) {}
      parts.push('Source: <a href="' + escapeHtml(b.source_url) + '" target="_blank" rel="noopener">' + escapeHtml(host) + '</a>');
    }
    if (b.data_asof) {
      const asof = new Date(b.data_asof);
      const ageDays = (Date.now() - asof.getTime()) / 86400000;
      const asofStr = asof.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
      let stale = '';
      if (ageDays > 90) {
        stale = '<span class="data-stale-badge" title="Data is over 90 days old - may be out of date">Data &gt;90d old</span>';
      }
      parts.push('Verified ' + escapeHtml(asofStr) + stale);
    }
    if (!parts.length) return '';
    return '<div class="breakdown-footnote">' + parts.join(' &middot; ') + '</div>';
  }

  /* ────────── SELECTION ────────── */
  function addBrokerage(slug) {
    if (state.selected.length >= MAX_SELECT) return;
    if (state.selected.some(b => b.slug === slug)) return;
    const b = state.published.find(x => x.slug === slug);
    if (!b) return;
    state.selected.push(b);
    track('compare_selection', {
      action: 'add',
      brokerage: slug,
      selection_count: state.selected.length,
      selection: state.selected.map(x => x.slug).join(',')
    });
    render();
  }

  function removeBrokerage(slug) {
    state.selected = state.selected.filter(b => b.slug !== slug);
    track('compare_selection', {
      action: 'remove',
      brokerage: slug,
      selection_count: state.selected.length
    });
    render();
  }

  /* ────────── LPT PLANS HELPER ────────── */
  function getLptPlansForView(brokerage) {
    if (brokerage.slug !== LPT_SLUG) return brokerage.plans ? [brokerage.plans[0]] : [];
    const plans = brokerage.plans || [];
    if (state.lptPlan === 'bp')  return plans.filter(p => p.plan_name.toLowerCase().includes('brokerage partner'));
    if (state.lptPlan === 'bb')  return plans.filter(p => p.plan_name.toLowerCase().includes('business builder'));
    return plans;
  }

  function getColumnsForMatrix() {
    const cols = [];
    state.selected.forEach(b => {
      if (b.slug === LPT_SLUG) {
        getLptPlansForView(b).forEach(plan => cols.push({ brokerage: b, plan }));
      } else {
        const firstPlan = (b.plans && b.plans[0]) || null;
        cols.push({ brokerage: b, plan: firstPlan });
      }
    });
    return cols;
  }

  /* ────────── RENDER: SELECTOR ────────── */
  function renderChips() {
    const wrap = $('selected-chips');
    wrap.innerHTML = '';
    if (!state.selected.length) {
      wrap.innerHTML = '<span class="chip-empty">No brokerages selected yet.</span>';
    } else {
      state.selected.forEach(b => {
        const chip = document.createElement('span');
        chip.className = 'chip' + (b.slug === LPT_SLUG ? ' lpt' : '');
        chip.innerHTML = logoHtml(b, 'chip') + '<span>' + escapeHtml(b.short_name || b.name) + '</span>';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.setAttribute('aria-label', 'Remove ' + b.name);
        btn.textContent = '×';
        btn.addEventListener('click', () => removeBrokerage(b.slug));
        chip.appendChild(btn);
        wrap.appendChild(chip);
      });
    }
    $('selected-count').textContent = String(state.selected.length);
  }

  function renderSelectorList() {
    const list = $('selector-list');
    const empty = $('selector-empty');
    list.innerHTML = '';
    const q = state.search.trim().toLowerCase();

    const filtered = state.published.filter(b => {
      if (state.category !== 'all' && b.category !== state.category) return false;
      if (!q) return true;
      const hay = [b.name, b.short_name, ...(b.aliases || [])].filter(Boolean).join(' ').toLowerCase();
      return hay.includes(q);
    });

    filtered.sort((a, b) => {
      const t = (a.tier || 9) - (b.tier || 9);
      return t !== 0 ? t : (a.name || '').localeCompare(b.name || '');
    });

    if (!filtered.length) {
      list.hidden = true;
      empty.hidden = false;
      return;
    }
    list.hidden = false;
    empty.hidden = true;

    filtered.forEach(b => {
      const alreadySelected = state.selected.some(x => x.slug === b.slug);
      const row = document.createElement('div');
      row.className = 'selector-row';
      row.setAttribute('role', 'option');
      if (alreadySelected) row.setAttribute('aria-disabled', 'true');
      row.innerHTML =
        '<div class="selector-row-logo">' + logoHtml(b, 'selector') + '</div>' +
        '<div class="selector-row-name">' + escapeHtml(b.name) + '</div>' +
        '<div class="selector-row-cat">' + escapeHtml(b.category || '') + '</div>' +
        '<button type="button" class="selector-row-add">' + (alreadySelected ? 'Added' : 'Add') + '</button>';
      const action = () => {
        if (alreadySelected) return;
        if (state.selected.length >= MAX_SELECT) return;
        addBrokerage(b.slug);
      };
      row.addEventListener('click', action);
      list.appendChild(row);
    });
  }

  /* ────────── RENDER: MATRIX ────────── */
  function renderMatrix() {
    const panel = $('matrix-panel');
    const empty = $('cmp-empty');
    const share = $('cmp-share');
    const breakdownSection = $('breakdown-section');

    if (!state.selected.length) {
      panel.hidden = true;
      empty.hidden = false;
      share.hidden = true;
      breakdownSection.hidden = true;
      return;
    }
    empty.hidden = true;
    panel.hidden = false;
    share.hidden = false;
    breakdownSection.hidden = false;

    const cols = getColumnsForMatrix();
    $('matrix-hint').textContent =
      '@ ' + fmtMoneyShort(state.gci) + ' GCI · ' + state.txns + ' txns';

    const rowGroups = [
      { label: 'Overview', rows: [
        { label: 'Model', fn: (c) => safe(c.brokerage.model_type) },
        { label: 'Founded', fn: (c) => safe(c.brokerage.founded) },
        { label: 'Public Ticker', fn: (c) => safe(c.brokerage.public_ticker) },
        { label: 'Data as of', fn: (c) => safe(c.brokerage.data_asof) }
      ]},
      { label: 'Cost Structure', rows: [
        { label: 'Plan', fn: (c) => c.plan ? safe(c.plan.plan_name) : '-' },
        { label: 'Split', fn: (c) => c.plan ? safe(c.plan.split_structure) : '-' },
        { label: 'Annual Cap', fn: (c) => c.plan ? (c.plan.annual_cap ? fmtMoney(c.plan.annual_cap) : (c.plan.cap_note || 'No cap')) : '-' },
        { label: 'Monthly Fee', fn: (c) => c.plan ? (c.plan.monthly_fee != null ? fmtMoney(c.plan.monthly_fee) + '/mo' : '-') : '-' },
        { label: 'Annual Fee', fn: (c) => c.plan ? (c.plan.annual_fee != null ? fmtMoney(c.plan.annual_fee) : '-') + (c.plan.annual_fee_note ? '<span class="val-sub">' + escapeHtml(c.plan.annual_fee_note) + '</span>' : '') : '-' },
        { label: 'E&O', fn: (c) => c.plan ? (c.plan.eo_insurance_annual != null ? fmtMoney(c.plan.eo_insurance_annual) + '/yr' : '-') + (c.plan.eo_note ? '<span class="val-sub">' + escapeHtml(c.plan.eo_note) + '</span>' : '') : '-' },
        { label: 'Franchise Royalty', fn: (c) => c.plan && c.plan.franchise_fee_pct ? c.plan.franchise_fee_pct + '%' + (c.plan.franchise_fee_cap_annual ? '<span class="val-sub">cap ' + fmtMoney(c.plan.franchise_fee_cap_annual) + '/yr</span>' : '') : 'None' },
        { label: 'Per-Txn Brokerage Fee', fn: (c) => c.plan ? (c.plan.per_txn_brokerage_fee ? fmtMoney(c.plan.per_txn_brokerage_fee) + '/txn' : (c.plan.flat_fee_per_txn ? fmtMoney(c.plan.flat_fee_per_txn) + '/txn (flat)' : '-')) : '-' }
      ]},
      { label: 'Calculated Total Annual Cost', rows: [
        { label: 'Total Brokerage Cost', kind: 'cost', fn: (c) => {
            const r = calcTotalCost(c.brokerage, c.plan, state.gci, state.txns, state.avgGci, state.lptPlus);
            return r ? '<span class="val-sub">at ' + fmtMoneyShort(state.gci) + ' GCI</span>' + fmtMoney(r.total) : '-';
          } },
        { label: 'Net to Agent', kind: 'net', fn: (c) => {
            const r = calcTotalCost(c.brokerage, c.plan, state.gci, state.txns, state.avgGci, state.lptPlus);
            return r ? fmtMoney(r.net) : '-';
          } },
        { label: 'Retained %', kind: 'pct', fn: (c) => {
            const r = calcTotalCost(c.brokerage, c.plan, state.gci, state.txns, state.avgGci, state.lptPlus);
            return r ? fmtPct(r.retainedPct) : '-';
          } }
      ]},
      { label: 'Revenue Share', rows: [
        { label: 'Offered', fn: (c) => c.brokerage.revshare && c.brokerage.revshare.offered ? 'Yes' : 'No' },
        { label: 'Program Name', fn: (c) => c.brokerage.revshare ? safe(c.brokerage.revshare.program_name) : '-' },
        { label: 'Tiers', fn: (c) => c.brokerage.revshare ? safe(c.brokerage.revshare.tiers) : '-' },
        { label: 'Pool % of Company Dollar', fn: (c) => c.brokerage.revshare && c.brokerage.revshare.pool_pct_of_company_dollar ? c.brokerage.revshare.pool_pct_of_company_dollar + '%' : '-' },
        { label: 'Willable', fn: (c) => c.brokerage.revshare ? (c.brokerage.revshare.willable === true ? 'Yes' : c.brokerage.revshare.willable === false ? 'No' : '-') : '-' },
        { label: 'Vesting', fn: (c) => {
            const rs = c.brokerage.revshare;
            if (!rs) return '-';
            if (rs.vesting_schedule) return escapeHtml(rs.vesting_schedule);
            if (rs.vesting_years != null) return rs.vesting_years === 0 ? 'Immediate' : rs.vesting_years + ' yrs';
            return '-';
          } }
      ]},
      { label: 'Equity / Stock', rows: [
        { label: 'Offered', fn: (c) => c.brokerage.equity && c.brokerage.equity.offered ? 'Yes' : 'No' },
        { label: 'Publicly Traded', fn: (c) => c.brokerage.equity && c.brokerage.equity.publicly_traded ? 'Yes (' + (c.brokerage.equity.ticker || '-') + ')' : 'No' },
        { label: 'Stock Type', fn: (c) => c.brokerage.equity ? safe(c.brokerage.equity.stock_type) : '-' },
        { label: 'Vesting', fn: (c) => c.brokerage.equity && c.brokerage.equity.vesting_years != null ? c.brokerage.equity.vesting_years + ' yrs' : '-' },
        { label: 'Liquidity', fn: (c) => c.brokerage.equity ? safe(c.brokerage.equity.liquidity) : '-' }
      ]},
      { label: 'Technology', rows: [
        { label: 'CRM Included', fn: (c) => c.brokerage.technology && c.brokerage.technology.crm_included ? 'Yes' : 'No' },
        { label: 'Included Tools', fn: (c) => c.brokerage.technology && c.brokerage.technology.included_tools && c.brokerage.technology.included_tools.length
            ? c.brokerage.technology.included_tools.map(t => escapeHtml(t)).join('<span class="val-sub" style="display:inline;color:var(--dim);">, </span>')
            : '-' }
      ]},
      { label: 'Training & Support', rows: [
        { label: 'Live Hours / Week', fn: (c) => c.brokerage.training && c.brokerage.training.live_hours_per_week != null ? c.brokerage.training.live_hours_per_week + ' hrs' : '-' },
        { label: 'On-Demand Library', fn: (c) => c.brokerage.training ? (c.brokerage.training.on_demand_library ? 'Yes' : '-') : '-' },
        { label: 'Mentorship', fn: (c) => c.brokerage.training ? (c.brokerage.training.mentorship_program ? 'Yes' : '-') : '-' }
      ]},
      { label: 'Culture', rows: [
        { label: 'Office-Based', fn: (c) => c.brokerage.culture ? (c.brokerage.culture.office_based === true ? 'Yes' : c.brokerage.culture.office_based === false ? 'No (remote/cloud)' : '-') : '-' },
        { label: 'Community Style', fn: (c) => c.brokerage.culture ? safe(c.brokerage.culture.community_style) : '-' }
      ]}
    ];

    const table = $('matrix-table');
    const headerHtml = '<thead><tr>' +
      '<th>Attribute</th>' +
      cols.map(c => {
        const isLpt = c.brokerage.slug === LPT_SLUG;
        const planLabel = isLpt && c.plan ? c.plan.plan_name.replace(/\s*\([^)]*\)\s*/, '').trim() : (c.brokerage.category || '');
        const subLabel = isLpt ? planLabel : (c.brokerage.category || '');
        return '<th class="' + (isLpt ? 'col-lpt' : '') + '">' +
          '<div class="col-logo-wrap">' + logoHtml(c.brokerage, 'matrix') + '</div>' +
          '<div class="col-name">' + escapeHtml(c.brokerage.short_name || c.brokerage.name) + '</div>' +
          '<span class="col-cat">' + escapeHtml(subLabel) + '</span>' +
          '</th>';
      }).join('') +
      '</tr></thead>';

    const bodyHtml = '<tbody>' + rowGroups.map(g => {
      const groupRow = '<tr class="row-group"><td colspan="' + (cols.length + 1) + '">' + escapeHtml(g.label) + '</td></tr>';
      const rows = g.rows.map(r => {
        return '<tr><td>' + escapeHtml(r.label) + '</td>' +
          cols.map(c => {
            const isLpt = c.brokerage.slug === LPT_SLUG;
            const cellClass = [
              isLpt ? 'col-lpt' : '',
              r.kind === 'cost' ? 'val-total negative' : '',
              r.kind === 'net'  ? 'val-total positive' : '',
              r.kind === 'pct'  ? 'val-pct' : ''
            ].filter(Boolean).join(' ');
            let content;
            try { content = r.fn(c); } catch (_) { content = '-'; }
            if (content == null || content === '' || content === 'null') content = '-';
            return '<td class="' + cellClass + '">' + content + '</td>';
          }).join('') +
          '</tr>';
      }).join('');
      return groupRow + rows;
    }).join('') + '</tbody>';

    table.innerHTML = headerHtml + bodyHtml;
  }

  /* ────────── RENDER: BREAKDOWN CARDS ────────── */
  function renderBreakdown() {
    const grid = $('breakdown-grid');
    grid.innerHTML = '';
    const cols = getColumnsForMatrix();

    cols.forEach(col => {
      const b = col.brokerage;
      const plan = col.plan;
      const card = document.createElement('div');
      card.className = 'breakdown-card' + (b.slug === LPT_SLUG ? ' lpt' : '');

      if (!plan || b.status !== 'published') {
        card.classList.add('pending');
        card.innerHTML =
          '<div class="breakdown-header">' +
            '<div class="breakdown-name">' + escapeHtml(b.short_name || b.name) + '</div>' +
            '<div class="breakdown-plan">' + escapeHtml(b.category || '') + '</div>' +
          '</div>' +
          '<div class="breakdown-body">' +
            '<div class="breakdown-pending-badge">Data Pending Verification</div>' +
            '<p>Published numbers coming soon. Until then this entry is excluded from the cost calculation.</p>' +
          '</div>';
        grid.appendChild(card);
        return;
      }

      const r = calcTotalCost(b, plan, state.gci, state.txns, state.avgGci, state.lptPlus);
      const planLabel = plan.plan_name;
      const bd = r.breakdown;

      const rows = [];
      if (bd.splitCost > 0) {
        const label = plan.flat_fee_per_txn ? 'Flat fees to cap' : 'Split to cap';
        rows.push(rowHtml(label, plan.flat_fee_per_txn
            ? Math.min(state.txns, Math.floor((plan.annual_cap || 0) / plan.flat_fee_per_txn)) + ' × ' + fmtMoney(plan.flat_fee_per_txn)
            : plan.split_structure + ' until ' + fmtMoney(plan.annual_cap || 0) + ' cap',
          bd.splitCost));
      }
      if (bd.txnBrokerageFees > 0) {
        rows.push(rowHtml('Per-txn brokerage fee',
          state.txns + ' × ' + fmtMoney(plan.per_txn_brokerage_fee || (plan.post_cap_per_txn_fee || 0)),
          bd.txnBrokerageFees));
      }
      rows.push(rowHtml('Monthly fee', (plan.monthly_fee ? fmtMoney(plan.monthly_fee) + '/mo × 12' : 'No monthly fees'), bd.monthly, bd.monthly === 0));
      rows.push(rowHtml('Annual fee', plan.annual_fee_note || 'Annual fee', bd.annual, bd.annual === 0));
      if (bd.eo > 0 || !plan.eo_note) {
        rows.push(rowHtml('E&O insurance', plan.eo_note || 'Annual E&O', bd.eo, bd.eo === 0));
      }
      if (bd.franchise > 0) rows.push(rowHtml('Franchise royalty', plan.franchise_fee_pct + '% (cap ' + fmtMoney(plan.franchise_fee_cap_annual || 0) + ')', bd.franchise));
      if (bd.marketing > 0) rows.push(rowHtml('Marketing fee', plan.marketing_fee_pct + '%', bd.marketing));
      if (bd.optional > 0) rows.push(rowHtml('LPT Plus upgrade', 'Optional tech add-on', bd.optional));

      const isLpt = b.slug === LPT_SLUG;
      const isLptWithPerTxn = isLpt && plan.per_txn_brokerage_fee;

      card.innerHTML =
        '<div class="breakdown-header">' +
          logoHtml(b, 'breakdown') +
          '<div class="breakdown-name">' + escapeHtml(b.short_name || b.name) + '</div>' +
          '<div class="breakdown-plan">' + escapeHtml(planLabel) + '</div>' +
        '</div>' +
        '<div class="breakdown-meta">@ ' + fmtMoneyShort(state.gci) + ' GCI · ' + state.txns + ' txns</div>' +
        '<div class="breakdown-list">' + rows.join('') + '</div>' +
        '<div class="breakdown-total">' +
          '<div class="breakdown-total-row">' +
            '<span class="breakdown-total-label">Total brokerage cost</span>' +
            '<span class="breakdown-total-val cost">' + fmtMoney(r.total) + '</span>' +
          '</div>' +
          '<div class="breakdown-total-row">' +
            '<span class="breakdown-total-label">Net to agent</span>' +
            '<span class="breakdown-total-val net">' + fmtMoney(r.net) + '</span>' +
          '</div>' +
          '<div class="breakdown-retained">' + fmtPct(r.retainedPct) + ' retained</div>' +
        '</div>' +
        (isLptWithPerTxn
          ? '<div class="breakdown-note gold">The $' + plan.per_txn_brokerage_fee + ' per-txn fee is typically passed through to the client at closing, so the agent\'s out-of-pocket is often lower than the total above. It is still counted here so the math matches apples-to-apples against other brokerages.</div>'
          : '') +
        (isLpt && plan.plan_name.toLowerCase().includes('brokerage partner')
          ? '<div class="breakdown-note">Plus: full HybridShare eligibility - up to $2,325/yr per Tier 1 BP downline. See the HybridShare panel below.</div>'
          : '') +
        (isLpt && plan.plan_name.toLowerCase().includes('business builder')
          ? '<div class="breakdown-note">BB agents can recruit and build a downline. HybridShare earnings activate on upgrade to Brokerage Partner; the downline tree carries over.</div>'
          : '') +
        sourceFootnoteHtml(b);

      grid.appendChild(card);
    });
  }

  function rowHtml(label, sub, val, muted) {
    return '<div class="breakdown-row' + (muted ? ' muted' : '') + '">' +
      '<div class="breakdown-row-label">' + escapeHtml(label) + (sub ? '<span class="sub">' + escapeHtml(sub) + '</span>' : '') + '</div>' +
      '<div class="breakdown-row-val">' + fmtMoney(val) + '</div>' +
      '</div>';
  }

  /* ────────── RENDER: HYBRIDSHARE + TPL CALLOUT ────────── */
  function renderHybridshare() {
    const panel = $('hybridshare-panel');
    const lpt = state.selected.find(b => b.slug === LPT_SLUG);
    if (!lpt || !lpt.revshare || !lpt.revshare.tier_breakdown) {
      panel.hidden = true; return;
    }
    panel.hidden = false;

    const tiers = lpt.revshare.tier_breakdown;
    const table = $('hybridshare-table');
    table.innerHTML =
      '<thead><tr>' +
        '<th>Tier</th>' +
        '<th>% of Pool</th>' +
        '<th>Max / BP Downline</th>' +
        '<th>Max / BB Downline</th>' +
        '<th>Min Directs to Unlock</th>' +
      '</tr></thead>' +
      '<tbody>' + tiers.map(t => (
        '<tr>' +
          '<td class="tier-num">T' + t.tier + '</td>' +
          '<td class="pct">' + t.pct_of_pool + '%</td>' +
          '<td>' + fmtMoney(t.max_annual_from_bp_downline_usd) + '/yr</td>' +
          '<td>' + fmtMoney(t.max_annual_from_bb_downline_usd) + '/yr</td>' +
          '<td>' + t.min_active_direct_sponsored_to_unlock + '</td>' +
        '</tr>'
      )).join('') + '</tbody>';
  }

  function renderTplCallout() {
    const panel = $('tpl-callout-panel');
    const lpt = state.selected.find(b => b.slug === LPT_SLUG);
    if (!lpt || !lpt.tpl_callout) { panel.hidden = true; return; }
    panel.hidden = false;
    $('tpl-callout-body').textContent = lpt.tpl_callout;
  }

  /* ────────── RENDER: DISPATCH ────────── */
  function render() {
    renderChips();
    renderSelectorList();
    renderMatrix();
    renderBreakdown();
    renderHybridshare();
    renderTplCallout();
    const hasLpt = state.selected.some(b => b.slug === LPT_SLUG);
    $('lpt-plan-toggle').hidden = !hasLpt;
    writeUrlState();
  }

  /* ────────── UTIL ────────── */
  function safe(v) { return (v == null || v === '') ? '-' : escapeHtml(String(v)); }
  function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  /* ────────── WIRING ────────── */
  function wire() {
    $('brokerage-search').addEventListener('input', (e) => {
      state.search = e.target.value;
      renderSelectorList();
    });

    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.category = btn.dataset.category;
        renderSelectorList();
        writeUrlState();
      });
    });

    $('gci-slider').addEventListener('input', (e) => {
      state.gci = parseInt(e.target.value, 10);
      $('gci-value').textContent = fmtMoney(state.gci);
      if (!state.avgGciEdited && state.txns > 0) {
        state.avgGci = Math.round(state.gci / state.txns);
        $('avg-gci').value = state.avgGci;
      }
      renderMatrix(); renderBreakdown(); writeUrlState();
    });
    $('txns-slider').addEventListener('input', (e) => {
      state.txns = parseInt(e.target.value, 10);
      $('txns-value').textContent = String(state.txns);
      if (!state.avgGciEdited && state.txns > 0) {
        state.avgGci = Math.round(state.gci / state.txns);
        $('avg-gci').value = state.avgGci;
      }
      renderMatrix(); renderBreakdown(); writeUrlState();
    });
    $('avg-gci').addEventListener('input', (e) => {
      const v = parseInt(e.target.value, 10);
      if (!isNaN(v) && v > 0) {
        state.avgGci = v;
        state.avgGciEdited = true;
        renderMatrix(); renderBreakdown();
      }
    });

    $('lpt-plus-toggle').addEventListener('change', (e) => {
      state.lptPlus = e.target.checked;
      renderMatrix(); renderBreakdown(); writeUrlState();
    });

    document.querySelectorAll('.plan-toggle-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.plan-toggle-btn').forEach(b => {
          b.classList.remove('active');
          b.setAttribute('aria-checked', 'false');
        });
        btn.classList.add('active');
        btn.setAttribute('aria-checked', 'true');
        state.lptPlan = btn.dataset.plan;
        renderMatrix(); renderBreakdown(); writeUrlState();
      });
    });

    $('copy-link-btn').addEventListener('click', async () => {
      writeUrlState();
      const url = window.location.origin + window.location.pathname + window.location.search;
      try {
        await navigator.clipboard.writeText(url);
      } catch (_) {
        const ta = document.createElement('textarea');
        ta.value = url; document.body.appendChild(ta);
        ta.select(); document.execCommand('copy'); ta.remove();
      }
      const fb = $('share-feedback');
      fb.hidden = false;
      setTimeout(() => { fb.hidden = true; }, 2000);
      track('compare_share', {
        selection: state.selected.map(b => b.slug).join(','),
        gci: state.gci, txns: state.txns, plan: state.lptPlan
      });
    });
  }

  /* ────────── INIT ────────── */
  function applyUrlState() {
    const u = readUrlState();
    if (u.gci != null) { state.gci = Math.max(50000, Math.min(1000000, u.gci)); }
    if (u.txns != null) { state.txns = Math.max(1, Math.min(60, u.txns)); }
    if (u.plan) state.lptPlan = u.plan;
    if (u.plus) state.lptPlus = true;
    if (u.cat) state.category = u.cat;

    const hasUrlSelection = u.slugs.length > 0;
    const initialSlugs = hasUrlSelection ? u.slugs : [LPT_SLUG];
    initialSlugs.forEach(slug => {
      const b = state.published.find(x => x.slug === slug);
      if (b && state.selected.length < MAX_SELECT) state.selected.push(b);
    });

    state.avgGci = state.txns > 0 ? Math.round(state.gci / state.txns) : 12500;

    $('gci-slider').value = state.gci;
    $('gci-value').textContent = fmtMoney(state.gci);
    $('txns-slider').value = state.txns;
    $('txns-value').textContent = String(state.txns);
    $('avg-gci').value = state.avgGci;
    $('lpt-plus-toggle').checked = state.lptPlus;

    document.querySelectorAll('.filter-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.category === state.category);
    });
    document.querySelectorAll('.plan-toggle-btn').forEach(b => {
      const match = b.dataset.plan === state.lptPlan;
      b.classList.toggle('active', match);
      b.setAttribute('aria-checked', match ? 'true' : 'false');
    });
  }

  async function init() {
    try {
      const res = await fetch(DATA_URL, { cache: 'no-store' });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const json = await res.json();
      state.all = json.brokerages || [];
      const previewMode = /[?&]preview=1\b/.test(window.location.search);
      state.published = previewMode
        ? state.all.slice()
        : state.all.filter(b => b.status === 'published');
    } catch (err) {
      console.error('Failed to load brokerages.json', err);
      $('selector-list').innerHTML =
        '<div class="selector-empty" style="padding:20px;">Could not load brokerage data. Please refresh.</div>';
      return;
    }
    wire();
    applyUrlState();
    render();
    track('compare_loaded', {
      initial_selection: state.selected.map(b => b.slug).join(','),
      published_count: state.published.length
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

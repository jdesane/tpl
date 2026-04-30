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
    lptPlan: 'both',
    growth: 10,
    stateFilter: 'all'
  };

  /* ────────── PERSONA QUIZ ────────── */
  const QUIZ = {
    steps: [
      {
        key: 'production',
        q: 'How many deals do you close per year?',
        options: [
          { label: '1-5 (new or part-time)', val: 'new' },
          { label: '6-15 (building)', val: 'building' },
          { label: '16-30 (established)', val: 'established' },
          { label: '30+ (top producer)', val: 'top' }
        ]
      },
      {
        key: 'recruit',
        q: 'Do you want to recruit agents and earn from their production?',
        options: [
          { label: 'Yes — building a team is the goal', val: 'yes' },
          { label: 'Maybe someday', val: 'maybe' },
          { label: 'No — I just want to sell', val: 'no' }
        ]
      },
      {
        key: 'brand',
        q: 'How much does the brand name on your sign matter?',
        options: [
          { label: 'Critical — I want a household name', val: 'critical' },
          { label: 'Helpful, but not required', val: 'helpful' },
          { label: 'Irrelevant — clients hire me, not a logo', val: 'irrelevant' }
        ]
      },
      {
        key: 'fees',
        q: 'What type of fee structure do you prefer?',
        options: [
          { label: 'Low/no monthly fees, pay per transaction', val: 'pertxn' },
          { label: 'Fixed cap, then 100% for the year', val: 'cap' },
          { label: 'Flat monthly fee, keep 100% of commissions', val: 'flat' }
        ]
      },
      {
        key: 'office',
        q: 'Do you want in-person office space and staff support?',
        options: [
          { label: 'Yes — I rely on a physical office', val: 'yes' },
          { label: 'Occasional — training or meetings only', val: 'sometimes' },
          { label: 'No — I work from home/remote', val: 'no' }
        ]
      }
    ],
    // Scoring: map answer combos → brokerage slug weights
    score(answers) {
      const s = {};
      const bump = (slug, n) => { s[slug] = (s[slug] || 0) + n; };

      // LPT always has a baseline (page bias, earned by math elsewhere)
      bump('lpt-realty', 5);

      // Production level
      if (answers.production === 'new') { bump('lpt-realty', 3); bump('keller-williams', 2); bump('real-brokerage', 1); }
      if (answers.production === 'building') { bump('lpt-realty', 3); bump('exp-realty', 2); bump('real-brokerage', 2); }
      if (answers.production === 'established') { bump('lpt-realty', 4); bump('exp-realty', 3); bump('real-brokerage', 2); bump('compass', 1); }
      if (answers.production === 'top') { bump('lpt-realty', 3); bump('compass', 3); bump('exp-realty', 2); bump('sothebys', 2); }

      // Recruiting
      if (answers.recruit === 'yes') { bump('lpt-realty', 5); bump('exp-realty', 5); bump('real-brokerage', 3); bump('epique-realty', 2); }
      if (answers.recruit === 'maybe') { bump('lpt-realty', 3); bump('exp-realty', 2); bump('real-brokerage', 2); }
      if (answers.recruit === 'no') { bump('redfin', 2); bump('compass', 1); bump('homesmart', 1); }

      // Brand
      if (answers.brand === 'critical') { bump('keller-williams', 3); bump('coldwell-banker', 3); bump('berkshire-hathaway', 3); bump('century-21', 2); bump('remax', 3); bump('compass', 2); bump('sothebys', 3); bump('douglas-elliman', 3); }
      if (answers.brand === 'helpful') { bump('exp-realty', 2); bump('keller-williams', 2); bump('compass', 2); bump('real-brokerage', 1); }
      if (answers.brand === 'irrelevant') { bump('lpt-realty', 4); bump('real-brokerage', 2); bump('epique-realty', 2); bump('fathom-realty', 2); bump('homesmart', 2); bump('lokation', 1); bump('samson-properties', 1); }

      // Fee structure
      if (answers.fees === 'pertxn') { bump('lpt-realty', 5); bump('homesmart', 3); bump('united-real-estate', 3); bump('fathom-realty', 3); }
      if (answers.fees === 'cap') { bump('keller-williams', 3); bump('exp-realty', 3); bump('real-brokerage', 3); bump('remax', 2); bump('coldwell-banker', 2); bump('compass', 2); }
      if (answers.fees === 'flat') { bump('homesmart', 3); bump('realty-one-group', 3); bump('epique-realty', 3); bump('united-real-estate', 2); }

      // Office support
      if (answers.office === 'yes') { bump('keller-williams', 3); bump('coldwell-banker', 3); bump('remax', 2); bump('century-21', 2); bump('berkshire-hathaway', 2); }
      if (answers.office === 'sometimes') { bump('lpt-realty', 1); bump('exp-realty', 1); bump('compass', 1); }
      if (answers.office === 'no') { bump('lpt-realty', 4); bump('exp-realty', 3); bump('real-brokerage', 3); bump('epique-realty', 2); bump('fathom-realty', 2); }

      return s;
    }
  };

  const quizState = { idx: 0, answers: {} };

  function renderQuizStep() {
    const step = QUIZ.steps[quizState.idx];
    const body = $('quiz-body');
    const isLast = quizState.idx === QUIZ.steps.length - 1;
    body.innerHTML =
      '<h3 class="quiz-q">' + escapeHtml(step.q) + '</h3>' +
      '<div class="quiz-options">' +
      step.options.map((opt, i) =>
        '<button type="button" class="quiz-option' + (quizState.answers[step.key] === opt.val ? ' selected' : '') + '" data-val="' + escapeHtml(opt.val) + '">' +
          escapeHtml(opt.label) +
        '</button>'
      ).join('') +
      '</div>';
    $('quiz-step-current').textContent = String(quizState.idx + 1);
    $('quiz-step-total').textContent = String(QUIZ.steps.length);
    $('quiz-progress-bar').style.width = ((quizState.idx + 1) / QUIZ.steps.length * 100) + '%';
    $('quiz-back-btn').hidden = quizState.idx === 0;

    body.querySelectorAll('.quiz-option').forEach(btn => {
      btn.addEventListener('click', () => {
        quizState.answers[step.key] = btn.dataset.val;
        if (isLast) finishQuiz();
        else { quizState.idx++; renderQuizStep(); }
      });
    });
  }

  function finishQuiz() {
    const scores = QUIZ.score(quizState.answers);
    const ranked = Object.entries(scores)
      .sort((a, b) => b[1] - a[1])
      .map(([slug]) => slug)
      .filter(slug => state.published.some(b => b.slug === slug));
    const top = ranked.slice(0, 5);

    const body = $('quiz-body');
    const topBrokerages = top.map(slug => state.published.find(b => b.slug === slug)).filter(Boolean);
    body.innerHTML =
      '<h3 class="quiz-q">Your top matches</h3>' +
      '<p class="quiz-result-sub">Based on your answers, these brokerages best fit your profile. We\'ve preloaded them into /compare so you can see the total-cost math side-by-side.</p>' +
      '<div class="quiz-results-list">' +
      topBrokerages.map((b, i) =>
        '<div class="quiz-result-card' + (i === 0 ? ' top' : '') + '">' +
          (i === 0 ? '<div class="quiz-result-badge">Best Match</div>' : '') +
          logoHtml(b, 'selector') +
          '<div class="quiz-result-name">' + escapeHtml(b.name) + '</div>' +
          '<div class="quiz-result-cat">' + escapeHtml(b.category || '') + '</div>' +
        '</div>'
      ).join('') +
      '</div>' +
      '<button type="button" class="btn-gold quiz-apply-btn" id="quiz-apply-btn">Load These Into /compare &rarr;</button>';

    $('quiz-apply-btn').addEventListener('click', () => {
      state.selected = [];
      topBrokerages.slice(0, MAX_SELECT).forEach(b => state.selected.push(b));
      render();
      closeQuiz();
      document.getElementById('selector-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
      track('compare_quiz_complete', {
        production: quizState.answers.production,
        recruit: quizState.answers.recruit,
        brand: quizState.answers.brand,
        fees: quizState.answers.fees,
        office: quizState.answers.office,
        top_match: top[0],
        top_matches: top.join(',')
      });
    });

    $('quiz-back-btn').hidden = false;
    $('quiz-progress-bar').style.width = '100%';
    $('quiz-step-current').textContent = String(QUIZ.steps.length);
  }

  function openQuiz() {
    quizState.idx = 0;
    quizState.answers = {};
    $('quiz-modal').hidden = false;
    document.body.style.overflow = 'hidden';
    renderQuizStep();
    track('compare_quiz_open', {});
  }
  function closeQuiz() {
    $('quiz-modal').hidden = true;
    document.body.style.overflow = '';
  }

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
    const growth = parseInt(params.get('growth'), 10);
    return {
      slugs,
      gci: !isNaN(gci) ? gci : null,
      txns: !isNaN(txns) ? txns : null,
      plan: ['bp','bb','both'].includes(plan) ? plan : null,
      plus,
      cat: ['all','cloud','franchise','luxury','hybrid'].includes(cat) ? cat : null,
      growth: !isNaN(growth) ? growth : null
    };
  }

  function writeUrlState() {
    const params = new URLSearchParams();
    // Custom brokerages are session-only (too many fields to encode); only persist published slugs
    const persistable = state.selected.filter(b => !b.isCustom).map(b => b.slug);
    if (persistable.length) params.set('brokerages', persistable.join(','));
    if (state.gci !== 250000) params.set('gci', String(state.gci));
    if (state.txns !== 20) params.set('txns', String(state.txns));
    if (state.lptPlan !== 'both') params.set('plan', state.lptPlan);
    if (state.lptPlus) params.set('plus', '1');
    if (state.category !== 'all') params.set('cat', state.category);
    if (state.growth !== 10) params.set('growth', String(state.growth));
    const qs = params.toString();
    const url = '/compare' + (qs ? '?' + qs : '');
    window.history.replaceState(null, '', url);
  }

  /* ────────── GA4 + MC TRACKING ────────── */
  function track(eventName, payload) {
    if (typeof gtag === 'function') {
      try { gtag('event', eventName, payload || {}); } catch (_) {}
    }
  }

  const MC_TRACKING_URL = 'https://mission.tplcollective.ai/api/tracking/calculator';
  function postMcTracking(payload) {
    try {
      const body = JSON.stringify(payload || {});
      if (navigator.sendBeacon) {
        const blob = new Blob([body], { type: 'application/json' });
        navigator.sendBeacon(MC_TRACKING_URL, blob);
        return;
      }
      fetch(MC_TRACKING_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body, keepalive: true, mode: 'cors'
      }).catch(() => {});
    } catch (_) {}
  }

  /* ────────── LOGO HELPER ────────── */
  function monogram(brokerage) {
    const src = brokerage && (brokerage.short_name || brokerage.name) || '?';
    const parts = src.trim().split(/\s+/);
    const initials = (parts[0][0] || '?') + (parts.length > 1 ? parts[parts.length - 1][0] : '');
    return initials.toUpperCase().slice(0, 2);
  }
  function logoHtml(brokerage, variant) {
    // variant: 'chip' | 'selector' | 'matrix' | 'breakdown'
    if (brokerage && brokerage.isCustom) {
      return '<span class="chip-monogram brk-logo-' + variant + '">' + escapeHtml(monogram(brokerage)) + '</span>';
    }
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
    let citationsHtml = '';
    if (Array.isArray(b.citations) && b.citations.length) {
      citationsHtml = '<div class="breakdown-citations">' +
        b.citations.map(c => '<span class="citation-badge">' + escapeHtml(c) + '</span>').join('') +
        '</div>';
    }
    if (!parts.length && !citationsHtml) return '';
    const line = parts.length ? '<div>' + parts.join(' &middot; ') + '</div>' : '';
    return '<div class="breakdown-footnote">' + line + citationsHtml + '</div>';
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
        chip.className = 'chip' + (b.slug === LPT_SLUG ? ' lpt' : '') + (b.isCustom ? ' chip-custom' : '');
        chip.innerHTML = logoHtml(b, 'chip') + '<span>' + escapeHtml(b.short_name || b.name) + '</span>';
        if (b.isCustom) {
          const editBtn = document.createElement('button');
          editBtn.type = 'button';
          editBtn.className = 'chip-edit-btn';
          editBtn.setAttribute('aria-label', 'Edit ' + b.name);
          editBtn.title = 'Edit';
          editBtn.textContent = '✎';
          editBtn.addEventListener('click', (e) => { e.stopPropagation(); openCustomModal(b); });
          chip.appendChild(editBtn);
        }
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
      if (state.stateFilter !== 'all') {
        const mk = b.markets || [];
        const isNationwide = mk.includes('nationwide');
        if (!isNationwide && !mk.includes(state.stateFilter)) return false;
      }
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

  /* ────────── CUSTOM BROKERAGE ────────── */
  let customEditingSlug = null;

  function buildCustomBrokerage(formValues) {
    // Build a brokerage object that calcTotalCost understands
    const slug = formValues.editingSlug || ('custom-' + Date.now());
    const model = formValues.model;
    const splitPct = parseFloat(formValues.split);
    const cap = parseFloat(formValues.cap);
    const flatFee = parseFloat(formValues.flat);
    const flatCap = parseFloat(formValues.flatCap);
    const perTxn = parseFloat(formValues.perTxn);
    const monthly = parseFloat(formValues.monthly);
    const annual = parseFloat(formValues.annual);
    const royalty = parseFloat(formValues.royalty);
    const royaltyCap = parseFloat(formValues.royaltyCap);

    const plan = {
      plan_name: 'Your Numbers',
      split_structure: null,
      annual_cap: null,
      flat_fee_per_txn: null,
      per_txn_brokerage_fee: !isNaN(perTxn) ? perTxn : 0,
      per_txn_fee_applies_to: 'every_transaction',
      monthly_fee: !isNaN(monthly) ? monthly : 0,
      annual_fee: !isNaN(annual) ? annual : 0,
      eo_insurance_annual: 0,
      franchise_fee_pct: !isNaN(royalty) ? royalty : 0,
      franchise_fee_cap_annual: !isNaN(royaltyCap) ? royaltyCap : null,
      marketing_fee_pct: null,
      signup_fee: 0
    };

    if (model === 'split-cap') {
      plan.split_structure = (!isNaN(splitPct) ? splitPct : 70) + '/' + (!isNaN(splitPct) ? (100 - splitPct) : 30);
      plan.annual_cap = !isNaN(cap) ? cap : 0;
    } else if (model === 'no-cap') {
      plan.split_structure = (!isNaN(splitPct) ? splitPct : 70) + '/' + (!isNaN(splitPct) ? (100 - splitPct) : 30);
      plan.annual_cap = null;
    } else if (model === 'flat-fee') {
      plan.flat_fee_per_txn = !isNaN(flatFee) ? flatFee : 0;
      plan.annual_cap = !isNaN(flatCap) ? flatCap : 0;
    }

    return {
      slug,
      name: formValues.name,
      short_name: formValues.name.length > 18 ? formValues.name.slice(0, 16) + '…' : formValues.name,
      isCustom: true,
      status: 'custom',
      model_type: model === 'flat-fee' ? 'Flat-Fee' : 'Split',
      category: 'custom',
      _customForm: formValues,  // preserve raw form for re-edit
      plans: [plan]
    };
  }

  function openCustomModal(existing) {
    const modal = $('custom-modal');
    const err = $('custom-modal-error');
    err.hidden = true;
    customEditingSlug = existing ? existing.slug : null;
    const f = existing && existing._customForm ? existing._customForm : {};
    $('custom-modal-title').textContent = existing ? 'Edit ' + (existing.name || 'brokerage') : 'Enter your brokerage';
    $('custom-name').value = f.name || (existing ? existing.name : '') || '';
    const model = f.model || 'split-cap';
    document.querySelectorAll('input[name="custom-model"]').forEach(r => { r.checked = (r.value === model); });
    $('custom-split').value = f.split || '';
    $('custom-cap').value = f.cap || '';
    $('custom-flat').value = f.flat || '';
    $('custom-flat-cap').value = f.flatCap || '';
    $('custom-per-txn').value = f.perTxn || '';
    $('custom-monthly').value = f.monthly || '';
    $('custom-annual').value = f.annual || '';
    $('custom-royalty').value = f.royalty || '';
    $('custom-royalty-cap').value = f.royaltyCap || '';
    syncCustomFieldVisibility();
    modal.hidden = false;
    setTimeout(() => $('custom-name').focus(), 50);
    track('compare_custom_modal_open', { mode: existing ? 'edit' : 'create' });
  }

  function closeCustomModal() {
    $('custom-modal').hidden = true;
    customEditingSlug = null;
  }

  function syncCustomFieldVisibility() {
    const model = document.querySelector('input[name="custom-model"]:checked').value;
    document.querySelectorAll('.custom-field[data-show]').forEach(el => {
      const visible = el.getAttribute('data-show').split(' ').includes(model);
      el.style.display = visible ? '' : 'none';
    });
  }

  function submitCustomBrokerage(e) {
    e.preventDefault();
    const err = $('custom-modal-error');
    err.hidden = true;
    const name = $('custom-name').value.trim();
    if (!name) {
      err.textContent = 'Please enter a brokerage name.';
      err.hidden = false;
      return;
    }
    const model = document.querySelector('input[name="custom-model"]:checked').value;
    const formValues = {
      name, model,
      editingSlug: customEditingSlug,
      split: $('custom-split').value,
      cap: $('custom-cap').value,
      flat: $('custom-flat').value,
      flatCap: $('custom-flat-cap').value,
      perTxn: $('custom-per-txn').value,
      monthly: $('custom-monthly').value,
      annual: $('custom-annual').value,
      royalty: $('custom-royalty').value,
      royaltyCap: $('custom-royalty-cap').value
    };

    if (model === 'split-cap') {
      const sp = parseFloat(formValues.split);
      if (isNaN(sp) || sp < 50 || sp > 100) {
        err.textContent = 'Enter a split between 50 and 100 (e.g. 70 = 70/30).';
        err.hidden = false; return;
      }
      const cap = parseFloat(formValues.cap);
      if (isNaN(cap) || cap <= 0) {
        err.textContent = 'Enter an annual cap amount.';
        err.hidden = false; return;
      }
    } else if (model === 'flat-fee') {
      const ff = parseFloat(formValues.flat);
      if (isNaN(ff) || ff <= 0) {
        err.textContent = 'Enter a flat fee per transaction.';
        err.hidden = false; return;
      }
    }

    const brokerage = buildCustomBrokerage(formValues);
    if (customEditingSlug) {
      const idx = state.selected.findIndex(b => b.slug === customEditingSlug);
      if (idx >= 0) {
        state.selected[idx] = brokerage;
      } else {
        if (state.selected.length >= MAX_SELECT) {
          err.textContent = 'Remove a brokerage first — max ' + MAX_SELECT + ' selected.';
          err.hidden = false; return;
        }
        state.selected.push(brokerage);
      }
    } else {
      if (state.selected.length >= MAX_SELECT) {
        err.textContent = 'Remove a brokerage first — max ' + MAX_SELECT + ' selected.';
        err.hidden = false; return;
      }
      state.selected.push(brokerage);
    }

    track('compare_custom_brokerage_saved', {
      mode: customEditingSlug ? 'edit' : 'create',
      model: formValues.model,
      has_split: !!formValues.split,
      has_cap: !!formValues.cap,
      has_per_txn: !!formValues.perTxn,
      has_royalty: !!formValues.royalty
    });

    closeCustomModal();
    render();
    document.getElementById('matrix-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function initCustomModal() {
    const otherBtn = $('selector-other-btn');
    if (otherBtn) otherBtn.addEventListener('click', () => openCustomModal(null));
    $('custom-modal-close').addEventListener('click', closeCustomModal);
    $('custom-modal-cancel').addEventListener('click', closeCustomModal);
    $('custom-modal-backdrop').addEventListener('click', closeCustomModal);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !$('custom-modal').hidden) closeCustomModal();
    });
    document.querySelectorAll('input[name="custom-model"]').forEach(r => {
      r.addEventListener('change', syncCustomFieldVisibility);
    });
    $('custom-modal-form').addEventListener('submit', submitCustomBrokerage);
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
    table.style.setProperty('--col-count', cols.length);
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

      // Custom brokerages always render (their data is user-supplied).
      // Only treat as "pending" if it's neither published nor a custom entry.
      if (!plan || (b.status !== 'published' && !b.isCustom)) {
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

  /* ────────── CALC: CAP BREAK-EVEN ────────── */
  function calcCapBreakeven(plan, avgGciPerTxn) {
    if (!plan) return { type: 'none', label: 'N/A' };
    const cap = plan.annual_cap || 0;
    const splitPct = parseSplitPct(plan.split_structure);

    if (!cap && !plan.flat_fee_per_txn) return { type: 'none', label: 'No cap' };

    if (plan.flat_fee_per_txn && cap) {
      const txns = Math.ceil(cap / plan.flat_fee_per_txn);
      const gci = txns * (avgGciPerTxn || 0);
      return {
        type: 'txns', cap, valueTxns: txns, valueGci: gci,
        label: txns + ' txns',
        sub: avgGciPerTxn ? '~' + fmtMoneyShort(gci) + ' GCI' : null
      };
    }

    if (splitPct !== null && cap) {
      const brokerageShare = 1 - splitPct / 100;
      if (brokerageShare <= 0) return { type: 'none', label: 'No cap' };
      let gci = cap / brokerageShare;
      if (plan.franchise_fee_pct && plan.franchise_fee_pct > 0) {
        const effectiveShare = brokerageShare + (plan.franchise_fee_pct / 100);
        gci = cap / effectiveShare;
      }
      const txns = avgGciPerTxn ? Math.ceil(gci / avgGciPerTxn) : null;
      return {
        type: 'gci', cap, valueGci: gci, valueTxns: txns,
        label: fmtMoneyShort(gci) + ' GCI',
        sub: txns ? '~' + txns + ' txns' : null
      };
    }

    return { type: 'none', label: 'N/A' };
  }

  function progressToCap(plan, gci, txns) {
    if (!plan || !plan.annual_cap) return null;
    const splitPct = parseSplitPct(plan.split_structure);
    let paidToBrokerage = 0;
    if (plan.flat_fee_per_txn) {
      paidToBrokerage = Math.min(txns * plan.flat_fee_per_txn, plan.annual_cap);
    } else if (splitPct !== null) {
      const share = 1 - splitPct / 100;
      paidToBrokerage = Math.min(gci * share, plan.annual_cap);
      if (plan.franchise_fee_pct) {
        paidToBrokerage += Math.min(
          gci * (plan.franchise_fee_pct / 100),
          plan.franchise_fee_cap_annual || Infinity
        );
      }
    }
    const pct = plan.annual_cap > 0 ? (paidToBrokerage / plan.annual_cap) * 100 : 0;
    return Math.min(100, Math.max(0, pct));
  }

  /* ────────── RENDER: CAP BREAK-EVEN ────────── */
  function renderCapBreakeven() {
    const panel = $('breakeven-panel');
    const grid = $('breakeven-grid');
    const cols = getColumnsForMatrix();
    if (!cols.length) { panel.hidden = true; return; }
    panel.hidden = false;
    grid.innerHTML = '';

    cols.forEach(col => {
      const b = col.brokerage;
      const plan = col.plan;
      const be = calcCapBreakeven(plan, state.avgGci);
      const pct = progressToCap(plan, state.gci, state.txns);
      const isLpt = b.slug === LPT_SLUG;
      const planLabel = isLpt ? (plan.plan_name || '').replace(/\s*\(.+\)/, '') : '';

      let barClass = 'breakeven-bar-fill';
      if (pct != null) {
        if (pct >= 100) barClass += ' capped';
        else if (pct >= 80) barClass += ' near';
      }

      const card = document.createElement('div');
      card.className = 'breakeven-card' + (isLpt ? ' lpt' : '');
      card.innerHTML =
        '<div class="breakeven-card-head">' +
          logoHtml(b, 'breakdown') +
          '<div class="breakeven-card-name">' +
            escapeHtml(b.short_name || b.name) +
            (planLabel ? '<span class="breakeven-plan-sub">' + escapeHtml(planLabel) + '</span>' : '') +
          '</div>' +
        '</div>' +
        '<div class="breakeven-stat">' +
          '<div class="breakeven-stat-label">Cap</div>' +
          '<div class="breakeven-stat-val">' + (plan && plan.annual_cap ? fmtMoney(plan.annual_cap) : '—') + '</div>' +
        '</div>' +
        '<div class="breakeven-stat">' +
          '<div class="breakeven-stat-label">Break-Even</div>' +
          '<div class="breakeven-stat-val">' + escapeHtml(be.label) +
            (be.sub ? '<span class="breakeven-stat-sub">' + escapeHtml(be.sub) + '</span>' : '') +
          '</div>' +
        '</div>' +
        (pct != null ?
          '<div class="breakeven-progress">' +
            '<div class="breakeven-progress-head">' +
              '<span>Your progress</span>' +
              '<span class="breakeven-progress-pct">' + pct.toFixed(0) + '%</span>' +
            '</div>' +
            '<div class="breakeven-bar">' +
              '<div class="' + barClass + '" style="width:' + pct + '%"></div>' +
            '</div>' +
          '</div>' : ''
        );
      grid.appendChild(card);
    });
  }

  /* ────────── CALC: 3-YEAR PROJECTION ────────── */
  function calcProjection(brokerage, plan, baseGci, baseTxns, avgGciPerTxn, growthPct, includeLptPlus) {
    const rows = [];
    let cumulative = 0;
    for (let y = 1; y <= 3; y++) {
      const mult = Math.pow(1 + growthPct / 100, y - 1);
      const gciY = baseGci * mult;
      const txnsY = Math.max(1, Math.round(baseTxns * mult));
      const avgY = avgGciPerTxn;
      const res = calcTotalCost(brokerage, plan, gciY, txnsY, avgY, includeLptPlus);
      const net = res ? res.net : gciY;
      cumulative += net;
      rows.push({ year: y, gci: gciY, txns: txnsY, net, cumulative });
    }
    return { rows, total: cumulative };
  }

  /* ────────── RENDER: 3-YEAR PROJECTION ────────── */
  function renderProjection() {
    const panel = $('projection-panel');
    const table = $('projection-table');
    const cols = getColumnsForMatrix();
    if (!cols.length) { panel.hidden = true; return; }
    panel.hidden = false;

    const growth = state.growth != null ? state.growth : 10;
    const projections = cols.map(col => ({
      col,
      proj: calcProjection(col.brokerage, col.plan, state.gci, state.txns, state.avgGci, growth, state.lptPlus)
    }));

    const lptProj = projections.find(p => p.col.brokerage.slug === LPT_SLUG &&
      (p.col.plan.plan_name || '').toLowerCase().includes('brokerage partner'));
    const lptTotal = lptProj ? lptProj.proj.total : null;

    const headCells = projections.map(p => {
      const b = p.col.brokerage;
      const isLpt = b.slug === LPT_SLUG;
      const planLabel = isLpt ? (p.col.plan.plan_name || '').replace(/\s*\(.+\)/, '') : '';
      return '<th' + (isLpt ? ' class="lpt-col"' : '') + '>' +
        '<div class="projection-col-name">' + escapeHtml(b.short_name || b.name) + '</div>' +
        (planLabel ? '<div class="projection-col-plan">' + escapeHtml(planLabel) + '</div>' : '') +
        '</th>';
    }).join('');

    const yearRows = [1, 2, 3].map(y => {
      const cells = projections.map(p => {
        const row = p.proj.rows[y - 1];
        const isLpt = p.col.brokerage.slug === LPT_SLUG;
        return '<td' + (isLpt ? ' class="lpt-col"' : '') + '>' +
          '<div class="projection-net">' + fmtMoney(row.net) + '</div>' +
          '<div class="projection-sub">' + fmtMoneyShort(row.gci) + ' GCI / ' + row.txns + ' txns</div>' +
          '</td>';
      }).join('');
      return '<tr><td class="projection-row-label">Year ' + y + '</td>' + cells + '</tr>';
    }).join('');

    const totalCells = projections.map(p => {
      const isLpt = p.col.brokerage.slug === LPT_SLUG;
      const delta = lptTotal != null ? (p.proj.total - lptTotal) : null;
      let deltaHtml = '';
      if (delta != null && !isLpt) {
        const sign = delta >= 0 ? '+' : '−';
        const deltaClass = delta >= 0 ? 'projection-delta-pos' : 'projection-delta-neg';
        deltaHtml = '<div class="projection-delta ' + deltaClass + '">' +
          sign + fmtMoney(Math.abs(delta)) + ' vs LPT BP</div>';
      }
      return '<td' + (isLpt ? ' class="lpt-col"' : '') + '>' +
        '<div class="projection-total">' + fmtMoney(p.proj.total) + '</div>' +
        deltaHtml +
        '</td>';
    }).join('');

    table.innerHTML =
      '<thead><tr>' +
        '<th class="projection-row-header">&nbsp;</th>' + headCells +
      '</tr></thead>' +
      '<tbody>' +
        yearRows +
        '<tr class="projection-total-row"><td class="projection-row-label">3-Year Total Retained</td>' + totalCells + '</tr>' +
      '</tbody>';
  }

  /* ────────── CALC + RENDER: LPT EQUITY (Performance Awards) ────────── */
  function lptBadgeForTxns(awards, txns) {
    // Returns the highest-tier badge whose threshold is met by `txns`.
    if (!awards || !awards.length) return null;
    const sorted = awards.slice().sort((a, b) => b.annual_core_transactions - a.annual_core_transactions);
    return sorted.find(a => txns >= a.annual_core_transactions) || null;
  }

  function nextBadgeForTxns(awards, txns) {
    if (!awards || !awards.length) return null;
    const sorted = awards.slice().sort((a, b) => a.annual_core_transactions - b.annual_core_transactions);
    return sorted.find(a => txns < a.annual_core_transactions) || null;
  }

  function renderLptEquity() {
    const panel = $('lpt-equity-panel');
    const lpt = state.selected.find(b => b.slug === LPT_SLUG);
    if (!lpt || !lpt.equity || !lpt.equity.achievement_awards) {
      panel.hidden = true; return;
    }
    panel.hidden = false;

    const eq = lpt.equity;
    const awards = eq.achievement_awards;
    const earned = lptBadgeForTxns(awards, state.txns);
    const next = nextBadgeForTxns(awards, state.txns);
    const isBB = state.lptPlan === 'bb';
    const isBoth = state.lptPlan === 'both';

    // ── This Year cards (BP + BB) ──
    const yearWrap = $('lpt-equity-this-year');
    if (earned) {
      const bpVal = earned.shares_bp != null ? earned.shares_bp.toLocaleString() + ' shares' : '—';
      const bbVal = earned.shares_bb != null
        ? earned.shares_bb.toLocaleString() + ' shares'
        : (earned.shares_bb_note || '—');
      yearWrap.innerHTML =
        '<div class="lpt-equity-stat">' +
          '<div class="lpt-equity-stat-label">' + escapeHtml(earned.badge) + ' badge &middot; Brokerage Partner</div>' +
          '<div class="lpt-equity-stat-val">' + bpVal + '</div>' +
          '<div class="lpt-equity-stat-sub">' + state.txns + ' txns &ge; ' + earned.annual_core_transactions + ' threshold &middot; 3-yr vest</div>' +
        '</div>' +
        '<div class="lpt-equity-stat">' +
          '<div class="lpt-equity-stat-label">' + escapeHtml(earned.badge) + ' badge &middot; Business Builder</div>' +
          '<div class="lpt-equity-stat-val">' + bbVal + '</div>' +
          '<div class="lpt-equity-stat-sub">' + (earned.shares_bb_note || '3-yr vest. Upgrade to BP to earn higher tiers.') + '</div>' +
        '</div>';
    } else {
      const ahead = next ? (next.annual_core_transactions - state.txns) : null;
      yearWrap.innerHTML =
        '<div class="lpt-equity-stat" style="grid-column:span 2">' +
          '<div class="lpt-equity-stat-label">No badge earned this year</div>' +
          '<div class="lpt-equity-stat-val" style="font-size:22px;color:var(--muted)">' +
            (next ? ahead + ' more txns to reach ' + escapeHtml(next.badge) : 'Outside award range') + '</div>' +
          '<div class="lpt-equity-stat-sub">First badge unlocks at 1 core transaction.</div>' +
        '</div>';
    }

    // ── Badge ladder (all 4 thresholds) ──
    const ladderWrap = $('lpt-equity-ladder');
    const sortedAsc = awards.slice().sort((a, b) => a.annual_core_transactions - b.annual_core_transactions);
    ladderWrap.innerHTML = sortedAsc.map(a => {
      const isEarned = earned && a.badge === earned.badge;
      const isNextOne = next && a.badge === next.badge;
      const cls = 'lpt-equity-rung' + (isEarned ? ' earned' : '') + (isNextOne ? ' next' : '');
      const bp = a.shares_bp != null ? a.shares_bp.toLocaleString() : '—';
      const bb = a.shares_bb != null ? a.shares_bb.toLocaleString() : (a.shares_bb_note ? 'N/A' : '—');
      return '<div class="' + cls + '">' +
        '<div class="lpt-equity-rung-badge">' + escapeHtml(a.badge) + '</div>' +
        '<div class="lpt-equity-rung-thresh">' + a.annual_core_transactions + '+ txns/yr</div>' +
        '<div class="lpt-equity-rung-shares">BP: <b>' + bp + '</b><br>BB: <b>' + bb + '</b></div>' +
      '</div>';
    }).join('');

    // ── Sponsorship extras ──
    const extras = $('lpt-equity-extras');
    const sp = eq.sponsorship_award_per_direct_sponsored;
    if (sp) {
      extras.innerHTML =
        '<strong>+ Sponsorship Performance Awards:</strong> ' +
        sp.shares_bp.toLocaleString() + ' shares (BP) / ' + sp.shares_bb.toLocaleString() + ' shares (BB) ' +
        'for each directly-sponsored agent\'s first Core Transaction (one-time per recruit). ' +
        'Stacks on top of your annual badge award.';
    }

    // ── 3-Year cumulative projection ──
    // Use the same growth slider and starting txns as the projection panel.
    let cum_bp = 0, cum_bb = 0;
    const yearRows = [];
    for (let y = 1; y <= 3; y++) {
      const mult = Math.pow(1 + (state.growth || 0) / 100, y - 1);
      const txY = Math.max(1, Math.round(state.txns * mult));
      const ear = lptBadgeForTxns(awards, txY);
      const bpY = ear && ear.shares_bp ? ear.shares_bp : 0;
      const bbY = ear && ear.shares_bb ? ear.shares_bb : 0;
      cum_bp += bpY; cum_bb += bbY;
      yearRows.push({ year: y, txns: txY, badge: ear ? ear.badge : '—', bp: bpY, bb: bbY });
    }
    const projWrap = $('lpt-equity-projection');
    projWrap.innerHTML =
      '<div class="lpt-equity-projection-title">3-Year Equity Projection (annual badge awards only)</div>' +
      '<div class="lpt-equity-projection-grid">' +
        yearRows.map(r =>
          '<div class="lpt-equity-projection-cell">' +
            '<span class="yr">Year ' + r.year + ' &middot; ' + r.txns + ' txns &middot; ' + escapeHtml(r.badge) + '</span><br>' +
            '<span class="val">' + (r.bp ? r.bp.toLocaleString() : '0') + '</span> BP<br>' +
            '<span class="val">' + (r.bb ? r.bb.toLocaleString() : '0') + '</span> BB' +
          '</div>'
        ).join('') +
      '</div>' +
      '<div class="lpt-equity-projection-total">' +
        '<span class="total-label">3-Year Total Shares</span>' +
        '<span class="total-val">' + cum_bp.toLocaleString() + ' BP &middot; ' + cum_bb.toLocaleString() + ' BB</span>' +
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
    renderCapBreakeven();
    renderProjection();
    renderLptEquity();
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
    initCustomModal();
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

    // Price + commission % + deals are now the PRIMARY inputs.
    // GCI and avg-gci are derived: avg = price × rate/100, gci = avg × deals.
    function recomputeFromPriceRateDeals() {
      const priceEl = $('calc-price');
      const rateEl = $('calc-rate');
      const price = Math.max(0, parseFloat(priceEl ? priceEl.value : 0) || 0);
      const rate = Math.max(0, parseFloat(rateEl ? rateEl.value : 0) || 0);
      const perDealGci = Math.round(price * (rate / 100));
      const totalGci = perDealGci * state.txns;
      state.avgGci = perDealGci;
      state.avgGciEdited = false;
      state.gci = totalGci;
      // Keep hidden mirrors in sync (used by some legacy paths)
      try {
        $('gci-slider').value = totalGci;
        $('gci-value').textContent = fmtMoney(totalGci);
        $('avg-gci').value = perDealGci;
      } catch (_) {}
      // Update the derived line
      const dgci = $('calc-derived-gci'); if (dgci) dgci.textContent = fmtMoney(totalGci);
      const davg = $('calc-derived-avg'); if (davg) davg.textContent = fmtMoney(perDealGci);
      renderMatrix(); renderBreakdown(); renderCapBreakeven(); renderProjection(); renderLptEquity(); writeUrlState();
    }

    const priceEl = $('calc-price');
    const rateEl = $('calc-rate');
    if (priceEl) priceEl.addEventListener('input', recomputeFromPriceRateDeals);
    if (rateEl) rateEl.addEventListener('input', recomputeFromPriceRateDeals);

    $('txns-slider').addEventListener('input', (e) => {
      state.txns = parseInt(e.target.value, 10);
      $('txns-value').textContent = String(state.txns);
      // Recompute total GCI from current price/rate
      recomputeFromPriceRateDeals();
    });

    $('lpt-plus-toggle').addEventListener('change', (e) => {
      state.lptPlus = e.target.checked;
      renderMatrix(); renderBreakdown(); renderProjection(); renderLptEquity(); writeUrlState();
    });

    $('growth-slider').addEventListener('input', (e) => {
      state.growth = parseInt(e.target.value, 10);
      $('growth-value').textContent = String(state.growth);
      renderProjection(); renderLptEquity(); writeUrlState();
    });

    const stateSel = $('state-filter');
    if (stateSel) {
      stateSel.addEventListener('change', (e) => {
        state.stateFilter = e.target.value;
        renderSelectorList();
        writeUrlState();
        track('compare_state_filter', { state: state.stateFilter });
      });
    }

    /* ── QUIZ ── */
    $('open-quiz-btn').addEventListener('click', openQuiz);
    $('quiz-modal-close').addEventListener('click', closeQuiz);
    $('quiz-modal-backdrop').addEventListener('click', closeQuiz);
    $('quiz-back-btn').addEventListener('click', () => {
      if (quizState.idx > 0) { quizState.idx--; renderQuizStep(); }
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !$('quiz-modal').hidden) closeQuiz();
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
        renderMatrix(); renderBreakdown(); renderCapBreakeven(); renderProjection(); renderLptEquity(); writeUrlState();
      });
    });

    /* ── EMAIL MODAL ── */
    const emailModal = $('email-modal');
    const emailForm = $('email-modal-form');
    const emailErr = $('email-modal-error');
    const emailSuccess = $('email-modal-success');

    function openEmailModal() {
      emailModal.hidden = false;
      document.body.style.overflow = 'hidden';
      setTimeout(() => { $('email-modal-name').focus(); }, 50);
      track('compare_email_modal_open', { selection: state.selected.map(b => b.slug).join(',') });
    }
    function closeEmailModal() {
      emailModal.hidden = true;
      document.body.style.overflow = '';
      emailErr.hidden = true;
      emailErr.textContent = '';
      emailForm.hidden = false;
      emailSuccess.hidden = true;
      emailForm.reset();
    }

    $('email-comparison-btn').addEventListener('click', openEmailModal);
    $('email-modal-close').addEventListener('click', closeEmailModal);
    $('email-modal-backdrop').addEventListener('click', closeEmailModal);
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !emailModal.hidden) closeEmailModal();
    });

    emailForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = $('email-modal-name').value.trim();
      const email = $('email-modal-email').value.trim();
      const phone = $('email-modal-phone').value.trim();
      emailErr.hidden = true;
      if (!name || !email) {
        emailErr.hidden = false;
        emailErr.textContent = 'Name and email are required.';
        return;
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        emailErr.hidden = false;
        emailErr.textContent = 'Please enter a valid email.';
        return;
      }
      const submitBtn = $('email-modal-submit');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Sending...';

      writeUrlState();
      const shareUrl = window.location.origin + window.location.pathname + window.location.search;
      const nameParts = name.split(/\s+/);
      const firstName = nameParts[0] || '';
      const lastName = nameParts.slice(1).join(' ') || '';
      const selectionSlugs = state.selected.map(b => b.slug);
      const customs = state.selected.filter(b => b.isCustom);
      const leadTags = ['compare-tool', 'comparison-requested'].concat(
        state.selected.filter(b => !b.isCustom).map(b => 'compared-' + b.slug)
      );
      if (customs.length) leadTags.push('compared-custom-brokerage');

      // Build custom-brokerage detail block for CRM notes
      let customDetails = '';
      if (customs.length) {
        customDetails = '\n\nCUSTOM BROKERAGE(S):\n' + customs.map(b => {
          const f = b._customForm || {};
          const lines = ['• ' + b.name + ' [' + f.model + ']'];
          if (f.split) lines.push('   Split: ' + f.split + '/' + (100 - parseFloat(f.split)));
          if (f.cap) lines.push('   Cap: $' + f.cap);
          if (f.flat) lines.push('   Flat fee/txn: $' + f.flat);
          if (f.flatCap) lines.push('   Flat-fee cap: $' + f.flatCap);
          if (f.perTxn) lines.push('   Per-txn fee: $' + f.perTxn);
          if (f.monthly) lines.push('   Monthly: $' + f.monthly);
          if (f.annual) lines.push('   Annual: $' + f.annual);
          if (f.royalty) lines.push('   Royalty: ' + f.royalty + '%' + (f.royaltyCap ? ' (cap $' + f.royaltyCap + ')' : ''));
          return lines.join('\n');
        }).join('\n');
      }

      const leadPayload = {
        first_name: firstName,
        last_name: lastName,
        email: email,
        phone: phone,
        source: 'compare_email_share',
        stage: 'research',
        tags: leadTags,
        notes: 'Brokerage comparison: ' + selectionSlugs.join(', ') +
               ' | GCI $' + state.gci + ' | Txns ' + state.txns +
               ' | LPT plan ' + state.lptPlan + (state.lptPlus ? ' + Plus' : '') +
               ' | Share URL: ' + shareUrl + customDetails
      };
      try {
        await fetch('/api/leads', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(leadPayload)
        });
      } catch (err) { /* non-blocking */ }

      const payload = {
        name, email, phone,
        source: 'compare_email_share',
        share_url: shareUrl,
        gci: state.gci,
        txns: state.txns,
        avg_gci_per_txn: state.avgGci,
        selection: selectionSlugs,
        lpt_plan: state.lptPlan,
        lpt_plus: state.lptPlus,
        ts: new Date().toISOString()
      };
      try {
        const res = await fetch(MC_TRACKING_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok && res.status !== 404) throw new Error('HTTP ' + res.status);
      } catch (err) {
        postMcTracking(payload);
      }
      track('compare_email_share_submit', {
        selection: state.selected.map(b => b.slug).join(','),
        gci: state.gci, txns: state.txns
      });
      if (typeof fbq === 'function') {
        try { fbq('track', 'Lead', { content_name: 'Compare Email Share' }); } catch (_) {}
      }
      emailForm.hidden = true;
      emailSuccess.hidden = false;
      submitBtn.disabled = false;
      submitBtn.textContent = 'Send My Comparison';
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
    if (u.growth != null) state.growth = Math.max(0, Math.min(25, u.growth));

    const hasUrlSelection = u.slugs.length > 0;
    const initialSlugs = hasUrlSelection ? u.slugs : [LPT_SLUG];
    initialSlugs.forEach(slug => {
      const b = state.published.find(x => x.slug === slug);
      if (b && state.selected.length < MAX_SELECT) state.selected.push(b);
    });

    state.avgGci = state.txns > 0 ? Math.round(state.gci / state.txns) : 12500;

    // Hydrate price + rate inputs so derived values match GCI from URL state.
    // Default rate is 2.5%; back-derive price from avgGci so things stay consistent.
    try {
      const priceEl = $('calc-price');
      const rateEl = $('calc-rate');
      if (priceEl && rateEl) {
        const rate = parseFloat(rateEl.value) || 2.5;
        const derivedPrice = state.avgGci > 0 && rate > 0
          ? Math.round(state.avgGci / (rate / 100))
          : 450000;
        priceEl.value = derivedPrice;
      }
    } catch (_) {}

    $('gci-slider').value = state.gci;
    $('gci-value').textContent = fmtMoney(state.gci);
    $('txns-slider').value = state.txns;
    $('txns-value').textContent = String(state.txns);
    $('avg-gci').value = state.avgGci;
    $('lpt-plus-toggle').checked = state.lptPlus;
    $('growth-slider').value = state.growth;
    $('growth-value').textContent = String(state.growth);

    // Refresh derived display
    const dgci = $('calc-derived-gci'); if (dgci) dgci.textContent = fmtMoney(state.gci);
    const davg = $('calc-derived-avg'); if (davg) davg.textContent = fmtMoney(state.avgGci);

    document.querySelectorAll('.filter-btn').forEach(b => {
      b.classList.toggle('active', b.dataset.category === state.category);
    });
    document.querySelectorAll('.plan-toggle-btn').forEach(b => {
      const match = b.dataset.plan === state.lptPlan;
      b.classList.toggle('active', match);
      b.setAttribute('aria-checked', match ? 'true' : 'false');
    });
  }

  /* ────────── REPORT MODE (?report=<token>) ────────── */
  // When a recruit lands on /compare?report=<token>, fetch the saved comparison from
  // Mission Control and lock the page into read-only "report" mode.

  function isReportMode() {
    return /[?&]report=[\w-]+/.test(window.location.search);
  }

  async function loadReportFromToken() {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('report');
    if (!token) return false;
    try {
      const res = await fetch('https://mission.tplcollective.ai/api/recruit-comparisons/by-token/' + encodeURIComponent(token));
      if (!res.ok) {
        console.error('Report load failed:', res.status);
        return false;
      }
      const data = await res.json();
      // Hydrate state from saved data
      state.gci = data.gci || 250000;
      state.txns = data.txns || 20;
      state.avgGci = data.avg_gci_per_txn || Math.round(state.gci / state.txns);
      state.lptPlan = data.lpt_plan || 'both';
      state.lptPlus = !!data.lpt_plus;
      state.selected = (data.selection || []).map(b => {
        // Custom brokerages were saved with isCustom flag - preserve it
        if (b && b.isCustom) return b;
        // Published brokerages: re-resolve from current published list to get fresh logos/citations
        const fresh = state.published.find(p => p.slug === b.slug);
        return fresh || b;
      });
      // Apply to UI inputs (sliders/numbers)
      try {
        $('gci-slider').value = state.gci;
        $('gci-value').textContent = fmtMoney(state.gci);
        $('txns-slider').value = state.txns;
        $('txns-value').textContent = String(state.txns);
        $('avg-gci').value = state.avgGci;
        $('lpt-plus-toggle').checked = state.lptPlus;
      } catch (_) {}

      // Inject report header banner above the matrix
      try {
        const sender = (data.created_by_name || 'Your TPL Collective contact');
        const recruitFirst = (data.recruit_first_name || 'there').trim().split(/\s+/)[0];
        const senderEmail = data.created_by_email || '';
        const banner = document.createElement('section');
        banner.className = 'cmp-panel report-banner';
        banner.innerHTML =
          '<div class="cmp-panel-head">' +
            '<div class="cmp-panel-label">Personal report</div>' +
            '<h2 class="cmp-panel-title">Comparison prepared for ' + escapeHtml(recruitFirst) + ' by ' + escapeHtml(sender) + '</h2>' +
          '</div>' +
          '<p class="report-banner-sub">' +
            'These numbers are from public sources and the LPT comp plan flyer. ' +
            'Have questions? ' +
            (senderEmail ? '<a href="mailto:' + escapeHtml(senderEmail) + '">Email ' + escapeHtml(sender) + '</a>' : 'Reply to the email you received.') +
          '</p>';
        const matrix = document.getElementById('matrix-panel');
        if (matrix && matrix.parentNode) {
          matrix.parentNode.insertBefore(banner, matrix);
        }
      } catch (_) {}

      // Hide selector + inputs + quiz/share — keep matrix, breakdown, cap break-even, projection
      try {
        document.querySelectorAll('.selector-panel, .inputs-panel, .quiz-launcher, .cmp-share-row, #email-comparison-btn').forEach(el => {
          if (el) el.style.display = 'none';
        });
      } catch (_) {}

      track('recruit_comparison_viewed', { token, view_count: data.view_count || 1 });
      return true;
    } catch (err) {
      console.error('Failed to load comparison report', err);
      return false;
    }
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
    if (isReportMode()) {
      const ok = await loadReportFromToken();
      if (ok) {
        render();
        return;
      }
      // Fall through to normal mode if report load fails
    }
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

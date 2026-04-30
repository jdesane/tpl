// Shared brokerage cost-comparison calculator. Mirrors the math in
// assets/compare/compare.js so server-side flows (PDF generation, recruit
// comparison emails) produce identical numbers to the live /compare page.

const LPT_SLUG = 'lpt-realty';

export function parseSplitPct(structure) {
  if (!structure || typeof structure !== 'string') return null;
  const m = structure.match(/^(\d+)\/(\d+)$/);
  return m ? parseInt(m[1], 10) : null;
}

export function calcTotalCost(brokerage, plan, gci, txns, avgGciPerTxn, includeLptPlus) {
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

  if (plan.per_txn_brokerage_fee) {
    txnBrokerageFees = txns * plan.per_txn_brokerage_fee;
  }

  if (plan.post_cap_per_txn_fee && plan.per_txn_fee_applies_to === 'post_cap_only_first_20') {
    const sp = splitPct !== null ? splitPct : 80;
    const brokerageShare = 1 - sp / 100;
    const capTxns = Math.ceil((plan.annual_cap || 0) / (brokerageShare * avgGciPerTxn));
    const postCapTxns = Math.max(0, Math.min(txns - capTxns, 20));
    txnBrokerageFees += postCapTxns * plan.post_cap_per_txn_fee;
  }

  let optional = 0;
  if (includeLptPlus && brokerage && brokerage.slug === LPT_SLUG) {
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

export function calcCapBreakeven(plan, avgGciPerTxn) {
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
      sub: avgGciPerTxn ? '~$' + Math.round(gci).toLocaleString() + ' GCI' : null
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
    const fmtShort = (n) => {
      if (n == null || isNaN(n)) return '-';
      if (n >= 1000000) return '$' + (n / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
      if (n >= 1000) return '$' + Math.round(n / 1000) + 'K';
      return '$' + Math.round(n);
    };
    return {
      type: 'gci', cap, valueGci: gci, valueTxns: txns,
      label: fmtShort(gci) + ' GCI',
      sub: txns ? '~' + txns + ' txns' : null
    };
  }

  return { type: 'none', label: 'N/A' };
}

export function progressToCap(plan, gci, txns) {
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

export function calcProjection(brokerage, plan, baseGci, baseTxns, avgGciPerTxn, growthPct, includeLptPlus) {
  const rows = [];
  let cumulative = 0;
  for (let y = 1; y <= 3; y++) {
    const mult = Math.pow(1 + growthPct / 100, y - 1);
    const gciY = baseGci * mult;
    const txnsY = Math.max(1, Math.round(baseTxns * mult));
    const res = calcTotalCost(brokerage, plan, gciY, txnsY, avgGciPerTxn, includeLptPlus);
    const net = res ? res.net : gciY;
    cumulative += net;
    rows.push({ year: y, gci: gciY, txns: txnsY, net, cumulative });
  }
  return { rows, total: cumulative };
}

export function earnedBadgesForTxns(awards, txns) {
  if (!awards || !awards.length) return [];
  const asc = awards.slice().sort((a, b) => a.annual_core_transactions - b.annual_core_transactions);
  return asc.filter(a => txns >= a.annual_core_transactions);
}

export function sumEarnedShares(awards, txns) {
  const earned = earnedBadgesForTxns(awards, txns);
  let bp = 0, bb = 0;
  earned.forEach(a => {
    if (typeof a.shares_bp === 'number') bp += a.shares_bp;
    if (typeof a.shares_bb === 'number') bb += a.shares_bb;
  });
  return { bp, bb, count: earned.length, list: earned };
}

// Fetch + cache the published brokerages.json so server-side endpoints can
// resolve slugs to full brokerage objects.
let _brokeragesCache = null;
export async function loadBrokerages() {
  if (_brokeragesCache) return _brokeragesCache;
  // In Vercel, fetch our own /data/brokerages.json from the deployment URL or
  // canonical site. Falls back to file load when running locally for tests.
  const url = (process.env.VERCEL_URL ? 'https://' + process.env.VERCEL_URL : 'https://tplcollective.ai') + '/data/brokerages.json';
  try {
    const res = await fetch(url, { cache: 'no-store' });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const json = await res.json();
    _brokeragesCache = json.brokerages || [];
    return _brokeragesCache;
  } catch (err) {
    console.error('loadBrokerages failed from', url, err);
    return [];
  }
}

export function findPublishedBySlug(brokerages, slug) {
  if (!Array.isArray(brokerages)) return null;
  return brokerages.find(b => b.slug === slug) || null;
}

// Build the columns the matrix iterates over given a selection (mix of slugs
// and custom brokerage objects) and the LPT plan filter ('bp' | 'bb' | 'both').
export function getColumnsForSelection(selection, published, lptPlan) {
  const cols = [];
  (selection || []).forEach((sel) => {
    if (sel && typeof sel === 'object' && sel.isCustom) {
      const firstPlan = (sel.plans && sel.plans[0]) || null;
      cols.push({ brokerage: sel, plan: firstPlan });
      return;
    }
    const slug = (typeof sel === 'string') ? sel : (sel && sel.slug);
    if (!slug) return;
    const b = findPublishedBySlug(published, slug);
    if (!b) return;
    if (slug === LPT_SLUG) {
      const plans = b.plans || [];
      const wanted = lptPlan === 'bp'
        ? plans.filter(p => /brokerage partner/i.test(p.plan_name || ''))
        : lptPlan === 'bb'
          ? plans.filter(p => /business builder/i.test(p.plan_name || ''))
          : plans;
      wanted.forEach(plan => cols.push({ brokerage: b, plan }));
    } else {
      cols.push({ brokerage: b, plan: (b.plans && b.plans[0]) || null });
    }
  });
  return cols;
}

const fmtMoney = (n) => {
  if (n == null || isNaN(n)) return '-';
  return '$' + Math.round(n).toLocaleString('en-US');
};

// Build the full PDF payload from raw inputs (selection, gci, txns, etc.)
// Reuses the matrix helpers above so the numbers match /compare exactly.
export async function buildReportData({
  selection,
  gci,
  txns,
  avgGciPerTxn,
  lptPlan = 'both',
  lptPlus = false,
  growthPct = 0
}) {
  const published = await loadBrokerages();
  const cols = getColumnsForSelection(selection || [], published, lptPlan);

  const comparisonResults = [];
  const detailColumns = [];
  const breakdownBlocks = [];
  const capBreakeven = [];
  const projection = [];

  cols.forEach(col => {
    const b = col.brokerage;
    const plan = col.plan;
    const r = calcTotalCost(b, plan, gci, txns, avgGciPerTxn, lptPlus);
    if (!r) return;

    comparisonResults.push({
      slug: b.slug, name: b.name, short_name: b.short_name,
      isCustom: !!b.isCustom,
      plan_name: plan && plan.plan_name,
      total: r.total, net: r.net, retainedPct: r.retainedPct
    });

    detailColumns.push({
      slug: b.slug, name: b.name, short_name: b.short_name,
      isCustom: !!b.isCustom,
      model_type: b.model_type || null,
      founded: b.founded || null,
      public_ticker: b.public_ticker || null,
      plan_name: plan ? plan.plan_name : null,
      split_structure: plan ? plan.split_structure : null,
      annual_cap: plan ? plan.annual_cap : null,
      monthly_fee: plan ? plan.monthly_fee : null,
      annual_fee: plan ? plan.annual_fee : null,
      annual_fee_note: plan ? plan.annual_fee_note : null,
      eo_insurance_annual: plan ? plan.eo_insurance_annual : null,
      eo_note: plan ? plan.eo_note : null,
      franchise_fee_pct: plan ? plan.franchise_fee_pct : null,
      franchise_fee_cap_annual: plan ? plan.franchise_fee_cap_annual : null,
      per_txn_brokerage_fee: plan ? plan.per_txn_brokerage_fee : null,
      flat_fee_per_txn: plan ? plan.flat_fee_per_txn : null,
      total: r.total, net: r.net, retainedPct: r.retainedPct
    });

    const bd = r.breakdown || {};
    const isLpt = b.slug === LPT_SLUG;
    breakdownBlocks.push({
      slug: b.slug, name: b.name, short_name: b.short_name,
      isCustom: !!b.isCustom,
      isLpt,
      plan_name: plan ? plan.plan_name : null,
      rows: [
        (bd.splitCost > 0
          ? { label: plan && plan.flat_fee_per_txn ? 'Flat fees to cap' : 'Split to cap',
              sub: plan && plan.flat_fee_per_txn
                ? Math.min(txns, Math.floor((plan.annual_cap || 0) / plan.flat_fee_per_txn)) + ' x ' + fmtMoney(plan.flat_fee_per_txn)
                : (plan ? plan.split_structure + ' until ' + fmtMoney(plan.annual_cap || 0) + ' cap' : ''),
              value: bd.splitCost }
          : null),
        (bd.txnBrokerageFees > 0
          ? { label: 'Per-txn brokerage fee',
              sub: txns + ' x ' + fmtMoney((plan && plan.per_txn_brokerage_fee) || (plan && plan.post_cap_per_txn_fee) || 0),
              value: bd.txnBrokerageFees }
          : null),
        { label: 'Monthly fee',
          sub: plan && plan.monthly_fee ? fmtMoney(plan.monthly_fee) + '/mo x 12' : 'No monthly fees',
          value: bd.monthly || 0 },
        { label: 'Annual fee',
          sub: (plan && plan.annual_fee_note) || 'Annual fee',
          value: bd.annual || 0 },
        (bd.eo > 0 || !(plan && plan.eo_note)
          ? { label: 'E&O insurance', sub: (plan && plan.eo_note) || 'Annual E&O', value: bd.eo || 0 }
          : null),
        (bd.franchise > 0
          ? { label: 'Franchise royalty',
              sub: (plan ? plan.franchise_fee_pct : 0) + '% (cap ' + fmtMoney((plan && plan.franchise_fee_cap_annual) || 0) + ')',
              value: bd.franchise }
          : null),
        (bd.marketing > 0
          ? { label: 'Marketing fee', sub: (plan && plan.marketing_fee_pct) + '%', value: bd.marketing }
          : null),
        (bd.optional > 0
          ? { label: 'LPT Plus upgrade', sub: 'Optional tech add-on', value: bd.optional }
          : null)
      ].filter(Boolean),
      total: r.total, net: r.net, retainedPct: r.retainedPct,
      per_txn_brokerage_fee: plan ? plan.per_txn_brokerage_fee : null,
      source_url: b.source_url || null,
      data_asof: b.data_asof || null
    });

    const be = calcCapBreakeven(plan, avgGciPerTxn);
    const pct = progressToCap(plan, gci, txns);
    capBreakeven.push({
      slug: b.slug, name: b.name, short_name: b.short_name,
      plan_name: plan && plan.plan_name,
      isLpt,
      cap: plan && plan.annual_cap ? plan.annual_cap : null,
      breakEvenLabel: be.label || '-',
      breakEvenSub: be.sub || null,
      progressPct: pct
    });
  });

  cols.forEach(col => {
    const proj = calcProjection(col.brokerage, col.plan, gci, txns, avgGciPerTxn, growthPct || 0, lptPlus);
    if (!proj) return;
    projection.push({
      slug: col.brokerage.slug,
      name: col.brokerage.name,
      short_name: col.brokerage.short_name,
      plan_name: col.plan && col.plan.plan_name,
      isLpt: col.brokerage.slug === LPT_SLUG,
      rows: proj.rows.map(r => ({
        year: r.year, gci: r.gci, txns: r.txns, net: r.net, cumulative: r.cumulative
      })),
      total: proj.total
    });
  });

  // LPT equity + hybridshare (only if LPT in the selection's matrix cols)
  const lptInSelection = cols.find(c => c.brokerage && c.brokerage.slug === LPT_SLUG);
  let hybridshareData = null;
  let lptEquityLadder = null;
  let lptEquity = null;

  if (lptInSelection) {
    const lpt = lptInSelection.brokerage;
    if (lpt.revshare && Array.isArray(lpt.revshare.tier_breakdown)) {
      hybridshareData = {
        tiers: lpt.revshare.tier_breakdown.map(t => ({
          tier: t.tier,
          pct_of_pool: t.pct_of_pool,
          max_bp: t.max_annual_from_bp_downline_usd,
          max_bb: t.max_annual_from_bb_downline_usd,
          min_directs: t.min_active_direct_sponsored_to_unlock
        }))
      };
    }
    if (lpt.equity && lpt.equity.achievement_awards) {
      const awards = lpt.equity.achievement_awards;
      const earned = earnedBadgesForTxns(awards, txns);
      const totals = sumEarnedShares(awards, txns);
      let cum_bp = 0, cum_bb = 0;
      for (let y = 1; y <= 3; y++) {
        const mult = Math.pow(1 + (growthPct || 0) / 100, y - 1);
        const txY = Math.max(1, Math.round(txns * mult));
        const yt = sumEarnedShares(awards, txY);
        cum_bp += yt.bp; cum_bb += yt.bb;
      }
      lptEquity = {
        thisYear: { badges: earned.map(b => b.badge), bp: totals.bp, bb: totals.bb },
        threeYear: { bp: cum_bp, bb: cum_bb }
      };
      lptEquityLadder = {
        awards: awards.map(a => ({
          badge: a.badge,
          threshold: a.annual_core_transactions,
          shares_bp: a.shares_bp,
          shares_bb: a.shares_bb,
          shares_bb_note: a.shares_bb_note || null
        })),
        sponsorship: lpt.equity.sponsorship_award_per_direct_sponsored || null
      };
    }
  }

  return {
    comparisonResults,
    detailColumns,
    breakdownBlocks,
    capBreakeven,
    projection,
    hybridshare: hybridshareData,
    lptEquityLadder,
    lptEquity
  };
}

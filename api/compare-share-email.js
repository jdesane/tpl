// Vercel serverless function — sends the "email this comparison to me" email
// triggered from the public /compare email modal. Public endpoint, no auth.
// Saves the full comparison snapshot (including custom brokerages) server-side
// so the email link can restore the exact comparison via /compare?report=<token>.
// Generates a branded PDF recap and attaches it to the Resend send.
import { generateComparisonPdf } from './_lib/comparison-pdf.js';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_KEY
);

async function sendResend({ to, from, replyTo, subject, html, attachments }) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) return { ok: false, error: 'RESEND_API_KEY missing' };
  const payload = { from, to: Array.isArray(to) ? to : [to], subject, html };
  if (replyTo) payload.reply_to = replyTo;
  if (Array.isArray(attachments) && attachments.length) payload.attachments = attachments;
  const res = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${apiKey}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  });
  const body = await res.json().catch(() => ({}));
  return { ok: res.ok, status: res.status, body };
}

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

const BROKERAGE_LABELS = {
  'lpt-realty': 'LPT Realty',
  'keller-williams': 'Keller Williams',
  'exp-realty': 'eXp Realty',
  'real-brokerage': 'REAL Brokerage',
  'compass': 'Compass',
  'remax': 'RE/MAX',
  'coldwell-banker': 'Coldwell Banker',
  'century-21': 'Century 21',
  'epique-realty': 'Epique Realty',
  'homesmart': 'HomeSmart',
  'berkshire-hathaway': 'Berkshire Hathaway HomeServices',
  'fathom-realty': 'Fathom Realty',
  'sothebys': "Sotheby's International Realty",
  'douglas-elliman': 'Douglas Elliman',
  'the-agency': 'The Agency',
  'redfin': 'Redfin',
  'realty-one-group': 'Realty ONE Group',
  'united-real-estate': 'United Real Estate',
  'samson-properties': 'Samson Properties',
  'lokation': 'LoKation Real Estate'
};

function buildEmailHtml({ firstName, shareUrl, selectionLabels, gci, txns, lptPlan, lptPlus }) {
  const safeFirst = (firstName || 'there').toString().trim().split(/\s+/)[0];
  const competitorList = selectionLabels.length
    ? selectionLabels.join(', ')
    : 'your selected brokerages';
  const planLine = lptPlan === 'bp'
    ? 'LPT Brokerage Partner only'
    : lptPlan === 'bb'
      ? 'LPT Business Builder only'
      : 'LPT Brokerage Partner + Business Builder';
  const plusLine = lptPlus ? ' (with LPT Plus add-on)' : '';
  const gciStr = '$' + (Math.round(gci || 0)).toLocaleString();
  return `<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f7;margin:0;padding:24px;">
  <div style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;padding:32px 28px;box-shadow:0 4px 16px rgba(0,0,0,0.06);">
    <div style="font-family:'Bebas Neue',Impact,sans-serif;font-size:14px;letter-spacing:0.18em;color:#888;text-transform:uppercase;margin-bottom:6px;">TPL Collective</div>
    <h1 style="font-size:24px;color:#1a1a1a;margin:0 0 16px;line-height:1.25;">Hi ${escapeHtml(safeFirst)} &mdash; here's your comparison</h1>
    <p style="font-size:15px;line-height:1.6;color:#333;margin:0 0 14px;">You compared <strong>${escapeHtml(competitorList)}</strong> at <strong>${escapeHtml(gciStr)}</strong> annual GCI across <strong>${escapeHtml(String(txns || 0))}</strong> transactions.</p>
    <p style="font-size:13px;line-height:1.6;color:#666;margin:0 0 20px;">View: ${escapeHtml(planLine)}${escapeHtml(plusLine)}</p>
    <div style="text-align:center;margin:0 0 24px;">
      <a href="${escapeHtml(shareUrl)}" style="display:inline-block;background:#f0c040;color:#1a1a1a;padding:14px 28px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px;letter-spacing:0.04em;">View Full Comparison &rarr;</a>
    </div>
    <p style="font-size:13px;line-height:1.6;color:#666;margin:0 0 8px;">All numbers are from public sources and the official LPT comp plan flyer. The comparison page shows total brokerage cost, net retained, cap break-even, 3-year projection, and LPT equity bonus.</p>
    <p style="font-size:13px;line-height:1.6;color:#666;margin:0;">Questions? Just reply to this email.</p>
    <hr style="border:0;border-top:1px solid #eee;margin:24px 0 14px;">
    <p style="font-size:11px;color:#999;margin:0;">TPL Collective &middot; Built for agents who want real numbers, not pitches.</p>
  </div>
</body></html>`;
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).end();

  const body = req.body || {};
  const {
    name, email, share_url, selection,
    gci, txns, lpt_plan, lpt_plus,
    growth_pct,
    avg_sale_price, commission_pct,
    comparison_results,
    detail_columns,
    breakdown_blocks,
    cap_breakeven,
    projection,
    hybridshare,
    lpt_equity_ladder,
    lpt_equity
  } = body;

  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ success: false, error: 'Valid email required' });
  }
  if (!share_url || typeof share_url !== 'string') {
    return res.status(400).json({ success: false, error: 'share_url required' });
  }

  const selectionSlugs = Array.isArray(selection) ? selection : [];
  const selectionLabels = selectionSlugs.map(s => {
    if (typeof s === 'string') return BROKERAGE_LABELS[s] || s;
    if (s && s.name) return s.name;          // custom brokerage object
    return null;
  }).filter(Boolean);

  const firstName = (name || '').toString().trim().split(/\s+/)[0] || '';

  // ── Save full comparison snapshot to Supabase so the email link can restore it ──
  // The recipient lands on /compare?report=<token> which fetches this row and
  // hydrates state — including custom brokerages, which can't fit in URL params.
  let tokenUrl = share_url;        // fallback to URL-state version if save fails
  let savedToken = null;
  let saveError = null;
  try {
    // The frontend may send `selection` as a mix of slug strings (published) and
    // {slug, name, isCustom, plans, _customForm, ...} objects (custom). For the
    // saved row we need full brokerage objects so report-mode can render them.
    // The richer `comparison_results` array has display rows but not source plans;
    // we keep BOTH so the loader has everything it needs.
    const saved = await supabase
      .from('recruit_comparisons')
      .insert({
        recruit_first_name: firstName || null,
        recruit_last_name: null,
        recruit_email: email,
        current_brokerage_name: null,
        selection: body.selection_full || selection,
        gci: gci || 0,
        txns: txns || 0,
        avg_gci_per_txn: (gci && txns) ? gci / txns : null,
        lpt_plan: lpt_plan || 'both',
        lpt_plus: !!lpt_plus,
        comparison_result: {
          rows: comparison_results || [],
          lpt_equity: lpt_equity || null,
          avg_sale_price: avg_sale_price || null,
          commission_pct: commission_pct || null
        },
        notes: 'Self-share from public /compare email modal'
      })
      .select('share_token')
      .single();
    if (saved.data && saved.data.share_token) {
      savedToken = saved.data.share_token;
      tokenUrl = `https://tplcollective.ai/compare?report=${savedToken}`;
    } else if (saved.error) {
      saveError = saved.error.message;
    }
  } catch (err) {
    saveError = err && err.message ? err.message : 'snapshot save failed';
    console.error('Comparison save error:', err);
  }

  const subject = 'Your brokerage comparison from TPL Collective';
  const html = buildEmailHtml({
    firstName,
    shareUrl: tokenUrl,
    selectionLabels,
    gci: gci || 0,
    txns: txns || 0,
    lptPlan: lpt_plan || 'both',
    lptPlus: !!lpt_plus
  });

  // Generate the PDF recap
  let attachments = [];
  let pdfError = null;
  try {
    const pdfBuf = await generateComparisonPdf({
      recipientName: firstName || null,
      brokerages: Array.isArray(comparison_results) ? comparison_results : [],
      detailColumns: Array.isArray(detail_columns) ? detail_columns : [],
      breakdownBlocks: Array.isArray(breakdown_blocks) ? breakdown_blocks : [],
      capBreakeven: Array.isArray(cap_breakeven) ? cap_breakeven : [],
      projection: Array.isArray(projection) ? projection : [],
      hybridshare: hybridshare || null,
      lptEquityLadder: lpt_equity_ladder || null,
      lptEquity: lpt_equity || null,
      avgSalePrice: avg_sale_price || null,
      commissionPct: commission_pct || null,
      gci: gci || 0,
      txns: txns || 0,
      lptPlan: lpt_plan || 'both',
      lptPlus: !!lpt_plus,
      growthPct: growth_pct || 0,
      shareUrl: tokenUrl
    });
    const today = new Date().toISOString().slice(0, 10);
    const safeName = (firstName || 'Comparison').replace(/[^A-Za-z0-9_-]/g, '');
    attachments = [{
      filename: `TPL-Brokerage-Comparison-${safeName}-${today}.pdf`,
      content: pdfBuf.toString('base64')
    }];
  } catch (err) {
    pdfError = err && err.message ? err.message : 'PDF generation failed';
    console.error('PDF generation error:', err);
  }

  const result = await sendResend({
    to: email,
    from: 'TPL Collective <comparisons@tplcollective.ai>',
    replyTo: 'joe@tplcollective.co',
    subject,
    html,
    attachments
  });

  if (!result.ok) {
    return res.status(502).json({
      success: false,
      error: result.error || result.body?.message || 'Email send failed',
      status: result.status,
      pdf_error: pdfError
    });
  }

  return res.status(200).json({
    success: true,
    resend_id: result.body?.id || null,
    pdf_attached: attachments.length > 0,
    pdf_error: pdfError,
    share_token: savedToken,
    token_url: savedToken ? tokenUrl : null,
    save_error: saveError
  });
}

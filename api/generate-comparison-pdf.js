// Generates a brokerage comparison PDF and returns it as base64.
// Called server-side from Mission Control's recruit-comparison flow so the
// recipient gets the same rich PDF the public /compare email modal produces.
import { generateComparisonPdf } from './_lib/comparison-pdf.js';
import { buildReportData } from './_lib/comparison-calc.js';

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).end();

  const body = req.body || {};
  const {
    recipient_name, sender_name, share_url,
    selection,
    gci, txns, avg_gci_per_txn,
    lpt_plan, lpt_plus, growth_pct,
    avg_sale_price, commission_pct
  } = body;

  if (!Array.isArray(selection) || !selection.length) {
    return res.status(400).json({ success: false, error: 'selection required' });
  }
  const txnsNum = parseInt(txns, 10);
  const gciNum = parseFloat(gci);
  if (!gciNum || !txnsNum) {
    return res.status(400).json({ success: false, error: 'gci and txns required' });
  }
  const avgGci = avg_gci_per_txn || (gciNum && txnsNum ? gciNum / txnsNum : 0);

  let report;
  try {
    report = await buildReportData({
      selection,
      gci: gciNum,
      txns: txnsNum,
      avgGciPerTxn: avgGci,
      lptPlan: lpt_plan || 'both',
      lptPlus: !!lpt_plus,
      growthPct: parseFloat(growth_pct) || 0
    });
  } catch (err) {
    return res.status(500).json({ success: false, error: 'compute failed: ' + (err.message || err) });
  }

  let pdfBase64;
  let filename;
  try {
    const pdfBuf = await generateComparisonPdf({
      recipientName: recipient_name || null,
      preparedBy: sender_name || null,
      brokerages: report.comparisonResults,
      detailColumns: report.detailColumns,
      breakdownBlocks: report.breakdownBlocks,
      capBreakeven: report.capBreakeven,
      projection: report.projection,
      hybridshare: report.hybridshare,
      lptEquityLadder: report.lptEquityLadder,
      lptEquity: report.lptEquity,
      avgSalePrice: avg_sale_price || null,
      commissionPct: commission_pct || null,
      gci: gciNum,
      txns: txnsNum,
      lptPlan: lpt_plan || 'both',
      lptPlus: !!lpt_plus,
      growthPct: parseFloat(growth_pct) || 0,
      shareUrl: share_url || null
    });
    pdfBase64 = pdfBuf.toString('base64');
    const safeName = (recipient_name || 'Comparison').replace(/[^A-Za-z0-9_-]/g, '');
    filename = `TPL-Brokerage-Comparison-${safeName}-${new Date().toISOString().slice(0, 10)}.pdf`;
  } catch (err) {
    return res.status(500).json({ success: false, error: 'pdf failed: ' + (err.message || err) });
  }

  return res.status(200).json({
    success: true,
    pdf_base64: pdfBase64,
    filename,
    report_summary: {
      brokerage_count: report.comparisonResults.length,
      gci: gciNum,
      txns: txnsNum
    }
  });
}

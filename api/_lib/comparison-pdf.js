// Generate a PDF recap of a brokerage comparison.
// Used by /api/compare-share-email.
import PDFDocument from 'pdfkit';

const fmtMoney = (n) => {
  if (n == null || isNaN(n)) return '-';
  return '$' + Math.round(n).toLocaleString('en-US');
};
const fmtPct = (n) => (n == null || isNaN(n)) ? '-' : (Number(n).toFixed(1) + '%');

const COLORS = {
  bg: '#0a0a0f',
  panel: '#15151f',
  border: '#2a2a35',
  text: '#e8e8ec',
  muted: '#9090a0',
  gold: '#f0c040',
  green: '#4dd181',
  red: '#e87878'
};

export async function generateComparisonPdf({
  recipientName,
  brokerages = [],         // [{ slug, name, plan_name, isCustom, total, net, retainedPct }, ...]
  avgSalePrice,            // optional
  commissionPct,           // optional
  gci,
  txns,
  lptPlan,
  lptPlus,
  shareUrl,
  preparedBy,              // optional sender name (from recruit-comparison flow)
  lptEquity                // optional { thisYear: { badges: ['White','Silver'], bp, bb }, threeYear: { bp, bb } }
}) {
  return new Promise((resolve, reject) => {
    const doc = new PDFDocument({
      size: 'LETTER',
      margins: { top: 56, bottom: 56, left: 56, right: 56 },
      bufferPages: true       // lets us render the footer on page 1 regardless of overflow
    });
    const chunks = [];
    doc.on('data', (c) => chunks.push(c));
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    // Background fill
    doc.rect(0, 0, doc.page.width, doc.page.height).fill(COLORS.bg);
    doc.fillColor(COLORS.text);

    // ── HEADER ──
    doc
      .fillColor(COLORS.gold)
      .fontSize(10)
      .text('TPL COLLECTIVE', 56, 56, { characterSpacing: 2 });

    doc
      .fillColor(COLORS.text)
      .fontSize(24)
      .text('Brokerage Cost Comparison', 56, 75);

    const today = new Date().toLocaleDateString('en-US', {
      year: 'numeric', month: 'long', day: 'numeric'
    });
    const headerLine = (recipientName ? `Prepared for ${recipientName}` : '') +
                       (preparedBy ? `${recipientName ? '  ·  ' : ''}Prepared by ${preparedBy}` : '') +
                       `${(recipientName || preparedBy) ? '  ·  ' : ''}${today}`;
    doc
      .fillColor(COLORS.muted)
      .fontSize(10)
      .text(headerLine, 56, 110);

    // Divider
    doc.moveTo(56, 132).lineTo(doc.page.width - 56, 132).strokeColor(COLORS.border).lineWidth(0.5).stroke();

    // ── YOUR NUMBERS ──
    let y = 150;
    doc.fillColor(COLORS.gold).fontSize(9).text('YOUR NUMBERS', 56, y, { characterSpacing: 1.5 });
    y += 16;
    const numberRows = [];
    if (avgSalePrice) numberRows.push(['Avg sale price', fmtMoney(avgSalePrice)]);
    if (commissionPct) numberRows.push(['Avg commission', commissionPct + '%']);
    numberRows.push(['Deals per year', String(txns || 0)]);
    numberRows.push(['Annual GCI', fmtMoney(gci)]);
    const lptPlanLabel = lptPlan === 'bp' ? 'Brokerage Partner only'
      : lptPlan === 'bb' ? 'Business Builder only'
      : 'Brokerage Partner + Business Builder';
    numberRows.push(['LPT plan view', lptPlanLabel]);
    numberRows.push(['LPT Plus add-on', lptPlus ? 'Yes' : 'No']);

    numberRows.forEach(([label, value]) => {
      doc.fillColor(COLORS.muted).fontSize(10).text(label, 56, y);
      doc.fillColor(COLORS.text).fontSize(10).text(value, 250, y);
      y += 16;
    });

    y += 12;
    doc.moveTo(56, y).lineTo(doc.page.width - 56, y).strokeColor(COLORS.border).lineWidth(0.5).stroke();
    y += 18;

    // ── COST COMPARISON TABLE ──
    doc.fillColor(COLORS.gold).fontSize(9).text('COST COMPARISON', 56, y, { characterSpacing: 1.5 });
    y += 18;

    // Headers
    doc.fillColor(COLORS.muted).fontSize(8);
    doc.text('BROKERAGE', 56, y, { characterSpacing: 1 });
    doc.text('PLAN', 220, y, { characterSpacing: 1 });
    doc.text('TOTAL COST', 350, y, { width: 90, align: 'right', characterSpacing: 1 });
    doc.text('NET RETAINED', 445, y, { width: 95, align: 'right', characterSpacing: 1 });
    y += 12;
    doc.moveTo(56, y).lineTo(doc.page.width - 56, y).strokeColor(COLORS.border).lineWidth(0.3).stroke();
    y += 8;

    // Identify LPT BP for delta calculation baseline
    const lptBP = brokerages.find(b => b.slug === 'lpt-realty' && /brokerage partner/i.test(b.plan_name || ''));
    const baselineNet = lptBP ? lptBP.net : null;

    brokerages.forEach((b) => {
      // Brokerage name + plan
      const isLpt = b.slug === 'lpt-realty';
      const isCustom = !!b.isCustom;
      doc.fillColor(isLpt ? COLORS.gold : COLORS.text).fontSize(10).text(
        (b.name || '?') + (isCustom ? '  (Custom)' : ''),
        56, y, { width: 160 }
      );
      doc.fillColor(COLORS.muted).fontSize(9).text(b.plan_name || '-', 220, y, { width: 120 });
      doc.fillColor(b.total != null ? COLORS.red : COLORS.muted).fontSize(11).text(
        fmtMoney(b.total),
        350, y, { width: 90, align: 'right' }
      );
      doc.fillColor(b.net != null ? COLORS.green : COLORS.muted).fontSize(11).text(
        fmtMoney(b.net),
        445, y, { width: 95, align: 'right' }
      );
      y += 18;

      // Sub line: retained % + delta vs LPT BP (use ASCII-only chars; Helvetica
      // bundled with pdfkit doesn't render Δ, em-dashes, etc.)
      const subParts = [];
      if (b.retainedPct != null) subParts.push(fmtPct(b.retainedPct) + ' retained');
      if (baselineNet != null && b.net != null && !isLpt) {
        const delta = b.net - baselineNet;
        const sign = delta >= 0 ? '+' : '-';
        subParts.push('vs LPT BP: ' + sign + fmtMoney(Math.abs(delta)) + '/yr');
      }
      if (subParts.length) {
        doc.fillColor(COLORS.muted).fontSize(8).text(subParts.join('   |   '), 220, y, { width: 320 });
        y += 12;
      }
      doc.moveTo(56, y).lineTo(doc.page.width - 56, y).strokeColor(COLORS.border).lineWidth(0.2).stroke();
      y += 10;
    });

    // ── LPT EQUITY BONUS (if data present) ──
    if (lptEquity && lptEquity.thisYear) {
      y += 14;
      doc.fillColor(COLORS.gold).fontSize(9).text('LPT EQUITY BONUS', 56, y, { characterSpacing: 1.5 });
      y += 16;
      doc.fillColor(COLORS.muted).fontSize(9).text(
        'RSU shares awarded based on annual core transactions. Awards stack - hitting Silver also earns White, etc. 3-year vest. Private equity (no open market).',
        56, y, { width: doc.page.width - 112 }
      );
      y += 28;

      const tyBadges = (lptEquity.thisYear.badges || []).join(' + ') || '-';
      doc.fillColor(COLORS.text).fontSize(10).text('This year:  ' + tyBadges, 56, y);
      y += 14;
      doc.fillColor(COLORS.gold).fontSize(11).text(
        '  ' + (lptEquity.thisYear.bp || 0).toLocaleString() + ' shares  (BP)' +
        '   ·   ' +
        (lptEquity.thisYear.bb || 0).toLocaleString() + ' shares  (BB)',
        56, y
      );
      y += 16;

      if (lptEquity.threeYear) {
        doc.fillColor(COLORS.muted).fontSize(10).text(
          '3-year cumulative (with growth):',
          56, y
        );
        y += 14;
        doc.fillColor(COLORS.gold).fontSize(11).text(
          '  ' + (lptEquity.threeYear.bp || 0).toLocaleString() + ' shares  (BP)' +
          '   ·   ' +
          (lptEquity.threeYear.bb || 0).toLocaleString() + ' shares  (BB)',
          56, y
        );
        y += 16;
      }
    }

    // ── FOOTER ── (always on page 0)
    // Background-fill any pages that exist (in case body overflowed onto pages 2+).
    const range = doc.bufferedPageRange();
    for (let i = range.start; i < range.start + range.count; i++) {
      doc.switchToPage(i);
      doc.rect(0, 0, doc.page.width, doc.page.height).fill(COLORS.bg);
    }
    // Anchor footer to page 0. Stay well within the bottom margin (56) so pdfkit
    // doesn't auto-paginate on us. Bottom-of-usable-area is page.height - 56 = 736.
    doc.switchToPage(range.start);
    const pageH = doc.page.height;
    const footerLineY = pageH - 92;   // 700 — divider line
    doc.moveTo(56, footerLineY).lineTo(doc.page.width - 56, footerLineY)
       .strokeColor(COLORS.border).lineWidth(0.5).stroke();

    doc.fillColor(COLORS.muted).fontSize(8).text(
      'Source: official lpt.com flyer (valid 4/30/26) and publicly documented competitor data.  TPL Collective.',
      56, footerLineY + 8,
      { width: doc.page.width - 112, lineBreak: false }
    );
    if (shareUrl) {
      doc.fillColor(COLORS.gold).fontSize(8).text(
        'Interactive view: ' + shareUrl,
        56, footerLineY + 22,
        { width: doc.page.width - 112, lineBreak: false, link: shareUrl, underline: false }
      );
    }

    doc.end();
  });
}

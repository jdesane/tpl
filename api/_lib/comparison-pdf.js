// Generate a multi-page PDF recap of a brokerage comparison that mirrors the
// live /compare page. Used by /api/compare-share-email.
import PDFDocument from 'pdfkit';

const fmtMoney = (n) => {
  if (n == null || isNaN(n)) return '-';
  return '$' + Math.round(n).toLocaleString('en-US');
};
const fmtMoneyShort = (n) => {
  if (n == null || isNaN(n)) return '-';
  if (n >= 1000000) return '$' + (n / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
  if (n >= 1000) return '$' + Math.round(n / 1000) + 'K';
  return '$' + Math.round(n);
};
const fmtPct = (n) => (n == null || isNaN(n)) ? '-' : (Number(n).toFixed(1) + '%');

const C = {
  bg: '#0a0a0f',
  panel: '#15151f',
  border: '#2a2a35',
  borderSoft: '#1f1f29',
  text: '#e8e8ec',
  muted: '#9090a0',
  dim: '#5e5e6d',
  gold: '#f0c040',
  goldDim: '#7a6020',
  green: '#4dd181',
  red: '#e87878',
  blue: '#7aa3ff'
};

const PAGE = {
  width: 612,             // LETTER
  height: 792,
  marginTop: 56,
  marginBottom: 56,
  marginLeft: 56,
  marginRight: 56
};
const CONTENT_WIDTH = PAGE.width - PAGE.marginLeft - PAGE.marginRight;
const BOTTOM_LIMIT = PAGE.height - PAGE.marginBottom - 28; // leave room for footer line

export async function generateComparisonPdf(opts) {
  const {
    recipientName,
    brokerages = [],
    detailColumns = [],
    breakdownBlocks = [],
    capBreakeven = [],
    projection = [],
    hybridshare = null,
    lptEquityLadder = null,
    lptEquity = null,
    avgSalePrice,
    commissionPct,
    gci,
    txns,
    lptPlan,
    lptPlus,
    growthPct = 0,
    shareUrl,
    preparedBy
  } = opts;

  return new Promise((resolve, reject) => {
    const doc = new PDFDocument({
      size: 'LETTER',
      margins: {
        top: PAGE.marginTop, bottom: PAGE.marginBottom,
        left: PAGE.marginLeft, right: PAGE.marginRight
      },
      bufferPages: true,
      autoFirstPage: false
    });
    const chunks = [];
    doc.on('data', (c) => chunks.push(c));
    doc.on('end', () => resolve(Buffer.concat(chunks)));
    doc.on('error', reject);

    let pageHeader = null; // closure used by addPage

    function paintBg() {
      doc.save();
      doc.rect(0, 0, doc.page.width, doc.page.height).fill(C.bg);
      doc.restore();
      doc.fillColor(C.text);
    }

    function newPage() {
      doc.addPage();
      paintBg();
      doc.y = PAGE.marginTop;
    }

    function ensureSpace(needed) {
      if (doc.y + needed > BOTTOM_LIMIT) newPage();
    }

    function rule(color = C.border, width = 0.5) {
      doc.strokeColor(color).lineWidth(width)
         .moveTo(PAGE.marginLeft, doc.y).lineTo(PAGE.width - PAGE.marginRight, doc.y).stroke();
      doc.y += 1;
    }

    function sectionLabel(text) {
      ensureSpace(28);
      doc.fillColor(C.gold).fontSize(9).text(text, PAGE.marginLeft, doc.y, {
        characterSpacing: 1.6, lineBreak: false
      });
      doc.y += 16;
    }

    function pageTitle(text) {
      doc.fillColor(C.text).fontSize(22).text(text, PAGE.marginLeft, doc.y, { lineBreak: false });
      doc.y += 28;
    }

    function pageEyebrow(label, sub) {
      doc.fillColor(C.gold).fontSize(9).text(label, PAGE.marginLeft, doc.y, {
        characterSpacing: 1.6, lineBreak: false
      });
      doc.y += 14;
      if (sub) {
        doc.fillColor(C.muted).fontSize(10).text(sub, PAGE.marginLeft, doc.y, {
          width: CONTENT_WIDTH
        });
        doc.y += 8;
      }
    }

    // ─────── PAGE 1: HEADER + YOUR NUMBERS + COST COMPARISON ───────
    newPage();
    doc.fillColor(C.gold).fontSize(10).text('TPL COLLECTIVE', PAGE.marginLeft, doc.y, {
      characterSpacing: 2, lineBreak: false
    });
    doc.y += 18;
    doc.fillColor(C.text).fontSize(24).text('Brokerage Cost Comparison', PAGE.marginLeft, doc.y, { lineBreak: false });
    doc.y += 30;

    const today = new Date().toLocaleDateString('en-US', {
      year: 'numeric', month: 'long', day: 'numeric'
    });
    const headerParts = [];
    if (recipientName) headerParts.push('Prepared for ' + recipientName);
    if (preparedBy) headerParts.push('Prepared by ' + preparedBy);
    headerParts.push(today);
    doc.fillColor(C.muted).fontSize(10).text(headerParts.join('  |  '), PAGE.marginLeft, doc.y, {
      lineBreak: false
    });
    doc.y += 18;
    rule();
    doc.y += 14;

    // Your Numbers
    sectionLabel('YOUR NUMBERS');
    const yourNumbers = [];
    if (avgSalePrice) yourNumbers.push(['Avg sale price', fmtMoney(avgSalePrice)]);
    if (commissionPct) yourNumbers.push(['Avg commission', commissionPct + '%']);
    yourNumbers.push(['Deals per year', String(txns || 0)]);
    yourNumbers.push(['Annual GCI', fmtMoney(gci)]);
    const planLabel = lptPlan === 'bp' ? 'Brokerage Partner only'
      : lptPlan === 'bb' ? 'Business Builder only'
      : 'Brokerage Partner + Business Builder';
    yourNumbers.push(['LPT plan view', planLabel]);
    yourNumbers.push(['LPT Plus add-on', lptPlus ? 'Yes' : 'No']);
    yourNumbers.forEach(([k, v]) => {
      ensureSpace(16);
      doc.fillColor(C.muted).fontSize(10).text(k, PAGE.marginLeft, doc.y, { lineBreak: false });
      doc.fillColor(C.text).fontSize(10).text(v, PAGE.marginLeft + 200, doc.y, { lineBreak: false });
      doc.y += 16;
    });
    doc.y += 8;
    rule();
    doc.y += 14;

    // Cost Comparison summary
    sectionLabel('COST COMPARISON');
    const tableLeft = PAGE.marginLeft;
    const colName = tableLeft;          // 56
    const colPlan = tableLeft + 160;    // 216
    const colCost = tableLeft + 305;    // 361
    const colCostW = 90;
    const colNet = tableLeft + 410;     // 466
    const colNetW = 90;

    doc.fillColor(C.muted).fontSize(8);
    doc.text('BROKERAGE', colName, doc.y, { characterSpacing: 1, lineBreak: false });
    doc.text('PLAN', colPlan, doc.y, { characterSpacing: 1, lineBreak: false });
    doc.text('TOTAL COST', colCost, doc.y, { width: colCostW, align: 'right', characterSpacing: 1, lineBreak: false });
    doc.text('NET RETAINED', colNet, doc.y, { width: colNetW, align: 'right', characterSpacing: 1, lineBreak: false });
    doc.y += 12;
    rule(C.border, 0.4);
    doc.y += 6;

    const lptBP = brokerages.find(b => b.slug === 'lpt-realty' && /brokerage partner/i.test(b.plan_name || ''));
    const baselineNet = lptBP ? lptBP.net : null;

    brokerages.forEach((b) => {
      ensureSpace(38);
      const isLpt = b.slug === 'lpt-realty';
      const rY = doc.y;
      doc.fillColor(isLpt ? C.gold : C.text).fontSize(10).text(
        (b.name || '?') + (b.isCustom ? '  (Custom)' : ''),
        colName, rY, { width: 155, lineBreak: false }
      );
      doc.fillColor(C.muted).fontSize(9).text(b.plan_name || '-', colPlan, rY, { width: 140, lineBreak: false });
      doc.fillColor(b.total != null ? C.red : C.muted).fontSize(11).text(
        fmtMoney(b.total), colCost, rY, { width: colCostW, align: 'right', lineBreak: false }
      );
      doc.fillColor(b.net != null ? C.green : C.muted).fontSize(11).text(
        fmtMoney(b.net), colNet, rY, { width: colNetW, align: 'right', lineBreak: false }
      );
      doc.y = rY + 16;
      const subParts = [];
      if (b.retainedPct != null) subParts.push(fmtPct(b.retainedPct) + ' retained');
      if (baselineNet != null && b.net != null && !isLpt) {
        const delta = b.net - baselineNet;
        subParts.push('vs LPT BP: ' + (delta >= 0 ? '+' : '-') + fmtMoney(Math.abs(delta)) + '/yr');
      }
      if (subParts.length) {
        const subY = doc.y;
        doc.fillColor(C.muted).fontSize(8).text(subParts.join('   |   '), colPlan, subY, { width: 320, lineBreak: false });
        doc.y = subY + 11;
      }
      rule(C.borderSoft, 0.3);
      doc.y += 5;
    });

    // ─────── PAGE 2: SIDE-BY-SIDE DETAIL ───────
    if (detailColumns && detailColumns.length) {
      newPage();
      pageEyebrow('SIDE BY SIDE', 'Every cost driver visible on the live /compare matrix.');
      doc.y += 4;

      const cols = detailColumns;
      const labelW = 130;
      const colW = Math.min(105, Math.floor((CONTENT_WIDTH - labelW) / Math.max(cols.length, 1)));

      // Header row: brokerage name then plan name on a second sub-line — drawn on locked y.
      ensureSpace(30);
      let rowY = doc.y;
      cols.forEach((c, i) => {
        const x = PAGE.marginLeft + labelW + i * colW;
        const isLpt = c.slug === 'lpt-realty';
        doc.fillColor(isLpt ? C.gold : C.text).fontSize(9).text(
          c.short_name || c.name || '-',
          x, rowY, { width: colW - 6, lineBreak: false }
        );
      });
      cols.forEach((c, i) => {
        if (!c.plan_name) return;
        const x = PAGE.marginLeft + labelW + i * colW;
        doc.fillColor(C.muted).fontSize(7).text(
          c.plan_name, x, rowY + 12, { width: colW - 6, lineBreak: false }
        );
      });
      doc.y = rowY + 24;
      rule(C.border, 0.5);
      doc.y += 4;

      function detailRow(label, valuesFn, opts = {}) {
        const lineH = opts.tall ? 16 : 14;
        ensureSpace(lineH + 4);
        const rY = doc.y;
        doc.fillColor(C.muted).fontSize(8).text(
          label, PAGE.marginLeft, rY, { width: labelW, lineBreak: false }
        );
        cols.forEach((c, i) => {
          const x = PAGE.marginLeft + labelW + i * colW;
          const v = valuesFn(c) || '-';
          doc.fillColor(opts.color || C.text).fontSize(opts.size || 9).text(
            String(v), x, rY, { width: colW - 6, lineBreak: false }
          );
        });
        doc.y = rY + lineH;
        rule(C.borderSoft, 0.2);
        doc.y += 2;
      }

      // OVERVIEW
      sectionLabel('OVERVIEW');
      detailRow('Model', c => c.model_type || '-');
      detailRow('Founded', c => c.founded || '-');
      detailRow('Public ticker', c => c.public_ticker || '-');
      doc.y += 6;

      // COST STRUCTURE
      sectionLabel('COST STRUCTURE');
      detailRow('Plan', c => c.plan_name || '-');
      detailRow('Split', c => c.split_structure || '-');
      detailRow('Annual cap', c => c.annual_cap ? fmtMoney(c.annual_cap) : 'No cap');
      detailRow('Monthly fee', c => c.monthly_fee ? fmtMoney(c.monthly_fee) + '/mo' : '-');
      detailRow('Annual fee', c => c.annual_fee != null ? fmtMoney(c.annual_fee) : '-');
      detailRow('E&O insurance', c => c.eo_insurance_annual != null ? fmtMoney(c.eo_insurance_annual) : '-');
      detailRow('Franchise royalty', c => c.franchise_fee_pct
        ? c.franchise_fee_pct + '%' + (c.franchise_fee_cap_annual ? ' cap ' + fmtMoneyShort(c.franchise_fee_cap_annual) : '')
        : 'None');
      detailRow('Per-txn fee', c => c.per_txn_brokerage_fee
        ? fmtMoney(c.per_txn_brokerage_fee) + '/txn'
        : (c.flat_fee_per_txn ? fmtMoney(c.flat_fee_per_txn) + '/txn (flat)' : '-'));
      doc.y += 8;

      // CALCULATED TOTAL
      sectionLabel('CALCULATED TOTAL');
      detailRow('Total cost', c => fmtMoney(c.total), { color: C.red, size: 11, tall: true });
      detailRow('Net to agent', c => fmtMoney(c.net), { color: C.green, size: 11, tall: true });
      detailRow('Retained', c => fmtPct(c.retainedPct), { color: C.text, size: 10 });
    }

    // ─────── PAGE 3: WHERE EVERY DOLLAR GOES ───────
    if (breakdownBlocks && breakdownBlocks.length) {
      newPage();
      pageEyebrow('COST BREAKDOWN', 'Where every dollar of your annual brokerage cost goes.');
      doc.y += 6;

      breakdownBlocks.forEach((bk) => {
        // Estimate height: header (24) + rows (16 each) + totals (50) + footnote (24 if lpt)
        const estimated = 24 + (bk.rows.length * 18) + 60 + (bk.isLpt && bk.per_txn_brokerage_fee ? 30 : 0);
        ensureSpace(estimated + 16);

        // Card top border
        doc.strokeColor(bk.isLpt ? C.gold : C.border).lineWidth(0.6)
           .moveTo(PAGE.marginLeft, doc.y).lineTo(PAGE.width - PAGE.marginRight, doc.y).stroke();
        doc.y += 8;

        doc.fillColor(bk.isLpt ? C.gold : C.text).fontSize(13).text(
          bk.name + (bk.isCustom ? '  (Custom)' : ''),
          PAGE.marginLeft, doc.y, { lineBreak: false }
        );
        if (bk.plan_name) {
          const labelWidth = doc.widthOfString(bk.name + (bk.isCustom ? '  (Custom)' : '')) + 10;
          doc.fillColor(C.muted).fontSize(9).text(
            bk.plan_name, PAGE.marginLeft + labelWidth, doc.y + 2, { lineBreak: false }
          );
        }
        doc.y += 16;
        doc.fillColor(C.muted).fontSize(8).text(
          '@ ' + fmtMoneyShort(gci) + ' GCI  |  ' + (txns || 0) + ' txns',
          PAGE.marginLeft, doc.y, { lineBreak: false }
        );
        doc.y += 12;
        rule(C.borderSoft, 0.3);
        doc.y += 6;

        // Rows
        bk.rows.forEach((row) => {
          ensureSpace(22);
          const rY = doc.y;
          doc.fillColor(C.text).fontSize(9).text(row.label, PAGE.marginLeft, rY, {
            width: 180, lineBreak: false
          });
          if (row.sub) {
            doc.fillColor(C.dim).fontSize(7).text(row.sub, PAGE.marginLeft, rY + 11, {
              width: 280, lineBreak: false
            });
          }
          doc.fillColor(row.value > 0 ? C.text : C.dim).fontSize(10).text(
            fmtMoney(row.value),
            PAGE.marginLeft, rY,
            { width: CONTENT_WIDTH, align: 'right', lineBreak: false }
          );
          doc.y = rY + 22;
        });

        doc.y += 2;
        rule(C.border, 0.4);
        doc.y += 6;

        // Totals — lock y per pair so amount aligns with label
        ensureSpace(48);
        let tY = doc.y;
        doc.fillColor(C.muted).fontSize(9).text('Total brokerage cost', PAGE.marginLeft, tY + 4, { lineBreak: false });
        doc.fillColor(C.red).fontSize(13).text(fmtMoney(bk.total), PAGE.marginLeft, tY, {
          width: CONTENT_WIDTH, align: 'right', lineBreak: false
        });
        doc.y = tY + 18;
        tY = doc.y;
        doc.fillColor(C.muted).fontSize(9).text('Net to agent', PAGE.marginLeft, tY + 4, { lineBreak: false });
        doc.fillColor(C.green).fontSize(13).text(fmtMoney(bk.net), PAGE.marginLeft, tY, {
          width: CONTENT_WIDTH, align: 'right', lineBreak: false
        });
        doc.y = tY + 18;
        doc.fillColor(C.gold).fontSize(8).text(
          fmtPct(bk.retainedPct) + ' retained', PAGE.marginLeft, doc.y, { lineBreak: false }
        );
        doc.y += 14;

        // LPT pass-through footnote
        if (bk.isLpt && bk.per_txn_brokerage_fee) {
          ensureSpace(36);
          doc.fillColor(C.goldDim).fontSize(8).text(
            'Note: the $' + bk.per_txn_brokerage_fee + ' per-txn fee is typically passed through to the client at closing, so the agent\'s out-of-pocket is often lower than the total above. It is still counted here so the math matches apples-to-apples against other brokerages.',
            PAGE.marginLeft, doc.y, { width: CONTENT_WIDTH }
          );
          doc.y += 8;
        }

        doc.y += 14;
      });
    }

    // ─────── PAGE 4: WEDGE PANELS ───────
    const haveCapBe = capBreakeven && capBreakeven.length;
    const haveProj = projection && projection.length;
    const haveLptEq = lptEquityLadder && lptEquityLadder.awards && lptEquityLadder.awards.length;
    const haveHybrid = hybridshare && hybridshare.tiers && hybridshare.tiers.length;

    if (haveCapBe || haveProj || haveLptEq || haveHybrid) {
      newPage();
      pageEyebrow('THE BIGGER PICTURE', 'Cap break-even, 3-year retention projection, LPT equity, and revshare.');
      doc.y += 6;

      // Cap Break-Even
      if (haveCapBe) {
        sectionLabel('WHERE YOU STOP PAYING (CAP BREAK-EVEN)');
        capBreakeven.forEach((be) => {
          ensureSpace(42);
          const isLpt = be.isLpt;
          const rY = doc.y;
          doc.fillColor(isLpt ? C.gold : C.text).fontSize(10).text(
            (be.short_name || be.name) + (be.plan_name ? '  -  ' + be.plan_name : ''),
            PAGE.marginLeft, rY, { width: 240, lineBreak: false }
          );
          doc.fillColor(C.muted).fontSize(9).text(
            'Cap: ' + (be.cap ? fmtMoney(be.cap) : 'No cap'),
            PAGE.marginLeft + 240, rY, { width: 110, lineBreak: false }
          );
          doc.fillColor(C.text).fontSize(9).text(
            'Break-even: ' + be.breakEvenLabel,
            PAGE.marginLeft + 350, rY, { width: 90, lineBreak: false }
          );
          if (be.progressPct != null) {
            const pctColor = be.progressPct >= 100 ? C.green : (be.progressPct >= 80 ? C.gold : C.muted);
            doc.fillColor(pctColor).fontSize(9).text(
              be.progressPct.toFixed(0) + '%',
              PAGE.marginLeft + 440, rY, { width: 60, align: 'right', lineBreak: false }
            );
          }
          doc.y = rY + 14;
          if (be.breakEvenSub) {
            const sY = doc.y;
            doc.fillColor(C.dim).fontSize(7).text(
              be.breakEvenSub, PAGE.marginLeft + 350, sY, { width: 200, lineBreak: false }
            );
            doc.y = sY + 10;
          }
          // Progress bar
          if (be.progressPct != null) {
            const barX = PAGE.marginLeft;
            const barW = CONTENT_WIDTH;
            const fillW = Math.min(barW, barW * (be.progressPct / 100));
            doc.rect(barX, doc.y, barW, 4).fill(C.borderSoft);
            const fillColor = be.progressPct >= 100 ? C.green : (be.progressPct >= 80 ? C.gold : C.blue);
            doc.rect(barX, doc.y, fillW, 4).fill(fillColor);
            doc.y += 10;
          }
          doc.y += 4;
        });
        doc.y += 10;
      }

      // 3-Year Projection
      if (haveProj) {
        sectionLabel('3-YEAR PROJECTION  (' + (growthPct || 0) + '% YOY GROWTH)');
        const numCols = projection.length;
        const labelW2 = 90;
        const colW2 = Math.min(115, Math.floor((CONTENT_WIDTH - labelW2) / Math.max(numCols, 1)));

        // Header
        ensureSpace(20);
        let pY = doc.y;
        projection.forEach((p, i) => {
          const x = PAGE.marginLeft + labelW2 + i * colW2;
          doc.fillColor(p.isLpt ? C.gold : C.text).fontSize(9).text(
            p.short_name || p.name, x, pY, { width: colW2 - 6, lineBreak: false }
          );
        });
        doc.y = pY + 14;
        rule(C.border, 0.4);
        doc.y += 4;

        // Rows: Year 1, 2, 3
        for (let y = 1; y <= 3; y++) {
          ensureSpace(28);
          const rY2 = doc.y;
          doc.fillColor(C.muted).fontSize(8).text(
            'Year ' + y, PAGE.marginLeft, rY2 + 4, { width: labelW2, lineBreak: false }
          );
          projection.forEach((p, i) => {
            const row = p.rows[y - 1];
            if (!row) return;
            const x = PAGE.marginLeft + labelW2 + i * colW2;
            doc.fillColor(p.isLpt ? C.green : C.text).fontSize(11).text(
              fmtMoney(row.net), x, rY2, { width: colW2 - 6, lineBreak: false }
            );
            doc.fillColor(C.dim).fontSize(7).text(
              fmtMoneyShort(row.gci) + ' GCI / ' + row.txns + ' txns',
              x, rY2 + 13, { width: colW2 - 6, lineBreak: false }
            );
          });
          doc.y = rY2 + 24;
          rule(C.borderSoft, 0.2);
          doc.y += 2;
        }

        // Total row
        ensureSpace(22);
        const tY = doc.y;
        doc.fillColor(C.gold).fontSize(8).text('3-YEAR TOTAL', PAGE.marginLeft, tY + 4, {
          width: labelW2, characterSpacing: 1.2, lineBreak: false
        });
        projection.forEach((p, i) => {
          const x = PAGE.marginLeft + labelW2 + i * colW2;
          doc.fillColor(p.isLpt ? C.gold : C.text).fontSize(12).text(
            fmtMoney(p.total), x, tY, { width: colW2 - 6, lineBreak: false }
          );
        });
        doc.y = tY + 22;
        doc.y += 8;
      }

      // LPT Equity Ladder
      if (haveLptEq) {
        ensureSpace(60);
        sectionLabel('LPT EQUITY  -  SHARES EARNED BY UNIT COUNT');
        doc.fillColor(C.muted).fontSize(9).text(
          'Awards stack: hit Silver and you also earn White; hit Gold and you earn White + Silver + Gold; hit Black and you earn all four. 3-year vest. Private equity.',
          PAGE.marginLeft, doc.y, { width: CONTENT_WIDTH }
        );
        doc.y += 6;

        // Ladder grid
        const awards = lptEquityLadder.awards.slice().sort((a, b) => a.threshold - b.threshold);
        const rungW = Math.floor(CONTENT_WIDTH / awards.length);
        const ladderY = doc.y;
        const earnedBadges = (lptEquity && lptEquity.thisYear && lptEquity.thisYear.badges) || [];

        awards.forEach((a, i) => {
          const x = PAGE.marginLeft + i * rungW;
          const isEarned = earnedBadges.indexOf(a.badge) > -1;
          const cardY = ladderY;
          // Card border
          doc.strokeColor(isEarned ? C.gold : C.border).lineWidth(0.6)
             .rect(x + 2, cardY, rungW - 6, 64).stroke();
          if (isEarned) {
            doc.fillColor(C.gold).fontSize(8).text('EARNED', x + 8, cardY + 4, {
              width: rungW - 18, align: 'right', characterSpacing: 1.5, lineBreak: false
            });
          }
          doc.fillColor(isEarned ? C.gold : C.text).fontSize(13).text(
            a.badge, x + 8, cardY + 16, { width: rungW - 16, lineBreak: false }
          );
          doc.fillColor(C.muted).fontSize(7).text(
            a.threshold + '+ txns/yr', x + 8, cardY + 32, { width: rungW - 16, lineBreak: false }
          );
          doc.fillColor(C.text).fontSize(8).text(
            'BP: ' + (a.shares_bp != null ? a.shares_bp.toLocaleString() : '-'),
            x + 8, cardY + 44, { width: rungW - 16, lineBreak: false }
          );
          doc.fillColor(C.text).fontSize(8).text(
            'BB: ' + (a.shares_bb != null ? a.shares_bb.toLocaleString() : 'N/A'),
            x + 8, cardY + 54, { width: rungW - 16, lineBreak: false }
          );
        });
        doc.y = ladderY + 72;

        // Sponsorship + this-year + 3-year totals
        if (lptEquityLadder.sponsorship) {
          const sp = lptEquityLadder.sponsorship;
          ensureSpace(28);
          const sY = doc.y;
          doc.fillColor(C.muted).fontSize(8).text(
            '+ Sponsorship Performance Awards: ' + (sp.shares_bp != null ? sp.shares_bp.toLocaleString() : '?')
            + ' BP / ' + (sp.shares_bb != null ? sp.shares_bb.toLocaleString() : '?')
            + ' BB shares per direct sponsored agent\'s first Core Transaction.',
            PAGE.marginLeft, sY, { width: CONTENT_WIDTH }
          );
          doc.y = sY + 22;
        }
        if (lptEquity && lptEquity.thisYear) {
          ensureSpace(34);
          const sY = doc.y;
          doc.fillColor(C.text).fontSize(10).text(
            'This year (' + (txns || 0) + ' txns): ' + (lptEquity.thisYear.badges || []).join(' + '),
            PAGE.marginLeft, sY, { lineBreak: false }
          );
          doc.y = sY + 14;
          const vY = doc.y;
          doc.fillColor(C.gold).fontSize(13).text(
            '  ' + (lptEquity.thisYear.bp || 0).toLocaleString() + ' BP shares  |  '
              + (lptEquity.thisYear.bb || 0).toLocaleString() + ' BB shares',
            PAGE.marginLeft, vY, { lineBreak: false }
          );
          doc.y = vY + 20;
        }
        if (lptEquity && lptEquity.threeYear) {
          ensureSpace(34);
          const sY = doc.y;
          doc.fillColor(C.text).fontSize(10).text('3-year cumulative:', PAGE.marginLeft, sY, { lineBreak: false });
          doc.y = sY + 14;
          const vY = doc.y;
          doc.fillColor(C.gold).fontSize(13).text(
            '  ' + (lptEquity.threeYear.bp || 0).toLocaleString() + ' BP shares  |  '
              + (lptEquity.threeYear.bb || 0).toLocaleString() + ' BB shares',
            PAGE.marginLeft, vY, { lineBreak: false }
          );
          doc.y = vY + 20;
        }
        doc.y += 8;
      }

      // HybridShare 7-Tier
      if (haveHybrid) {
        ensureSpace(40);
        sectionLabel('THE 7-TIER REVENUE SHARE  (HYBRIDSHARE)');
        doc.fillColor(C.muted).fontSize(9).text(
          'Each LPT agent\'s capped company dollar funds the HybridShare Pool. A capped Brokerage Partner contributes $7,500 to the pool; a capped Business Builder contributes $2,500. An upline sponsor earns their tier percentage of that pool contribution.',
          PAGE.marginLeft, doc.y, { width: CONTENT_WIDTH }
        );
        doc.y += 28;

        const tCol = {
          tier: PAGE.marginLeft,
          pct: PAGE.marginLeft + 50,
          bp: PAGE.marginLeft + 130,
          bb: PAGE.marginLeft + 280,
          dir: PAGE.marginLeft + 430
        };
        ensureSpace(18);
        const hY = doc.y;
        doc.fillColor(C.muted).fontSize(8);
        doc.text('TIER', tCol.tier, hY, { characterSpacing: 1, lineBreak: false });
        doc.text('% OF POOL', tCol.pct, hY, { characterSpacing: 1, lineBreak: false });
        doc.text('MAX / BP DOWNLINE', tCol.bp, hY, { characterSpacing: 1, lineBreak: false });
        doc.text('MAX / BB DOWNLINE', tCol.bb, hY, { characterSpacing: 1, lineBreak: false });
        doc.text('MIN DIRECTS', tCol.dir, hY, { characterSpacing: 1, lineBreak: false });
        doc.y = hY + 12;
        rule(C.border, 0.4);
        doc.y += 4;

        hybridshare.tiers.forEach(t => {
          ensureSpace(18);
          const rY = doc.y;
          doc.fillColor(C.gold).fontSize(11).text('T' + t.tier, tCol.tier, rY, { lineBreak: false });
          doc.fillColor(C.text).fontSize(10).text(t.pct_of_pool + '%', tCol.pct, rY + 1, { lineBreak: false });
          doc.fillColor(C.text).fontSize(9).text(fmtMoney(t.max_bp) + '/yr', tCol.bp, rY + 2, { lineBreak: false });
          doc.fillColor(C.text).fontSize(9).text(fmtMoney(t.max_bb) + '/yr', tCol.bb, rY + 2, { lineBreak: false });
          doc.fillColor(C.text).fontSize(9).text(String(t.min_directs), tCol.dir, rY + 2, { lineBreak: false });
          doc.y = rY + 16;
          rule(C.borderSoft, 0.2);
          doc.y += 2;
        });
        doc.y += 6;
      }
    }

    // ─────── FOOTER ON EVERY PAGE ───────
    // Footer must stay above the bottom margin (PAGE.height - marginBottom = 736)
    // or pdfkit will auto-paginate each line onto its own page.
    const range = doc.bufferedPageRange();
    const footerLineY = PAGE.height - PAGE.marginBottom - 28;   // 708
    const footerTextY = footerLineY + 6;                        // 714
    const footerLinkY = footerLineY + 16;                       // 724

    for (let i = range.start; i < range.start + range.count; i++) {
      doc.switchToPage(i);
      doc.strokeColor(C.borderSoft).lineWidth(0.4)
         .moveTo(PAGE.marginLeft, footerLineY)
         .lineTo(PAGE.width - PAGE.marginRight, footerLineY).stroke();
      doc.fillColor(C.dim).fontSize(7).text(
        'TPL Collective  |  Source: official lpt.com flyer (valid 4/30/26) and publicly documented competitor data.',
        PAGE.marginLeft, footerTextY,
        { width: CONTENT_WIDTH - 70, lineBreak: false }
      );
      doc.fillColor(C.dim).fontSize(7).text(
        'Page ' + (i - range.start + 1) + ' of ' + range.count,
        PAGE.marginLeft, footerTextY,
        { width: CONTENT_WIDTH, align: 'right', lineBreak: false }
      );
      if (i === range.start && shareUrl) {
        doc.fillColor(C.gold).fontSize(7).text(
          'Interactive view: ' + shareUrl,
          PAGE.marginLeft, footerLinkY,
          { width: CONTENT_WIDTH, lineBreak: false, link: shareUrl, underline: false }
        );
      }
    }

    doc.end();
  });
}

#!/usr/bin/env python3
"""
Matchup page generator.

Reads data/brokerages.json and emits /vs/<slug>.html pages for every
published brokerage that does NOT already have a hand-crafted /vs/ page.

Pages reference only verified data (brokerages.json) — no fabrication.
All structural / benchmark comparisons link to /compare for live math.
"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data" / "brokerages.json"
VS_DIR = ROOT / "vs"
OUT_LOG = []

# Brokerages that already have hand-crafted pages — skip.
EXISTING_PAGES = {
    "berkshire-hathaway", "century-21", "coldwell-banker", "compass",
    "epique-realty", "exp-realty", "homesmart", "keller-williams",
    "real-brokerage", "remax",
}


def esc(s):
    if s is None:
        return ""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def money(n):
    if n is None:
        return "—"
    try:
        return "$" + format(int(round(float(n))), ",")
    except Exception:
        return "—"


def pct(n):
    if n is None or n == "":
        return "—"
    try:
        return f"{float(n):g}%"
    except Exception:
        return "—"


def plan_cell(plan):
    if not plan:
        return "—"
    parts = []
    if plan.get("split_structure"):
        parts.append(esc(plan["split_structure"]))
    if plan.get("annual_cap"):
        parts.append(f"Cap {money(plan['annual_cap'])}")
    if plan.get("per_txn_brokerage_fee"):
        parts.append(f"${plan['per_txn_brokerage_fee']}/txn")
    if plan.get("flat_fee_per_txn"):
        parts.append(f"${plan['flat_fee_per_txn']}/txn flat")
    return " · ".join(parts) if parts else "—"


def citations_block(b):
    cites = b.get("citations") or []
    if not cites:
        return ""
    items = "".join(f'<span class="cite">{esc(c)}</span>' for c in cites)
    return f'<div class="citations"><strong>Sources:</strong> {items}</div>'


def has_cap(plan):
    return bool(plan and plan.get("annual_cap"))


def breakeven_line(plan):
    """Plain-English break-even."""
    if not plan:
        return None
    cap = plan.get("annual_cap") or 0
    split = plan.get("split_structure") or ""
    m = re.match(r"(\d+)/(\d+)", split)
    if plan.get("flat_fee_per_txn") and cap:
        n = -(-cap // plan["flat_fee_per_txn"])  # ceil
        return f"{n} transactions to cap"
    if m and cap:
        brokerage_share = 1 - int(m.group(1)) / 100
        if brokerage_share <= 0:
            return None
        gci = cap / brokerage_share
        return f"{money(gci)} GCI to cap"
    return None


def build_page(lpt, competitor):
    """Emit HTML for /vs/<competitor-slug>.html"""
    slug = competitor["slug"]
    comp_name = competitor["name"]
    comp_short = competitor.get("short_name") or comp_name
    comp_logo = competitor.get("logo", "")
    category_label = (competitor.get("category") or "").capitalize()
    founded = competitor.get("founded")
    agent_count_note = competitor.get("agent_count_note") or ""
    source_url = competitor.get("source_url") or ""
    source_host = ""
    if source_url:
        try:
            from urllib.parse import urlparse
            source_host = urlparse(source_url).netloc.replace("www.", "")
        except Exception:
            source_host = source_url

    lpt_bp = next((p for p in lpt.get("plans", []) if "brokerage partner" in (p.get("plan_name") or "").lower()), None)
    lpt_bb = next((p for p in lpt.get("plans", []) if "business builder" in (p.get("plan_name") or "").lower()), None)
    comp_plan = (competitor.get("plans") or [None])[0]

    title = f"LPT Realty vs {comp_short} — Real Numbers Compared | TPL Collective"
    desc = f"Honest, data-backed comparison of LPT Realty vs {comp_name}. Splits, caps, fees, and total cost at your production. No pitch, just math."
    canonical = f"https://tplcollective.ai/vs/{slug}"

    lpt_bp_cell = plan_cell(lpt_bp)
    lpt_bb_cell = plan_cell(lpt_bb)
    comp_cell = plan_cell(comp_plan)
    lpt_bp_be = breakeven_line(lpt_bp) or "—"
    lpt_bb_be = breakeven_line(lpt_bb) or "—"
    comp_be = breakeven_line(comp_plan) or "—"

    monthly_fee = (comp_plan.get("monthly_fee") if comp_plan else None) or 0
    annual_fee = (comp_plan.get("annual_fee") if comp_plan else None) or 0
    royalty = (comp_plan.get("franchise_fee_pct") if comp_plan else None)
    royalty_cap = (comp_plan.get("franchise_fee_cap_annual") if comp_plan else None)
    per_txn = (comp_plan.get("per_txn_brokerage_fee") if comp_plan else None)

    revshare_label = "Yes" if (competitor.get("revshare") or {}).get("offered") else "No"
    equity_label = "Yes" if (competitor.get("equity") or {}).get("offered") else "No"

    verdict = build_verdict(lpt, competitor)

    compare_url = f"/compare?brokerages=lpt-realty,{slug}"

    faq = build_faq(lpt, competitor)

    jsonld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": desc,
        "author": {"@type": "Organization", "name": "TPL Collective"},
        "publisher": {"@type": "Organization", "name": "TPL Collective"},
        "mainEntityOfPage": canonical,
        "datePublished": "2026-04-24",
        "dateModified": "2026-04-24",
    }
    faq_jsonld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in faq
        ],
    }

    faq_html = "".join(
        f'<details class="faq-item"><summary>{esc(q)}</summary><p>{esc(a)}</p></details>'
        for q, a in faq
    )

    citations_html = citations_block(competitor)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<link rel="canonical" href="{canonical}"/>

<meta property="og:type" content="article"/>
<meta property="og:title" content="{esc(title)}"/>
<meta property="og:description" content="{esc(desc)}"/>
<meta property="og:url" content="{canonical}"/>
<meta property="og:image" content="https://tplcollective.ai/og/joining-lpt-realty.jpg"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{esc(title)}"/>
<meta name="twitter:description" content="{esc(desc)}"/>
<meta name="twitter:image" content="https://tplcollective.ai/og/joining-lpt-realty.jpg"/>

<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-X6WMCMBJ9R"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', 'G-X6WMCMBJ9R');
  gtag('config', 'AW-11351310286');
</script>
<!-- Meta Pixel Code -->
<script>
!function(f,b,e,v,n,t,s)
{{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '34463024060012400');
fbq('track', 'PageView');
</script>
<script src="/tpl-tracking.js" defer></script>

<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@300;400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet"/>
<style>
  :root {{ --bg:#0a0a0f; --surface:#13131a; --panel:#1a1a25; --border:rgba(255,255,255,0.08);
    --text:rgba(255,255,255,0.92); --muted:rgba(255,255,255,0.6); --dim:rgba(255,255,255,0.4);
    --accent:#6c63ff; --accent-hi:#8b84ff; --gold:#f0c040; --gold-br:rgba(240,192,64,0.3);
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--text); font-family:'DM Sans',sans-serif; -webkit-font-smoothing:antialiased; }}
  a {{ color:var(--accent-hi); }}
  nav {{ position:fixed; top:0; left:0; right:0; z-index:100; padding:18px 5%;
    display:flex; justify-content:space-between; align-items:center;
    background:rgba(10,10,15,0.9); backdrop-filter:blur(12px); border-bottom:1px solid var(--border); }}
  .nav-logo {{ font-family:'Bebas Neue',sans-serif; font-size:24px; letter-spacing:0.08em; color:#fff; text-decoration:none; }}
  .nav-logo span {{ color:var(--accent); }}
  .nav-links {{ display:flex; gap:26px; align-items:center; }}
  .nav-links a {{ color:var(--muted); text-decoration:none; font-size:13px; transition:color 0.2s; }}
  .nav-links a:hover {{ color:#fff; }}
  .nav-cta {{ background:var(--gold); color:#0a0a0f !important; padding:9px 18px; border-radius:6px; font-weight:600 !important; font-size:13px !important; }}
  .hamburger {{ display:none; background:none; border:none; cursor:pointer; flex-direction:column; gap:5px; width:28px; padding:0; }}
  .hamburger span {{ display:block; width:100%; height:2px; background:#fff; }}
  .mobile-menu {{ display:none; position:fixed; top:64px; left:0; right:0; background:var(--bg); padding:20px 5%; border-bottom:1px solid var(--border); z-index:99; }}
  .mobile-menu.open {{ display:flex; flex-direction:column; gap:14px; }}
  .mobile-menu a {{ color:#fff; text-decoration:none; font-size:15px; }}

  header.hero {{ padding:140px 5% 50px; max-width:980px; margin:0 auto; }}
  .eyebrow {{ font-family:'DM Mono',monospace; font-size:10px; letter-spacing:0.18em;
    text-transform:uppercase; color:var(--accent-hi); margin-bottom:14px; }}
  h1 {{ font-family:'Bebas Neue',sans-serif; font-size:64px; line-height:1.05;
    letter-spacing:0.02em; color:#fff; margin:0 0 18px; }}
  h1 em {{ font-style:normal; color:var(--gold); }}
  .hero-sub {{ font-size:17px; color:var(--muted); line-height:1.6; max-width:720px; margin:0 0 26px; }}
  .hero-meta {{ display:flex; gap:24px; flex-wrap:wrap; align-items:center; font-size:12px; color:var(--dim);
    font-family:'DM Mono',monospace; letter-spacing:0.06em; }}
  .hero-meta strong {{ color:var(--text); font-weight:500; }}

  .verdict {{ max-width:980px; margin:40px auto; padding:24px 28px;
    background:linear-gradient(145deg,rgba(108,99,255,0.08),var(--surface));
    border:1px solid rgba(108,99,255,0.3); border-radius:14px; }}
  .verdict h2 {{ font-family:'Bebas Neue',sans-serif; font-size:22px; margin:0 0 12px; letter-spacing:0.04em; color:#fff; }}
  .verdict p {{ font-size:15px; line-height:1.7; color:var(--muted); margin:0; }}

  main {{ max-width:980px; margin:0 auto; padding:40px 5% 80px; }}
  section {{ margin-bottom:56px; }}
  h2.section-title {{ font-family:'Bebas Neue',sans-serif; font-size:32px; letter-spacing:0.02em;
    color:#fff; margin:0 0 8px; }}
  .section-intro {{ color:var(--muted); font-size:15px; line-height:1.7; margin:0 0 22px; }}

  table.cmp-table {{ width:100%; border-collapse:collapse; background:var(--surface);
    border:1px solid var(--border); border-radius:10px; overflow:hidden; }}
  table.cmp-table th, table.cmp-table td {{ padding:16px 18px; text-align:left; border-bottom:1px solid var(--border); font-size:14px; }}
  table.cmp-table th {{ font-family:'DM Mono',monospace; font-size:10px; letter-spacing:0.14em;
    text-transform:uppercase; color:var(--dim); background:var(--panel); }}
  table.cmp-table td.row-label {{ font-family:'DM Mono',monospace; font-size:11px; letter-spacing:0.1em;
    text-transform:uppercase; color:var(--dim); white-space:nowrap; }}
  table.cmp-table td.lpt {{ background:rgba(240,192,64,0.04); }}
  table.cmp-table th.lpt {{ background:rgba(240,192,64,0.06); color:var(--gold); }}
  .cmp-wrap {{ overflow-x:auto; margin:0 -5%; padding:0 5%; }}

  .cta-row {{ display:flex; gap:14px; flex-wrap:wrap; margin:28px 0 10px; }}
  .btn-primary {{ padding:14px 28px; background:var(--gold); color:#0a0a0f !important;
    border-radius:8px; text-decoration:none; font-weight:600; font-size:14px;
    border:none; cursor:pointer; transition:transform 0.2s; }}
  .btn-primary:hover {{ transform:translateY(-1px); background:#ffd76a; }}
  .btn-secondary {{ padding:14px 28px; background:transparent; color:var(--text) !important;
    border:1px solid var(--border); border-radius:8px; text-decoration:none; font-weight:500;
    font-size:14px; transition:border-color 0.2s, color 0.2s; }}
  .btn-secondary:hover {{ border-color:var(--accent); color:var(--accent-hi) !important; }}

  .faq-item {{ border-bottom:1px solid var(--border); padding:18px 0; }}
  .faq-item summary {{ cursor:pointer; font-size:16px; font-weight:500; color:var(--text); list-style:none; }}
  .faq-item summary::-webkit-details-marker {{ display:none; }}
  .faq-item summary::before {{ content:"+ "; color:var(--accent-hi); font-weight:700; margin-right:4px; }}
  .faq-item[open] summary::before {{ content:"− "; }}
  .faq-item p {{ margin:14px 0 0; color:var(--muted); font-size:14px; line-height:1.7; }}

  .citations {{ margin-top:22px; padding:14px 18px; background:rgba(10,10,15,0.5);
    border:1px solid var(--border); border-radius:8px; }}
  .citations strong {{ font-family:'DM Mono',monospace; font-size:10px; letter-spacing:0.14em;
    text-transform:uppercase; color:var(--accent-hi); display:block; margin-bottom:8px; }}
  .cite {{ display:inline-block; padding:3px 8px; margin:3px 4px 3px 0;
    font-family:'DM Mono',monospace; font-size:10px; letter-spacing:0.06em;
    text-transform:uppercase; color:rgba(255,255,255,0.7);
    background:rgba(108,99,255,0.08); border:1px solid rgba(108,99,255,0.25); border-radius:3px; }}

  footer {{ padding:48px 5% 64px; border-top:1px solid var(--border); text-align:center; background:var(--bg); }}
  .footer-brand {{ font-family:'Bebas Neue',sans-serif; font-size:20px; letter-spacing:0.08em;
    color:#fff; margin-bottom:18px; }}
  .footer-links {{ display:flex; gap:24px; justify-content:center; flex-wrap:wrap; margin-bottom:20px; }}
  .footer-links a {{ color:var(--muted); font-size:12px; text-decoration:none;
    letter-spacing:0.05em; text-transform:uppercase; transition:color 0.2s; }}
  .footer-links a:hover {{ color:var(--accent-hi); }}
  .footer-copy {{ color:var(--dim); font-size:11px; letter-spacing:0.05em; }}

  @media (max-width:900px) {{
    .nav-links {{ display:none; }} .hamburger {{ display:flex; }}
    h1 {{ font-size:44px; }}
    .verdict {{ padding:22px; }}
  }}
</style>

<script type="application/ld+json">{json.dumps(jsonld)}</script>
<script type="application/ld+json">{json.dumps(faq_jsonld)}</script>
</head>
<body>

<nav>
  <a href="/" class="nav-logo">TPL<span>.</span></a>
  <div class="nav-links">
    <a href="/lpt-explained">LPT Explained</a>
    <a href="/why-tpl">Why TPL</a>
    <a href="/fee-plans">Fee Plans</a>
    <a href="/compare">Compare</a>
    <a href="/blog">Blog</a>
    <a href="https://calendly.com/discovertpl" target="_blank" class="nav-cta" onclick="gtag('event','calendly_click',{{'page_location':window.location.pathname}});fbq('track','Schedule',{{content_name:'Discovery Call'}})">Book a Call</a>
  </div>
  <button class="hamburger" id="hamburger" aria-label="Menu"><span></span><span></span><span></span></button>
</nav>
<div class="mobile-menu" id="mobileMenu">
  <a href="/lpt-explained">LPT Explained</a>
  <a href="/why-tpl">Why TPL</a>
  <a href="/fee-plans">Fee Plans</a>
  <a href="/compare">Compare</a>
  <a href="/blog">Blog</a>
  <a href="https://calendly.com/discovertpl" target="_blank" class="nav-cta">Book a Call</a>
</div>

<header class="hero">
  <div class="eyebrow">LPT Realty vs {esc(comp_short)}</div>
  <h1>LPT Realty vs {esc(comp_name)}<br><em>Real numbers. No pitch.</em></h1>
  <p class="hero-sub">If you're weighing {esc(comp_short)} against LPT Realty, this is the structural side-by-side — splits, caps, fees, and how each model behaves at your actual production. Numbers are pulled from published sources; use <a href="{compare_url}">our live comparator</a> to plug in your GCI and see total-cost impact.</p>
  <div class="hero-meta">
    {"<span><strong>Model:</strong> " + esc(category_label) + "</span>" if category_label else ""}
    {"<span><strong>Founded:</strong> " + esc(founded) + "</span>" if founded else ""}
    {"<span><strong>Source:</strong> <a href='" + esc(source_url) + "' target='_blank' rel='noopener'>" + esc(source_host) + "</a></span>" if source_url else ""}
  </div>
</header>

<section class="verdict">
  <h2>Bottom Line</h2>
  <p>{esc(verdict)}</p>
</section>

<main>

  <section>
    <h2 class="section-title">Structural Comparison</h2>
    <p class="section-intro">Each brokerage's primary plan, head-to-head. LPT shows both the Brokerage Partner (80/20 with cap) and Business Builder (flat fee per deal) plans so you can pick the one that fits your style.</p>
    <div class="cmp-wrap">
      <table class="cmp-table">
        <thead>
          <tr>
            <th>&nbsp;</th>
            <th class="lpt">LPT · Brokerage Partner</th>
            <th class="lpt">LPT · Business Builder</th>
            <th>{esc(comp_short)}</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="row-label">Plan structure</td>
            <td class="lpt">{esc(lpt_bp_cell)}</td>
            <td class="lpt">{esc(lpt_bb_cell)}</td>
            <td>{esc(comp_cell)}</td>
          </tr>
          <tr>
            <td class="row-label">Annual cap</td>
            <td class="lpt">{money(lpt_bp.get("annual_cap") if lpt_bp else None)}</td>
            <td class="lpt">{money(lpt_bb.get("annual_cap") if lpt_bb else None)}</td>
            <td>{money(comp_plan.get("annual_cap") if comp_plan else None)}</td>
          </tr>
          <tr>
            <td class="row-label">Per-txn brokerage fee</td>
            <td class="lpt">${lpt_bp.get("per_txn_brokerage_fee", "—") if lpt_bp else "—"} / txn</td>
            <td class="lpt">${lpt_bb.get("per_txn_brokerage_fee", "—") if lpt_bb else "—"} / txn</td>
            <td>{"$" + str(per_txn) + " / txn" if per_txn else "—"}</td>
          </tr>
          <tr>
            <td class="row-label">Monthly fee</td>
            <td class="lpt">{money(lpt_bp.get("monthly_fee", 0) * 12 if lpt_bp else None)}{" / yr" if lpt_bp else ""}</td>
            <td class="lpt">{money(lpt_bb.get("monthly_fee", 0) * 12 if lpt_bb else None)}{" / yr" if lpt_bb else ""}</td>
            <td>{money(monthly_fee * 12) if monthly_fee else "—"}{" / yr" if monthly_fee else ""}</td>
          </tr>
          <tr>
            <td class="row-label">Annual fee</td>
            <td class="lpt">{money(lpt_bp.get("annual_fee") if lpt_bp else None)}</td>
            <td class="lpt">{money(lpt_bb.get("annual_fee") if lpt_bb else None)}</td>
            <td>{money(annual_fee)}</td>
          </tr>
          <tr>
            <td class="row-label">Franchise royalty</td>
            <td class="lpt">0%</td>
            <td class="lpt">0%</td>
            <td>{pct(royalty)}{" (cap " + money(royalty_cap) + ")" if royalty_cap else ""}</td>
          </tr>
          <tr>
            <td class="row-label">Break-even to cap</td>
            <td class="lpt">{esc(lpt_bp_be)}</td>
            <td class="lpt">{esc(lpt_bb_be)}</td>
            <td>{esc(comp_be)}</td>
          </tr>
          <tr>
            <td class="row-label">Revenue share</td>
            <td class="lpt">HybridShare (7 tiers)</td>
            <td class="lpt">HybridShare (on upgrade)</td>
            <td>{esc(revshare_label)}</td>
          </tr>
          <tr>
            <td class="row-label">Stock / equity</td>
            <td class="lpt">—</td>
            <td class="lpt">—</td>
            <td>{esc(equity_label)}</td>
          </tr>
        </tbody>
      </table>
    </div>
    {citations_html}
    <div class="cta-row">
      <a href="{compare_url}" class="btn-primary">Run the Live Math at My Production &rarr;</a>
      <a href="https://calendly.com/discovertpl" class="btn-secondary" target="_blank" onclick="gtag('event','calendly_click',{{'page_location':window.location.pathname,cta_location:'vs_table'}});fbq('track','Schedule',{{content_name:'Discovery Call'}})">Talk to Joe (15 min)</a>
    </div>
  </section>

  <section>
    <h2 class="section-title">Who's a Better Fit?</h2>
    <p class="section-intro">Neither model is universally "better." The right call depends on your production, your brand needs, and what you want long-term.</p>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;">
      <div style="padding:22px;background:var(--surface);border:1px solid var(--border);border-radius:12px;">
        <div style="font-family:'DM Mono',monospace;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;color:var(--gold);margin-bottom:10px;">LPT Realty wins if</div>
        <ul style="margin:0;padding:0 0 0 20px;color:var(--muted);font-size:14px;line-height:1.7;">
          <li>You want a predictable, flat-fee ceiling instead of split erosion</li>
          <li>You care about revenue share with uncapped earning potential (HybridShare)</li>
          <li>You're comfortable working remote/cloud and don't need a physical office</li>
          <li>You want to keep close to 100% of commissions above the cap</li>
        </ul>
      </div>
      <div style="padding:22px;background:var(--surface);border:1px solid var(--border);border-radius:12px;">
        <div style="font-family:'DM Mono',monospace;font-size:10px;letter-spacing:0.14em;text-transform:uppercase;color:var(--accent-hi);margin-bottom:10px;">{esc(comp_short)} might fit if</div>
        <ul style="margin:0;padding:0 0 0 20px;color:var(--muted);font-size:14px;line-height:1.7;">
          {fit_bullets(competitor)}
        </ul>
      </div>
    </div>
  </section>

  <section>
    <h2 class="section-title">Frequently Asked</h2>
    {faq_html}
  </section>

  <section>
    <h2 class="section-title">See Your Own Numbers</h2>
    <p class="section-intro">Plug in your GCI, transaction count, and the two brokerages you're weighing. Our comparator computes the full-year brokerage cost including splits, caps, fees, franchise royalties, and per-transaction fees — no gate, no sales call required.</p>
    <div class="cta-row">
      <a href="{compare_url}" class="btn-primary">Open /compare with These Two &rarr;</a>
      <a href="/compare" class="btn-secondary">Compare All Brokerages</a>
    </div>
  </section>

</main>

<footer>
  <div class="footer-brand">TPL Collective</div>
  <div class="footer-links">
    <a href="/">Home</a>
    <a href="/lpt-explained">LPT Explained</a>
    <a href="/fee-plans">Fee Plans</a>
    <a href="/compare">Compare</a>
    <a href="/vs">All Comparisons</a>
    <a href="/blog">Blog</a>
  </div>
  <div class="footer-copy">&copy; 2026 TPL Collective &middot; Powered by LPT Realty</div>
</footer>

<script>
  document.getElementById('hamburger').addEventListener('click',()=>{{document.getElementById('mobileMenu').classList.toggle('open');}});
</script>
</body>
</html>
"""


def build_verdict(lpt, competitor):
    category = (competitor.get("category") or "").lower()
    comp_name = competitor.get("short_name") or competitor["name"]
    if category == "franchise":
        return (f"{comp_name} delivers a recognized brand and in-person office infrastructure, "
                f"but agents pay for it through higher splits, franchise royalty on every deal, and monthly or desk fees. "
                f"LPT Realty trades the brand halo for a $15K cap (Brokerage Partner plan) or a $500/deal flat fee "
                f"(Business Builder plan, capped at $5K), no franchise royalty, and a 7-tier revenue share pool. "
                f"If brand name on your sign is revenue-critical, {comp_name} makes sense. If you're confident your clients "
                f"hire you, not a logo, the math strongly favors LPT.")
    if category == "luxury":
        return (f"{comp_name} is a legitimate luxury brand with real pull on $5M+ listings — but you pay full franchise economics "
                f"even when the client hired you personally. LPT's flat cap model lets top producers keep materially more of "
                f"their commission once they clear the cap. If 90%+ of your business is true ultra-luxury, {comp_name} has utility. "
                f"For the agent doing occasional luxury along with conventional volume, LPT's math wins.")
    if category == "hybrid":
        return (f"{comp_name} operates on a flat-fee / monthly-fee model that works well for agents who want predictable overhead. "
                f"LPT's Business Builder plan is structurally similar (flat $500/deal, $5K cap), with the added benefit of optional "
                f"upgrade to HybridShare revenue sharing and a national brand. If you like predictable monthly bills, {comp_name} is viable; "
                f"if you want optionality and revenue share, LPT is the better long-term home.")
    if category == "cloud":
        return (f"{comp_name} and LPT are both cloud-first, no-office brokerages — so the comparison is about the specific cap, "
                f"per-transaction fees, and revenue share structure. Run the live math at your production to see the exact delta; "
                f"the two models behave very differently once you factor in per-deal fees and cap break-even points.")
    if category == "independent":
        return (f"{comp_name} is a strong regional independent with local market expertise. LPT is nationwide with a flat cap "
                f"and revenue share. The right choice depends on whether you value deep local ties or a scalable national model. "
                f"Run the live math at your production to see the cost delta.")
    return (f"This comparison highlights structural differences between {comp_name} and LPT Realty. Use /compare to plug in "
            f"your actual production and see the year-over-year cost impact.")


def fit_bullets(competitor):
    category = (competitor.get("category") or "").lower()
    name = competitor.get("short_name") or competitor["name"]
    if category == "franchise":
        return ("<li>You're early in your career and need structured training + an office to show up to</li>"
                "<li>Your local market values the brand name on the sign</li>"
                "<li>You prefer shared marketing dollars and legacy tools</li>")
    if category == "luxury":
        return ("<li>90%+ of your pipeline is genuine ultra-luxury ($5M+)</li>"
                "<li>Your buyers expect a white-glove brand experience</li>"
                "<li>You benefit from luxury-specific referral networks</li>")
    if category == "hybrid":
        return ("<li>You prefer a flat monthly fee with no per-deal upside cap</li>"
                "<li>You don't need revenue share or equity</li>"
                "<li>You want very predictable month-over-month overhead</li>")
    if category == "cloud":
        return ("<li>You're already sold on the cloud model and just comparing cap/fee structures</li>"
                "<li>The specific platform features matter more to you than economics</li>"
                "<li>You have a pre-existing team/downline tied to that brand</li>")
    if category == "independent":
        return (f"<li>You want a local, independent brand with regional reputation</li>"
                f"<li>You value direct access to ownership</li>"
                f"<li>{name} is already the strongest brand in your immediate market</li>")
    return "<li>Your specific situation favors their structure — use /compare to validate</li>"


def build_faq(lpt, competitor):
    name = competitor.get("short_name") or competitor["name"]
    return [
        (
            f"Is LPT actually cheaper than {name}?",
            f"At the per-transaction level, LPT's flat-fee structure (either $500/deal on Business Builder or 80/20 to a $15K cap on Brokerage Partner) typically results in lower total brokerage cost for agents clearing $75K+ in annual GCI. Use /compare to plug in your exact numbers — the delta varies by production level.",
        ),
        (
            f"Why would anyone stay at {name} if LPT's math is better?",
            f"Brand pull, office culture, pre-existing teams, and broker relationships are real switching costs. LPT wins on structural economics for most production profiles, but those soft factors are why the decision isn't automatic. Talk to Joe if you want a neutral read on whether switching is actually worth it for your situation.",
        ),
        (
            f"Does LPT work in my state?",
            f"LPT Realty is a nationwide brokerage licensed in all 50 states. Sponsorship process and commission plans are the same state-to-state.",
        ),
        (
            f"How fast can I switch from {name} to LPT?",
            f"Most switches take 5-10 business days once you've selected a sponsor and submitted the application. We walk you through the paperwork and MLS transfer during the discovery call.",
        ),
        (
            f"What's HybridShare — is it MLM?",
            f"HybridShare is a 7-tier revenue share program funded by 50% of each capped agent's company dollar ($7,500 for BP, $2,500 for BB). It's a residual income stream for agents who sponsor other agents — not a pyramid structure and not tied to recruiting-first behavior. You earn on their production, not on their enrollment.",
        ),
        (
            f"What if I'm already in contract on a listing — do I have to cancel?",
            f"No. Open listings and pending contracts stay with your current brokerage until they close. You switch your license for new business going forward. Joe can walk you through the transition plan on a discovery call.",
        ),
    ]


def main():
    with open(DATA) as f:
        data = json.load(f)
    brokerages = data["brokerages"]
    lpt = next(b for b in brokerages if b["slug"] == "lpt-realty")

    published = [b for b in brokerages if b.get("status") == "published"]
    generated = []
    skipped = []

    for b in published:
        slug = b["slug"]
        if slug == "lpt-realty":
            continue
        if slug in EXISTING_PAGES:
            skipped.append(slug)
            continue
        html = build_page(lpt, b)
        out_path = VS_DIR / f"{slug}.html"
        out_path.write_text(html, encoding="utf-8")
        generated.append(slug)
        OUT_LOG.append(f"  generated {out_path.relative_to(ROOT)}")

    print(f"Generated {len(generated)} pages:")
    for s in generated:
        print(f"  - vs/{s}.html")
    print(f"Skipped {len(skipped)} existing hand-crafted pages:")
    for s in skipped:
        print(f"  - vs/{s}.html")


if __name__ == "__main__":
    main()

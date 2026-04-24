#!/usr/bin/env python3
"""Generate 4 new SEO blog articles for TPL Collective using the canonical blog template."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BLOG = ROOT / "blog"

HEAD_CSS = """*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root { --bg:#0a0a0f; --bg2:#111118; --bg3:#16161f; --accent:#6c63ff; --accent-dim:rgba(108,99,255,0.12); --gold:#f0c040; --green:#34d399; --red:#f87171; --text:#e8e8f0; --muted:#888899; --border:rgba(108,99,255,0.2); --border-subtle:rgba(255,255,255,0.06); --font-display:'Bebas Neue',sans-serif; --font-body:'DM Sans',sans-serif; --font-mono:'DM Mono',monospace; }
body { background:var(--bg); color:var(--text); font-family:var(--font-body); line-height:1.7; }
nav { position:sticky; top:0; z-index:100; background:rgba(10,10,15,0.95); backdrop-filter:blur(12px); border-bottom:1px solid var(--border); padding:0 2rem; display:flex; align-items:center; justify-content:space-between; height:64px; }
.nav-logo { font-family:var(--font-display); font-size:1.6rem; letter-spacing:0.05em; color:var(--text); text-decoration:none; }
.nav-logo span { color:var(--accent); }
.nav-links { display:flex; align-items:center; gap:2rem; list-style:none; }
.nav-links a { color:var(--muted); text-decoration:none; font-size:0.9rem; font-weight:500; transition:color 0.2s; }
.nav-links a:hover { color:var(--text); }
.nav-cta { background:var(--accent); color:#fff !important; padding:0.45rem 1.1rem; border-radius:6px; font-weight:600 !important; }
.article-hero { padding:4rem 2rem 3rem; max-width:860px; margin:0 auto; text-align:center; }
.breadcrumb { font-family:var(--font-mono); font-size:0.72rem; letter-spacing:0.1em; color:var(--muted); text-transform:uppercase; margin-bottom:1.5rem; }
.breadcrumb a { color:var(--accent); text-decoration:none; }
.article-hero h1 { font-family:var(--font-display); font-size:clamp(2.4rem,5vw,3.8rem); letter-spacing:0.03em; line-height:1.05; margin-bottom:1.2rem; }
.article-hero .subtitle { font-size:1.1rem; color:var(--muted); max-width:600px; margin:0 auto 2rem; }
.article-meta { display:flex; align-items:center; justify-content:center; gap:1.5rem; font-family:var(--font-mono); font-size:0.75rem; letter-spacing:0.06em; color:var(--muted); flex-wrap:wrap; }
.verdict-banner { background:linear-gradient(135deg,rgba(108,99,255,0.15) 0%,rgba(108,99,255,0.05) 100%); border:1px solid var(--accent); border-radius:12px; padding:1.8rem 2rem; margin:2.5rem auto; max-width:860px; }
.verdict-banner .verdict-label { font-family:var(--font-mono); font-size:0.7rem; letter-spacing:0.15em; text-transform:uppercase; color:var(--accent); margin-bottom:0.6rem; }
.verdict-banner p { font-size:1.05rem; color:var(--text); line-height:1.6; }
.toc { background:var(--bg2); border:1px solid var(--border-subtle); border-radius:10px; padding:1.5rem; margin:2rem auto; max-width:860px; }
.toc-title { font-family:var(--font-mono); font-size:0.72rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--muted); margin-bottom:1rem; }
.toc ol { padding-left:1.2rem; display:grid; grid-template-columns:1fr 1fr; gap:0.3rem 1rem; }
.toc ol li { font-size:0.9rem; }
.toc ol li a { color:var(--accent); text-decoration:none; }
.toc ol li a:hover { text-decoration:underline; }
.article-body { max-width:860px; margin:0 auto; padding:0 2rem 4rem; }
.article-body h2 { font-family:var(--font-display); font-size:2rem; letter-spacing:0.04em; color:var(--text); margin:3rem 0 1rem; padding-top:1rem; }
.article-body h3 { font-size:1.15rem; font-weight:600; color:var(--text); margin:2rem 0 0.6rem; }
.article-body p { color:var(--text); margin-bottom:1.2rem; font-size:1rem; }
.article-body ul, .article-body ol { padding-left:1.4rem; margin-bottom:1.2rem; }
.article-body li { margin-bottom:0.4rem; font-size:0.97rem; }
.compare-table-wrap { overflow-x:auto; margin:1.5rem 0 2rem; border-radius:10px; border:1px solid var(--border); }
table { width:100%; border-collapse:collapse; font-size:0.9rem; }
thead tr { background:var(--bg3); }
thead th { padding:1rem 1.2rem; text-align:left; font-family:var(--font-mono); font-size:0.75rem; letter-spacing:0.1em; text-transform:uppercase; color:var(--muted); border-bottom:1px solid var(--border); }
thead th:nth-child(2) { color:var(--accent); }
tbody tr { border-bottom:1px solid var(--border-subtle); transition:background 0.15s; }
tbody tr:last-child { border-bottom:none; }
tbody tr:hover { background:rgba(255,255,255,0.02); }
tbody td { padding:0.85rem 1.2rem; vertical-align:top; }
tbody td:first-child { color:var(--muted); font-size:0.85rem; font-family:var(--font-mono); letter-spacing:0.04em; }
.win { color:var(--green); font-weight:600; }
.loss { color:var(--red); }
.win-badge { display:inline-block; background:rgba(52,211,153,0.12); color:var(--green); border:1px solid rgba(52,211,153,0.3); border-radius:4px; font-family:var(--font-mono); font-size:0.65rem; letter-spacing:0.1em; text-transform:uppercase; padding:0.15rem 0.5rem; margin-left:0.4rem; vertical-align:middle; }
.callout { border-radius:10px; padding:1.4rem 1.6rem; margin:1.8rem 0; }
.callout-insight { background:rgba(240,192,64,0.08); border-left:3px solid var(--gold); }
.callout-insight .callout-label { font-family:var(--font-mono); font-size:0.68rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--gold); margin-bottom:0.5rem; }
.callout-insight p { color:var(--text); margin:0; font-size:0.95rem; }
.callout-accent { background:var(--accent-dim); border-left:3px solid var(--accent); }
.callout-accent .callout-label { font-family:var(--font-mono); font-size:0.68rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--accent); margin-bottom:0.5rem; }
.callout-accent p { color:var(--text); margin:0; font-size:0.95rem; }
.cta-block { background:linear-gradient(135deg,rgba(108,99,255,0.18) 0%,rgba(108,99,255,0.06) 100%); border:1px solid var(--accent); border-radius:12px; padding:2.5rem 2rem; text-align:center; margin:3rem 0; }
.cta-block h3 { font-family:var(--font-display); font-size:1.8rem; letter-spacing:0.04em; margin-bottom:0.8rem; }
.cta-block p { color:var(--muted); max-width:480px; margin:0 auto 1.8rem; font-size:0.95rem; }
.cta-buttons { display:flex; gap:1rem; justify-content:center; flex-wrap:wrap; }
.btn-primary { background:var(--accent); color:#fff; padding:0.75rem 1.8rem; border-radius:8px; text-decoration:none; font-weight:600; font-size:0.95rem; transition:opacity 0.2s,transform 0.2s; display:inline-block; }
.btn-primary:hover { opacity:0.9; transform:translateY(-1px); }
.btn-secondary { background:transparent; color:var(--text); padding:0.75rem 1.8rem; border-radius:8px; text-decoration:none; font-weight:500; font-size:0.95rem; border:1px solid var(--border); transition:border-color 0.2s,transform 0.2s; display:inline-block; }
.btn-secondary:hover { border-color:var(--accent); transform:translateY(-1px); }
footer { border-top:1px solid var(--border); padding:2.5rem 2rem; text-align:center; color:var(--muted); font-size:0.85rem; }
footer a { color:var(--accent); text-decoration:none; }
@media (max-width:640px) { .nav-links{display:none;} .toc ol{grid-template-columns:1fr;} }"""

NAV = """<nav>
  <a href="/" class="nav-logo">TPL <span>Collective</span></a>
  <ul class="nav-links">
    <li><a href="/why-tpl">Why TPL</a></li>
    <li><a href="/lpt-explained">LPT Explained</a></li>
    <li><a href="/resources">Resources</a></li>
    <li><a href="/compare">Compare</a></li>
    <li><a href="/blog">Blog</a></li>
    <li><a href="https://calendly.com/discovertpl" target="_blank" class="nav-cta" onclick="gtag('event','calendly_click',{'page_location':window.location.pathname});fbq('track','Schedule',{content_name:'Discovery Call'})">Book a Call</a></li>
  </ul>
</nav>"""

FOOTER = """<footer>
  <p>&copy; 2026 TPL Collective &middot; <a href="/privacy-policy">Privacy</a> &middot; <a href="/blog">More Articles</a> &middot; <a href="/compare">Run the Comparator</a></p>
</footer>"""

CTA_BLOCK = """<div class="cta-block">
  <h3>Run the Math for Your Situation</h3>
  <p>Plug in your GCI, deal count, and the brokerages you're weighing. Our /compare tool does the total-cost math side by side.</p>
  <div class="cta-buttons">
    <a href="/compare" class="btn-primary">Open /compare</a>
    <a href="https://calendly.com/discovertpl" target="_blank" class="btn-secondary" onclick="gtag('event','calendly_click',{'page_location':window.location.pathname,cta_location:'blog_cta_block'});fbq('track','Schedule',{content_name:'Discovery Call'})">Talk to Joe (15 min)</a>
  </div>
</div>"""

TRACKING = """<script async src="https://www.googletagmanager.com/gtag/js?id=G-X6WMCMBJ9R"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-X6WMCMBJ9R');
  gtag('config', 'AW-11351310286');
</script>
<script>
!function(f,b,e,v,n,t,s)
{if(f.fbq)return;n=f.fbq=function(){n.callMethod?
n.callMethod.apply(n,arguments):n.queue.push(arguments)};
if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
n.queue=[];t=b.createElement(e);t.async=!0;
t.src=v;s=b.getElementsByTagName(e)[0];
s.parentNode.insertBefore(t,s)}(window, document,'script',
'https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '34463024060012400');
fbq('track', 'PageView');
</script>
<noscript><img height="1" width="1" style="display:none" src="https://www.facebook.com/tr?id=34463024060012400&ev=PageView&noscript=1"/></noscript>"""


def render(article):
    """article dict keys: slug, title, meta_desc, h1, subtitle, read_min, date, verdict, toc (list of (id,label)), body (raw HTML string)."""
    toc_html = "\n    ".join(f'<li><a href="#{i}">{l}</a></li>' for i, l in article["toc"])
    canonical = f"https://tplcollective.ai/blog/{article['slug']}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <script src="/tpl-tracking.js" defer></script>
  <link rel="canonical" href="{canonical}"/>
  <title>{article['title']}</title>
  <meta name="description" content="{article['meta_desc']}" />
  <meta property="og:title" content="{article['title']}" />
  <meta property="og:description" content="{article['meta_desc']}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="{canonical}" />
  <meta name="twitter:card" content="summary_large_image"/>
  <meta name="twitter:title" content="{article['title']}"/>
  <meta name="twitter:description" content="{article['meta_desc']}"/>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:ital,wght@0,400;0,500;0,600;1,400&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet" />
{TRACKING}
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "{article['h1']}",
    "description": "{article['meta_desc']}",
    "author": {{ "@type": "Organization", "name": "TPL Collective" }},
    "publisher": {{ "@type": "Organization", "name": "TPL Collective", "url": "https://tplcollective.ai" }},
    "datePublished": "{article['date']}",
    "dateModified": "{article['date']}"
  }}
  </script>
  <style>{HEAD_CSS}</style>
</head>
<body>

{NAV}

<div class="article-hero">
  <p class="breadcrumb"><a href="/blog">Blog</a> &nbsp;/&nbsp; {article['category']}</p>
  <h1>{article['h1']}</h1>
  <p class="subtitle">{article['subtitle']}</p>
  <div class="article-meta">
    <span>{article['date_display']}</span>
    <span>{article['read_min']} min read</span>
    <span>TPL Collective</span>
  </div>
</div>

<div class="verdict-banner">
  <p class="verdict-label">Quick Verdict</p>
  <p>{article['verdict']}</p>
</div>

<div class="toc">
  <p class="toc-title">Table of Contents</p>
  <ol>
    {toc_html}
  </ol>
</div>

<div class="article-body">
{article['body']}

{CTA_BLOCK}

</div>

{FOOTER}

</body>
</html>
"""


ARTICLES = [
    {
        "slug": "cap-break-even-explained",
        "title": "Cap Break-Even Explained: When Your Brokerage Actually Pays You 100% | TPL Collective",
        "meta_desc": "How cap break-even works, why it's the number that actually matters, and how LPT's $5K/$15K caps compare to KW ($20-35K), eXp ($16K), and Compass (often none).",
        "h1": "Cap Break-Even Explained: When Your Brokerage Actually Pays You 100%",
        "subtitle": "Your cap is a ceiling. Break-even is when you hit it. The gap between those two numbers is where your real take-home lives.",
        "date": "2026-04-24",
        "date_display": "April 2026",
        "read_min": 7,
        "category": "Agent Guides",
        "verdict": "Break-even is the GCI (or deal count) where you've paid your full brokerage cap. LPT's Brokerage Partner caps at $15K, hitting break-even at $75K GCI. Business Builder caps at $5K after 10 deals. KW's cap ranges $20K-$35K depending on market center - a much higher bar before you keep 100%.",
        "toc": [
            ("what-is-break-even", "What Is Cap Break-Even?"),
            ("two-structures", "Split Caps vs Flat-Fee Caps"),
            ("the-math", "The Math: Two Worked Examples"),
            ("brokerage-comparison", "Break-Even by Brokerage"),
            ("why-matters", "Why Break-Even Matters More Than the Cap"),
            ("lpt-numbers", "LPT's Two Break-Even Points"),
            ("faq", "Frequently Asked Questions"),
        ],
        "body": """<h2 id="what-is-break-even">What Is Cap Break-Even?</h2>
<p>"Cap break-even" is the GCI (or deal count) where you've paid your brokerage its full annual cap. After that point, every additional dollar of commission (minus any per-transaction fees) stays in your pocket.</p>
<p>Most agents fixate on the cap number itself: "LPT caps at $15K, eXp caps at $16K, sounds close." But the cap is only half of the picture. The real question is: how much business do I have to close before I hit that ceiling? That's break-even.</p>

<div class="callout callout-insight">
  <p class="callout-label">Key insight</p>
  <p>A $10K cap that you never hit is worse than a $15K cap that you hit by Q3. Break-even determines how many months of the year you actually benefit from the cap.</p>
</div>

<h2 id="two-structures">Split Caps vs Flat-Fee Caps</h2>
<p>There are two break-even formulas depending on the plan structure:</p>
<h3>Split-based plans (80/20, 85/15, 70/30, etc.)</h3>
<p>Break-even GCI = Cap / Split percentage.</p>
<p>Example: LPT's Brokerage Partner is 80/20 with a $15,000 cap. $15,000 / 0.20 = $75,000 GCI to break even. Every dollar after that $75K clears your pocket net of per-txn fees.</p>
<h3>Flat-fee-per-transaction plans</h3>
<p>Break-even = Cap / Flat fee.</p>
<p>Example: LPT's Business Builder is $500/deal with a $5,000 cap. $5,000 / $500 = 10 deals to break even. Deal 11 and beyond, you only pay the $195 per-txn fee (not the $500 flat).</p>

<h2 id="the-math">The Math: Two Worked Examples</h2>
<h3>Agent A: $90K GCI on 12 deals (BP plan)</h3>
<ul>
  <li>First $75K of GCI: 80/20 split = $15K to brokerage (cap hit)</li>
  <li>Last $15K: keeps 100% minus per-txn fees</li>
  <li>Per-txn fees: 12 deals x $195 = $2,340</li>
  <li>Annual fee: $500</li>
  <li>Net to agent: $90K - $15K - $2,340 - $500 = <span class="win">$72,160</span></li>
</ul>
<h3>Agent B: $60K GCI on 12 deals (BB plan)</h3>
<ul>
  <li>First 10 deals: $500 x 10 = $5,000 (cap hit)</li>
  <li>Last 2 deals: $500 flat waived, $195 per-txn still applies</li>
  <li>Per-txn fees: 12 x $195 = $2,340</li>
  <li>Annual fee: $500</li>
  <li>Net to agent: $60K - $5K - $2,340 - $500 = <span class="win">$52,160</span></li>
</ul>

<h2 id="brokerage-comparison">Break-Even by Brokerage</h2>
<p>Every major brokerage expressed in one comparable metric: how much production to hit cap?</p>

<div class="compare-table-wrap">
  <table>
    <thead><tr><th>Brokerage</th><th>Cap</th><th>Break-Even Point</th><th>Notes</th></tr></thead>
    <tbody>
      <tr><td>LPT Business Builder</td><td><span class="win">$5,000</span></td><td><span class="win">10 transactions</span></td><td>Flat $500/deal</td></tr>
      <tr><td>LPT Brokerage Partner</td><td><span class="win">$15,000</span></td><td><span class="win">$75,000 GCI</span></td><td>80/20 split, HybridShare eligible</td></tr>
      <tr><td>REAL Brokerage</td><td>$12,000</td><td>$80,000 GCI</td><td>85/15 split [VERIFY]</td></tr>
      <tr><td>eXp Realty</td><td class="loss">$16,000</td><td class="loss">$80,000 GCI</td><td>80/20 split + $85/mo tech fee [VERIFY]</td></tr>
      <tr><td>Keller Williams</td><td class="loss">$20K-$35K</td><td class="loss">~$100K-$175K GCI</td><td>Varies by market center [VERIFY]</td></tr>
      <tr><td>Fathom Realty</td><td>$9,000</td><td>20 transactions</td><td>$465/txn flat [VERIFY]</td></tr>
      <tr><td>RE/MAX</td><td class="loss">Effectively none</td><td class="loss">Never fully</td><td>Desk fees continue regardless</td></tr>
      <tr><td>Compass</td><td class="loss">Often none</td><td class="loss">Never</td><td>Varies per agent [VERIFY]</td></tr>
    </tbody>
  </table>
</div>

<h2 id="why-matters">Why Break-Even Matters More Than the Cap</h2>
<p>Two reasons:</p>
<ol>
  <li><strong>It tells you how soon the cap kicks in.</strong> An agent doing $150K GCI at LPT BP hits break-even by deal 10 (around July for most agents) and spends the second half of the year at 100%. Same agent at a brokerage with a $25K cap hits break-even in October and barely sees 100% commission before the year resets.</li>
  <li><strong>It normalizes for split structure.</strong> Comparing "$15K cap vs $20K cap" is misleading without knowing the split. A $20K cap at 70/30 actually means $66K GCI to break even - not that different from LPT BP. But if the $20K cap is at 80/20, now it's $100K GCI. Always do the division.</li>
</ol>

<div class="callout callout-accent">
  <p class="callout-label">Pro tip</p>
  <p>If a brokerage markets their "low monthly fee" but has no cap or a very high break-even, you're being sold the entry price, not the total cost. Run the full-year math before signing.</p>
</div>

<h2 id="lpt-numbers">LPT's Two Break-Even Points</h2>
<p>LPT is unusual in that it offers two entirely different plan structures, each with its own break-even logic:</p>
<ul>
  <li><strong>Brokerage Partner:</strong> $75K GCI to break even. Targeted at producing agents who want revenue share (HybridShare) and the structural benefits of a higher cap plus uncapped post-cap economics.</li>
  <li><strong>Business Builder:</strong> 10 transactions to break even. Targeted at volume producers where flat-fee-per-deal beats any percentage split, and the $5K cap is the lowest in the industry by a wide margin.</li>
</ul>
<p>Most agents will see that one plan clearly fits their production profile. The /compare tool lets you toggle both and see the exact delta at your numbers.</p>

<h2 id="faq">Frequently Asked Questions</h2>
<h3>Does the cap include per-transaction fees?</h3>
<p>No. Cap refers specifically to the split-based or flat-fee portion going to the brokerage. Per-txn fees (like LPT's $195/txn), annual fees ($500), and any optional add-ons are separate line items that continue after cap.</p>
<h3>If I'm at 80% of my cap, should I delay a deal?</h3>
<p>Almost never. The next deal moves you closer to break-even, and any deals after break-even are dramatically more profitable. Closing faster compresses your timeline to 100% commission.</p>
<h3>Does break-even reset every calendar year?</h3>
<p>At LPT, caps reset on your anniversary date (the month you joined), not January 1. This matters if you join mid-year - your first cap year runs 12 full months.</p>
<h3>What if I don't hit my cap?</h3>
<p>You pay the full split/flat rate on every deal you do close. That's why break-even matters most for mid-to-high producers. For agents at 4-8 deals a year, the BB flat-fee plan gives better economics than any split plan regardless of break-even timing.</p>"""
    },
    {
        "slug": "switching-brokerages-risk-checklist",
        "title": "Switching Brokerages: The Risk Checklist Most Agents Skip | TPL Collective",
        "meta_desc": "Switching brokerages isn't just paperwork. Pending deals, referral obligations, MLS, splits, and sponsor selection. The 12-item risk checklist before you sign.",
        "h1": "Switching Brokerages: The Risk Checklist Most Agents Skip",
        "subtitle": "Most switches go smoothly. The ones that don't usually trip on the same 3 or 4 items - all of them fixable if you catch them before signing.",
        "date": "2026-04-24",
        "date_display": "April 2026",
        "read_min": 8,
        "category": "Agent Guides",
        "verdict": "The biggest risks aren't about which brokerage you pick - they're about what you forget to close out at your current one. Pending deals, referral splits, MLS transitions, and sponsor due diligence are where most agents lose money or momentum during a switch.",
        "toc": [
            ("why-risk", "Why Switching Has Hidden Risk"),
            ("pending-deals", "Risk 1: Open and Pending Deals"),
            ("referrals", "Risk 2: Referral Obligations"),
            ("mls", "Risk 3: MLS and Board Transitions"),
            ("sponsor", "Risk 4: Picking the Wrong Sponsor"),
            ("tech", "Risk 5: CRM and Tech Stack"),
            ("checklist", "The 12-Item Pre-Switch Checklist"),
            ("timing", "When to Switch (and When to Wait)"),
        ],
        "body": """<h2 id="why-risk">Why Switching Has Hidden Risk</h2>
<p>Every year thousands of agents switch brokerages. Most switches go smoothly. But a meaningful minority run into preventable problems - pending deals that get stuck, referral agreements that get misfiled, or a sponsor relationship that dies six months in because the economics weren't what was pitched.</p>
<p>This article is the checklist we walk every incoming TPL agent through before they sign. It's not a pitch for LPT - it's the operational due diligence that applies regardless of which brokerage you're moving to.</p>

<h2 id="pending-deals">Risk 1: Open and Pending Deals</h2>
<p>Any listing or pending contract you have at your current brokerage stays there until it closes. Your new brokerage can't take a commission on business your old brokerage originated.</p>
<p>Before you switch, inventory:</p>
<ul>
  <li>Every open listing (date listed, expected close, exclusive expiration)</li>
  <li>Every pending contract (closing date, contingency status)</li>
  <li>Every active showing or offer not yet in contract</li>
</ul>
<p>Decide case-by-case: close it out at your current brokerage, or have your current broker release it so you can bring it with you. Most brokerages will release pending deals for a transfer fee; getting that in writing matters.</p>

<div class="callout callout-insight">
  <p class="callout-label">Common mistake</p>
  <p>Agents assume their current broker will automatically release pending deals. They won't - you have to ask, and they may push back or charge a fee. Handle this in writing before you submit your resignation.</p>
</div>

<h2 id="referrals">Risk 2: Referral Obligations</h2>
<p>If you've sent or received referrals, there are usually written agreements attached. A switch can complicate enforcement.</p>
<p>Check your referral pipeline:</p>
<ul>
  <li>Outbound referrals (deals you sent to other agents, waiting on commission when they close)</li>
  <li>Inbound referrals (deals where you owe a % to the referring agent)</li>
  <li>Any referral agreements tied to your current brokerage's commission-advance system</li>
</ul>
<p>Best practice: collect written confirmation from every active referral partner that the agreement follows you to your new brokerage. If your current brokerage administered the referral (held the payments), confirm how they'll disburse.</p>

<h2 id="mls">Risk 3: MLS and Board Transitions</h2>
<p>Your MLS access, lockbox credentials, board dues, and Realtor affiliation are separate from your brokerage. But most require a new activation when you change brokerages.</p>
<p>Timeline-sensitive items:</p>
<ul>
  <li>MLS access may go dark for 1-3 business days during the transition</li>
  <li>Lockbox credentials typically reissue after your new brokerage is on file</li>
  <li>Some local boards charge a transfer fee ($50-$300)</li>
  <li>If you pay annual dues in January, you likely don't need to re-pay - but confirm</li>
</ul>
<p>Plan your switch so the MLS dark window doesn't land on a critical showing day. Friday-to-Sunday transitions are usually safest.</p>

<h2 id="sponsor">Risk 4: Picking the Wrong Sponsor</h2>
<p>At cloud/hybrid brokerages (LPT, eXp, REAL, Fathom), your sponsor affects both your onboarding experience and your revenue share upline. A sponsor you'll never talk to is a bad sponsor. A sponsor who's only interested in downline size is worse.</p>
<p>Questions to ask any potential sponsor:</p>
<ul>
  <li>Are you actually producing, or only recruiting?</li>
  <li>How often are you available for structural questions (transaction issues, contract clauses, tool setup)?</li>
  <li>Do you run a team with a pipeline I can plug into, or am I fully independent?</li>
  <li>What's your actual experience with the brokerage's tools and processes?</li>
</ul>
<p>A good sponsor is someone who helps you make more money - not someone who collects residuals on your production without adding value.</p>

<h2 id="tech">Risk 5: CRM and Tech Stack</h2>
<p>Data portability is rarely smooth. Your CRM contacts, call logs, transaction history, email templates, and lead-source tracking may or may not migrate cleanly.</p>
<p>Before you switch:</p>
<ul>
  <li>Export every contact record (CSV or compatible format) and back it up locally</li>
  <li>Export transaction history if your current brokerage's system supports it</li>
  <li>Screenshot or save your pipeline view - reconstructing it from scratch is painful</li>
  <li>List every tool subscription currently paid through the brokerage (signing, CRM, IDX)</li>
</ul>
<p>LPT uses Lofty CRM and Dotloop - standard industry tools that most agents can migrate into cleanly. Other brokerages use proprietary systems you may lose access to the day you leave.</p>

<h2 id="checklist">The 12-Item Pre-Switch Checklist</h2>
<ol>
  <li>Written release or transfer plan for every open/pending deal</li>
  <li>Written confirmation of every active referral agreement</li>
  <li>Inventory of MLS, lockbox, and board transition steps with timing</li>
  <li>Sponsor conversation completed (2-3 options vetted, not just 1)</li>
  <li>CRM and contact database exported and backed up</li>
  <li>Tool subscription audit (what the brokerage provides vs what you pay for)</li>
  <li>Commission plan selected (split plan vs flat plan, based on your production)</li>
  <li>Cap math run at your actual GCI and deal count (use /compare)</li>
  <li>Anniversary date understood (when does your cap year start?)</li>
  <li>Transfer fee and any exit costs from current brokerage documented</li>
  <li>Clear first 30 days plan: who signs the paperwork, what closes this month, when the new license is active</li>
  <li>Communication plan for existing clients (brief, professional, non-dramatic)</li>
</ol>

<div class="callout callout-accent">
  <p class="callout-label">Rule of thumb</p>
  <p>If your switch timeline is shorter than 10 business days end-to-end, you're probably skipping one of these items. 2-3 weeks is the realistic minimum for a clean move with pending deals in motion.</p>
</div>

<h2 id="timing">When to Switch (and When to Wait)</h2>
<h3>Switch now if:</h3>
<ul>
  <li>You have 0-2 pending deals that will close in the next 30 days</li>
  <li>Your current brokerage's economics are visibly worse than alternatives at your production level</li>
  <li>You've already vetted a sponsor relationship</li>
  <li>Your MLS and board transitions are straightforward (no multi-state complications)</li>
</ul>
<h3>Wait if:</h3>
<ul>
  <li>You have a listing set to go on market in the next 2 weeks</li>
  <li>You're inside 30 days of your anniversary date - hitting a cap reset twice in one year wastes cap progress</li>
  <li>You haven't run the total-cost math (don't switch on vibes)</li>
  <li>You don't have a sponsor picked (bad sponsor is worse than wrong brokerage)</li>
</ul>
<p>Switching is not a one-way door - you can always move again. But doing it cleanly the first time protects your income during the transition, and that window is often when agents can least afford disruption.</p>"""
    },
    {
        "slug": "fl-top-5-brokerages",
        "title": "Florida Top 5 Brokerages for Agents in 2026: Honest Comparison | TPL Collective",
        "meta_desc": "The 5 brokerages Florida agents actually compare in 2026: LPT, eXp, Compass, Keller Williams, and LoKation. Real splits, real caps, real market fit.",
        "h1": "Florida Top 5 Brokerages for Agents in 2026: Honest Comparison",
        "subtitle": "Not the biggest. The 5 every Florida agent actually shortlists when switching - by market presence, model, and agent economics.",
        "date": "2026-04-24",
        "date_display": "April 2026",
        "read_min": 7,
        "category": "Agent Guides",
        "verdict": "Florida's agent market is fragmented: national cloud brokerages (LPT, eXp), national franchise (KW), national luxury (Compass), and strong regional players (LoKation). The right answer depends on your production profile, whether you need office space, and how you value revenue share. Here's the honest side-by-side.",
        "toc": [
            ("why-five", "Why These Five"),
            ("lpt", "1. LPT Realty"),
            ("exp", "2. eXp Realty"),
            ("kw", "3. Keller Williams"),
            ("compass", "4. Compass"),
            ("lokation", "5. LoKation Real Estate"),
            ("decision", "How to Pick Between Them"),
        ],
        "body": """<h2 id="why-five">Why These Five</h2>
<p>Florida has dozens of brokerages with real market presence. We narrowed to five because these are the brokerages we see Florida agents actually shortlist when they start comparing - either because they're already there, or because they've been recruited heavily.</p>
<p>This list isn't ordered by preference. It's ordered by the comparison flow most agents work through: cloud-first alternatives, then the franchise incumbent, then luxury, then regional.</p>

<h2 id="lpt">1. LPT Realty</h2>
<p><strong>Model:</strong> Cloud, two plans (Brokerage Partner and Business Builder).</p>
<p><strong>BP plan:</strong> 80/20 split, $15K cap, $195/txn, $500/yr. Break-even: $75K GCI.</p>
<p><strong>BB plan:</strong> $500 flat per deal, $5K cap (10 deals), $195/txn, $500/yr. Break-even: 10 transactions.</p>
<p><strong>Florida fit:</strong> Strong. Florida is one of LPT's largest markets, sponsor network is dense, and the flat-fee BB plan is especially attractive for high-volume coastal and suburban agents.</p>
<p><strong>Unique features:</strong> HybridShare revenue share (7 tiers, 50% of company dollar), no monthly fee on either plan, Lofty CRM included.</p>
<p><strong>Best for:</strong> Producing agents who want predictable ceiling economics and optional revenue share. Agents who want to build a team have a clean path via BP + HybridShare.</p>
<p><a href="/vs/exp-realty">LPT vs eXp</a> | <a href="/vs/keller-williams">LPT vs KW</a> | <a href="/compare?brokerages=lpt-realty">Run your numbers</a></p>

<h2 id="exp">2. eXp Realty</h2>
<p><strong>Model:</strong> Cloud, single plan.</p>
<p><strong>Structure:</strong> 80/20 split, $16K cap, ~$85/month tech fee. [VERIFY]</p>
<p><strong>Florida fit:</strong> Strong national presence, though growth has plateaued in recent years (8 quarters of agent decline per public filings).</p>
<p><strong>Unique features:</strong> Revenue share program (7 tiers), stock award opportunities, large Facebook-based training ecosystem.</p>
<p><strong>Best for:</strong> Agents who want a well-established cloud brokerage with extensive revenue share lineage. If you already have a downline pipeline, that matters.</p>
<p><strong>vs LPT:</strong> Higher cap ($16K vs $15K), ongoing monthly tech fee, larger established brand. LPT's BB flat-fee plan has no equivalent at eXp for high-volume agents. <a href="/vs/exp-realty">Full comparison</a>.</p>

<h2 id="kw">3. Keller Williams</h2>
<p><strong>Model:</strong> Franchise, office-based, per-market-center economics.</p>
<p><strong>Structure:</strong> 70/30 split, cap varies $20K-$35K by market center, 6% royalty on top. [VERIFY]</p>
<p><strong>Florida fit:</strong> Huge footprint, most Florida markets have multiple KW offices. Training programs (Ignite, BOLD) are well-regarded industry-wide.</p>
<p><strong>Unique features:</strong> Profit share program, Command CRM platform, office-based team culture.</p>
<p><strong>Best for:</strong> New licensees who benefit from office structure and hands-on training, or agents who value the existing KW network and don't mind the higher total cost.</p>
<p><strong>vs LPT:</strong> Much higher cap break-even ($100K-$175K GCI depending on market center), monthly market center fees, franchise royalty on top of split. Most producing agents save $15K+/year switching to LPT. <a href="/vs/keller-williams">Full comparison</a>.</p>

<h2 id="compass">4. Compass</h2>
<p><strong>Model:</strong> National luxury with tech platform.</p>
<p><strong>Structure:</strong> 70/30 to 90/10 splits negotiated per agent, platform fees, often no annual cap. [VERIFY]</p>
<p><strong>Florida fit:</strong> Concentrated in luxury markets (Miami, Palm Beach, Naples, Sarasota). Less relevant outside those zones.</p>
<p><strong>Unique features:</strong> In-house tech platform, Compass Concierge for listing prep, strong brand in HNW segments.</p>
<p><strong>Best for:</strong> Luxury-focused agents whose transactions justify the brand premium, particularly in established Compass markets.</p>
<p><strong>vs LPT:</strong> Strong brand in HNW circles but total cost runs $25K+/year higher for most producing agents. No revenue share. <a href="/vs/compass">Full comparison</a>.</p>

<h2 id="lokation">5. LoKation Real Estate</h2>
<p><strong>Model:</strong> Regional (FL/NC/SC) flat-fee independent.</p>
<p><strong>Structure:</strong> Monthly fee model, varies by plan. [VERIFY]</p>
<p><strong>Florida fit:</strong> Dominant regional presence in Florida with office support in multiple counties.</p>
<p><strong>Unique features:</strong> Office space available, in-person support, independent (not franchised), Florida-focused broker relationships.</p>
<p><strong>Best for:</strong> Agents who want a local independent with office infrastructure and don't mind regional scope (no expansion outside FL/NC/SC).</p>
<p><strong>vs LPT:</strong> LPT is nationwide, LoKation is regional. LPT offers revenue share; LoKation does not. Economics vary by exact plan structure; run the math in /compare. <a href="/vs/lokation">Full comparison</a>.</p>

<h2 id="decision">How to Pick Between Them</h2>
<p>A rough decision tree based on the questions that actually matter:</p>
<ul>
  <li><strong>Do you need physical office space?</strong> Yes - LoKation or KW. No - LPT or eXp.</li>
  <li><strong>Are you in a luxury market with $1M+ average sale?</strong> Consider Compass. Otherwise skip it.</li>
  <li><strong>Do you want revenue share as a long-term income stream?</strong> LPT or eXp.</li>
  <li><strong>Is this your first year in the business?</strong> KW offices still provide the most structured new-agent training. If you have a strong sponsor lined up at LPT or eXp, the cloud path also works.</li>
  <li><strong>Are you doing 15+ deals/year?</strong> Flat-fee-per-deal economics (LPT BB) beat any percentage split at that volume. Run /compare to confirm.</li>
</ul>

<div class="callout callout-insight">
  <p class="callout-label">The 2-minute test</p>
  <p>Open /compare, select all 5 brokerages, plug in your actual GCI and deal count. The brokerage showing the highest "Net to You" is the structural winner for your production profile. Everything else (sponsor, culture, office) is a soft factor on top of the math.</p>
</div>"""
    },
    {
        "slug": "cloud-brokerages-compared-2026",
        "title": "Cloud Brokerages Compared 2026: LPT vs eXp vs REAL vs Fathom | TPL Collective",
        "meta_desc": "The 4 major cloud brokerages in 2026 compared side by side: splits, caps, monthly fees, revenue share, and which model fits which production profile.",
        "h1": "Cloud Brokerages Compared 2026: LPT vs eXp vs REAL vs Fathom",
        "subtitle": "Cloud brokerages aren't all the same model. The differences in cap, per-deal fees, and revenue share are where the real decision lives.",
        "date": "2026-04-24",
        "date_display": "April 2026",
        "read_min": 8,
        "category": "Agent Guides",
        "verdict": "LPT, eXp, REAL, and Fathom are often grouped as 'cloud brokerages' but their economics are structurally different. LPT offers two plans (split and flat-fee) with the lowest overall caps in the group. eXp has the largest revenue share downline history. REAL has no monthly fee but a higher cap. Fathom uses a pure 100/0 flat-fee model. The right pick depends on your production and what you value in a downline.",
        "toc": [
            ("what-is-cloud", "What Is a Cloud Brokerage?"),
            ("the-four", "The Four Major Options"),
            ("side-by-side", "Side-by-Side Economics"),
            ("revenue-share", "Revenue Share Compared"),
            ("hidden-costs", "Hidden Costs to Watch"),
            ("best-for", "Which One Fits You?"),
            ("faq", "Frequently Asked"),
        ],
        "body": """<h2 id="what-is-cloud">What Is a Cloud Brokerage?</h2>
<p>"Cloud brokerage" generally means a fully remote brokerage with no physical offices - agents work independently, training and broker support are delivered virtually, and the cost structure passes the overhead savings back to agents via lower splits or caps.</p>
<p>The model emerged in the 2010s (eXp pioneered it at scale) and has expanded significantly through 2026. But the four brokerages covered here use very different economic structures underneath the "cloud" label.</p>

<h2 id="the-four">The Four Major Options</h2>
<h3>LPT Realty</h3>
<p>Two plans: Brokerage Partner (80/20, $15K cap, HybridShare revenue share) and Business Builder ($500/deal, $5K cap after 10 deals, HybridShare on upgrade). $195/txn on both. No monthly fee. Lofty CRM included.</p>
<h3>eXp Realty</h3>
<p>Single plan: 80/20 split, $16K cap, ~$85/month tech fee, revenue share program (7 tiers). [VERIFY] Stock award opportunities for milestones.</p>
<h3>REAL Brokerage</h3>
<p>Single plan: 85/15 split, $12K cap, revenue share program, tied to REAL Coin token/stock incentives. [VERIFY] No monthly fee.</p>
<h3>Fathom Realty</h3>
<p>Single plan: 100/0 split with $465 flat-fee-per-transaction, $9,000 annual cap (20 transactions), $700 annual fee. [VERIFY] Smaller revenue share model.</p>

<h2 id="side-by-side">Side-by-Side Economics</h2>

<div class="compare-table-wrap">
  <table>
    <thead><tr><th>Feature</th><th>LPT BP</th><th>LPT BB</th><th>eXp</th><th>REAL</th><th>Fathom</th></tr></thead>
    <tbody>
      <tr><td>Split</td><td>80/20</td><td>100/0 ($500/deal)</td><td>80/20</td><td>85/15</td><td>100/0 ($465/deal)</td></tr>
      <tr><td>Cap</td><td><span class="win">$15K</span></td><td><span class="win">$5K</span></td><td class="loss">$16K</td><td>$12K</td><td>$9K</td></tr>
      <tr><td>Break-even</td><td>$75K GCI</td><td>10 deals</td><td>$80K GCI</td><td>$80K GCI</td><td>20 deals</td></tr>
      <tr><td>Monthly fee</td><td><span class="win">$0</span></td><td><span class="win">$0</span></td><td class="loss">$85/mo</td><td><span class="win">$0</span></td><td><span class="win">$0</span></td></tr>
      <tr><td>Per-txn fee</td><td>$195</td><td>$195 + $500</td><td>Varies</td><td>Varies</td><td>$465 only</td></tr>
      <tr><td>Annual fee</td><td>$500</td><td>$500</td><td>Varies</td><td>Varies</td><td>$700</td></tr>
      <tr><td>Revenue share</td><td><span class="win">Yes (7 tiers)</span></td><td>On upgrade</td><td><span class="win">Yes (7 tiers)</span></td><td>Yes</td><td>Yes (smaller)</td></tr>
      <tr><td>CRM included</td><td>Lofty</td><td>Lofty</td><td>kvCORE</td><td>Proprietary</td><td>Proprietary</td></tr>
    </tbody>
  </table>
</div>

<div class="callout callout-insight">
  <p class="callout-label">Why break-even matters most</p>
  <p>LPT BB hits break-even at 10 deals regardless of GCI per deal. Fathom hits break-even at 20 deals. For a 12-deal agent, LPT BB means 2 deals of 100% commission; Fathom means zero. The same cloud label, wildly different outcomes.</p>
</div>

<h2 id="revenue-share">Revenue Share Compared</h2>
<p>All four offer some form of revenue share, but the mechanics differ:</p>
<ul>
  <li><strong>LPT HybridShare:</strong> 7 tiers, funded by 50% of each capped agent's company dollar ($7,500 for BP, $2,500 for BB). Unlock requires production-based tier requirements - not recruiting numbers alone.</li>
  <li><strong>eXp Revenue Share:</strong> 7 tiers, deepest established program by years in market. Heavily scaled for agents who recruited early in eXp's growth (2015-2020 cohort).</li>
  <li><strong>REAL:</strong> Revenue share tied to REAL's corporate structure and includes token/equity incentive components. [VERIFY]</li>
  <li><strong>Fathom:</strong> Smaller revenue share program; Fathom's original model was not revenue-share-first, so downline depth is shallower industry-wide.</li>
</ul>
<p>If revenue share is a primary driver for you, the question isn't just "does it exist" - it's "which existing downline can I realistically plug into?" That's a sponsor-specific conversation, not a brokerage-level one.</p>

<h2 id="hidden-costs">Hidden Costs to Watch</h2>
<p>Cloud brokerages advertise lower splits. But the total cost often includes line items not on the headline:</p>
<ul>
  <li><strong>Monthly tech fees</strong> (eXp ~$85/mo = $1,020/yr): adds up quickly and doesn't cap</li>
  <li><strong>E&O insurance</strong>: varies $200-$500/yr, sometimes bundled, sometimes separate</li>
  <li><strong>Transaction coordinator fees</strong>: some brokerages include, most charge per-deal ($300-$500)</li>
  <li><strong>CRM/IDX subscriptions</strong>: included at LPT (Lofty) and eXp (kvCORE), often extra elsewhere</li>
  <li><strong>Annual fee</strong> (LPT $500, Fathom $700)</li>
</ul>
<p>When comparing, sum every line item over a 12-month period at your actual deal count. The cloud brokerage with the "lowest split" isn't always the cheapest total cost.</p>

<h2 id="best-for">Which One Fits You?</h2>
<h3>LPT BP fits if:</h3>
<ul>
  <li>You do $75K-$200K GCI and want a predictable 80/20 ceiling with no monthly fee</li>
  <li>You want revenue share that's unlocked by production milestones, not pure recruiting</li>
  <li>You value Lofty CRM as a first-class tool</li>
</ul>
<h3>LPT BB fits if:</h3>
<ul>
  <li>You do 10-25+ deals/year with mixed deal sizes (especially lower-GCI deals where a flat fee beats a percentage)</li>
  <li>You want the lowest cap break-even in the industry</li>
  <li>You're willing to upgrade to BP later for full HybridShare access</li>
</ul>
<h3>eXp fits if:</h3>
<ul>
  <li>You have an established sponsor with a deep downline you'd be plugging into</li>
  <li>Monthly tech fee economics work at your production level</li>
  <li>Stock awards are meaningful to you</li>
</ul>
<h3>REAL fits if:</h3>
<ul>
  <li>You want 85/15 structurally (slightly better split than 80/20)</li>
  <li>You believe in REAL's equity/token incentive program long-term</li>
</ul>
<h3>Fathom fits if:</h3>
<ul>
  <li>You do 20+ deals with lower average GCI per deal (the 100/0 + flat-fee math works best for volume producers)</li>
  <li>Revenue share is secondary to per-deal economics</li>
</ul>

<h2 id="faq">Frequently Asked</h2>
<h3>Does every cloud brokerage work nationwide?</h3>
<p>LPT, eXp, REAL, and Fathom are all licensed in all 50 states or nearly all. Confirm your specific state before signing - regional licensing gaps do occur.</p>
<h3>Can I switch between cloud brokerages mid-year?</h3>
<p>Yes, but your cap at the new brokerage resets on your join date. If you've paid $10K of a $15K cap at one brokerage and switch mid-year, that progress does not transfer.</p>
<h3>Which cloud brokerage has the best tech?</h3>
<p>Subjective, but LPT (Lofty) and eXp (kvCORE) both use well-regarded industry-standard CRMs. REAL and Fathom use proprietary platforms that agents report mixed satisfaction with.</p>
<h3>What about regional cloud brokerages?</h3>
<p>Several exist (LoKation in FL/NC/SC, Samson in DMV, etc.). They often have stronger local broker support but give up the nationwide scalability and revenue share depth of the four covered here.</p>"""
    },
]


def main():
    for art in ARTICLES:
        html = render(art)
        out = BLOG / f"{art['slug']}.html"
        out.write_text(html)
        print(f"  wrote {out.relative_to(ROOT)}")
    print(f"\nGenerated {len(ARTICLES)} blog articles.")


if __name__ == "__main__":
    main()

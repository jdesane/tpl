#!/usr/bin/env python3
"""Insert a 'Ready to explore LPT?' linkback block before the disclaimer on every /vs/* page."""
from pathlib import Path

VS_DIR = Path("/Users/desane/Desktop/tpl/vs")

BLOCK = '''<!-- JOIN LPT CTA -->
<section style="max-width:800px;margin:0 auto;padding:2rem;text-align:center;">
  <div style="background:rgba(108,99,255,0.08);border:1px solid rgba(108,99,255,0.25);border-radius:10px;padding:1.4rem 1.6rem;">
    <p style="color:#8888aa;font-size:0.95rem;margin:0;line-height:1.6;">
      <strong style="color:#8b85ff;">Ready to explore LPT?</strong>
      Read <a href="/joining-lpt-realty" style="color:#6c63ff;font-weight:600;text-decoration:none;">the complete joining guide</a> to see how commission, revenue share, and sponsor selection actually work.
    </p>
  </div>
</section>

'''

MARKER = '<!-- DISCLAIMER -->'
FALLBACK_MARKER = '<div class="disclaimer">'

updated = []
skipped = []
for path in sorted(VS_DIR.glob("*.html")):
    if path.name == "index.html":
        continue
    text = path.read_text()
    if "joining-lpt-realty" in text:
        skipped.append(path.name + " (already linked)")
        continue
    if MARKER in text:
        new = text.replace(MARKER, BLOCK + MARKER, 1)
    elif FALLBACK_MARKER in text:
        new = text.replace(FALLBACK_MARKER, BLOCK + FALLBACK_MARKER, 1)
    else:
        skipped.append(path.name + " (no marker found)")
        continue
    path.write_text(new)
    updated.append(path.name)

print(f"Updated {len(updated)} files:")
for n in updated: print(f"  + {n}")
if skipped:
    print(f"Skipped {len(skipped)}:")
    for n in skipped: print(f"  - {n}")

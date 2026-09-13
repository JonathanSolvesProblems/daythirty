"""The submission thumbnail: name plus one line, 3:2, legible at 250 px.

Rendered from HTML with the product's own fonts and tokens (Kalam in the litigator's
oxblood on paper, Atkinson Hyperlegible for the line) so the card matches the page a
judge lands on. Gallery image 1 is not reused here: at card size it has too much in it.

    python scripts/thumbnail.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "preview" / "thumbnail.png"

HTML = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Kalam:wght@700&display=swap" rel="stylesheet">
<style>
  html,body{margin:0;width:1500px;height:1000px;background:#DDE1E6;overflow:hidden}
  .sheet{position:absolute;left:90px;top:80px;width:1320px;height:840px;background:#F3F5F7;
         box-shadow:0 2px 4px rgba(0,0,0,.08),0 18px 44px rgba(0,0,0,.10)}
  .label{position:absolute;top:22px;right:30px;font:400 24px 'Kalam',cursive;color:#5C636E}
  h1{position:absolute;left:110px;top:200px;margin:0;font:700 230px/1 'Kalam',cursive;color:#7A1F2E;letter-spacing:1px}
  svg{position:absolute;left:104px;top:448px;width:1000px;height:40px;overflow:visible}
  p{position:absolute;left:114px;top:520px;margin:0;width:1120px;font:400 62px/1.25 'Atkinson Hyperlegible',system-ui,sans-serif;color:#1C1F24}
  .site{position:absolute;left:114px;bottom:62px;font:400 30px 'Atkinson Hyperlegible',system-ui,sans-serif;color:#5C636E}
  .stamp{position:absolute;right:96px;bottom:70px;font:700 54px/1 'Kalam',cursive;color:#7A1F2E;border:4px solid #7A1F2E;
         padding:10px 22px;transform:rotate(-7deg);opacity:.9}
</style></head><body>
<div class="sheet">
  <div class="label">the appeal, drafted</div>
  <h1>Day Thirty</h1>
  <svg viewBox="0 0 1000 40" preserveAspectRatio="none">
    <defs><filter id="rough"><feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="2" seed="7"/>
    <feDisplacementMap in="SourceGraphic" scale="4"/></filter></defs>
    <path d="M4 22 C 180 14, 360 30, 540 20 S 880 26, 996 18" fill="none" stroke="#7A1F2E" stroke-width="7" stroke-linecap="round" filter="url(#rough)"/>
  </svg>
  <p>An insurance denial, worked end to end. It stops before anything is filed.</p>
  <div class="site">Strands Agents on Amazon Bedrock</div>
  <div class="stamp">READY TO SIGN</div>
</div>
</body></html>"""

tmp = OUT.parent / "_thumbnail.html"
tmp.write_text(HTML, encoding="utf-8")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1500, "height": 1000}, device_scale_factor=1)
    pg.goto(tmp.as_uri())
    pg.wait_for_function("document.fonts.ready.then(() => document.fonts.check(\"700 20px Kalam\"))", timeout=30000)
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(OUT))
    b.close()
tmp.unlink()
print(f"written {OUT.relative_to(ROOT)}  {OUT.stat().st_size // 1024} KB")

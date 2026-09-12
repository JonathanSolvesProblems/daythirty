"""Render the README's mermaid architecture diagram to a PNG for the submission form.

Reads the ```mermaid block out of README.md so there is exactly one source of truth,
renders it with mermaid in a headless browser, and writes _submission/architecture.png.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_submission" / "architecture.png"

HTML = """<!doctype html><html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>
  body{margin:0;background:#F3F5F7;font-family:'Atkinson Hyperlegible',system-ui,sans-serif}
  #wrap{padding:36px 40px;display:inline-block}
  h1{margin:0 0 6px;font:700 22px/1 system-ui;color:#7A1F2E}
  p{margin:0 0 18px;font:14px/1.4 system-ui;color:#5C636E}
</style></head><body><div id="wrap">
<h1>Day Thirty</h1>
<p>Two models, two deterministic engines, one gate. Nothing is filed until a person approves that specific letter.</p>
<pre class="mermaid">
%%{init: {"theme":"base","themeVariables":{"primaryColor":"#ffffff","primaryTextColor":"#1C1F24","primaryBorderColor":"#7A1F2E","lineColor":"#7A1F2E","secondaryColor":"#F3F5F7","tertiaryColor":"#E9ECF0","fontFamily":"system-ui","fontSize":"14px"}}}%%
__DIAGRAM__
</pre></div>
<script>mermaid.initialize({startOnLoad:true});</script>
</body></html>"""


def main() -> int:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"```mermaid\n(.*?)```", readme, re.S)
    if not m:
        print("no mermaid block in README.md"); return 1
    html = HTML.replace("__DIAGRAM__", m.group(1))
    tmp = ROOT / "_submission" / "_diagram.html"
    tmp.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1400, "height": 900}, device_scale_factor=2)
        page.goto(tmp.as_uri())
        page.wait_for_selector("pre.mermaid svg", timeout=30000)
        page.wait_for_timeout(600)
        page.locator("#wrap").screenshot(path=str(OUT))
        b.close()
    tmp.unlink()
    print(f"written {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

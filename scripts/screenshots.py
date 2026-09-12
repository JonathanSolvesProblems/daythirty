"""Capture the screens a judge actually sees, at the size they see them.

1280x720 is the demo-video frame. If the design does not read at this size it does not
read. Three states: first load, the deadline resolving, and the gate.

  python scripts/screenshots.py            # against http://127.0.0.1:8030
  python scripts/screenshots.py --dark
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_submission" / "shots"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8030")
    ap.add_argument("--dark", action="store_true")
    ap.add_argument("--case", type=int, default=0)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    suffix = "-dark" if args.dark else ""

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=2,
            color_scheme="dark" if args.dark else "light",
        )
        page = ctx.new_page()
        page.goto(args.base + "/")
        page.wait_for_function("document.fonts.ready.then(() => true)")
        page.wait_for_function("document.querySelector('#ta').value.length > 100", timeout=60000)
        for _ in range(args.case):
            page.click("#next")
            page.wait_for_timeout(1500)
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT / f"1-first-load{suffix}.png"))
        print("1 first load")

        page.click("#run")
        # deadline note appears
        page.wait_for_function(
            "[...document.querySelectorAll('.note')].some(n => n.textContent.includes('Day 30'))",
            timeout=90000,
        )
        page.wait_for_timeout(1400)  # let the marks finish drawing
        page.screenshot(path=str(OUT / f"2-deadline{suffix}.png"))
        print("2 deadline")

        # precedent note
        page.wait_for_function(
            "[...document.querySelectorAll('.note')].some(n => n.textContent.includes('overturned'))",
            timeout=90000,
        )
        page.wait_for_timeout(600)
        page.screenshot(path=str(OUT / f"3-precedent{suffix}.png"))
        print("3 precedent")

        # gate
        page.wait_for_selector("#gate.on", timeout=120000)
        page.wait_for_timeout(900)
        page.screenshot(path=str(OUT / f"4-gate{suffix}.png"))
        print("4 gate")

        page.click("#sign")
        page.wait_for_selector("#stamp.on", timeout=60000)
        page.wait_for_timeout(900)  # the "ready to file" note fades in
        page.screenshot(path=str(OUT / f"5-approved{suffix}.png"))
        print("5 approved")

        browser.close()
    print(f"written to {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

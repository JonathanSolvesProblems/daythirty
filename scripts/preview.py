"""Gallery previews for the submission form: 8 images at 3:2, one caption each, 140 max.

Story order is the demo video's order. The app shots drive the real page (one run of the
agent, then the signature) and screenshot states of that run; the two terminal shots are
the replays of real captured output used in the video, letterboxed from 16:9 to 3:2 in
their own background colour so the right edge, where the numbers are, is not cropped.

The character count is asserted here and printed to the terminal only. It never goes in
captions.md and never next to a caption in chat, because a count that sits beside a
caption gets pasted into the form with it.

    .venv/Scripts/uvicorn app:app --port 8030          # the app
    python -m http.server 8031 --bind 127.0.0.1        # from broll/, for the replays
    python scripts/preview.py
"""
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------ CONFIG
OUT = ROOT / "preview"
APP = "http://127.0.0.1:8030/"
REPLAY = "http://127.0.0.1:8031/_term.html"
W, H = 1500, 1000  # 3:2

NAMES = ["1-letter", "2-record", "3-deadline", "4-precedent", "5-draft", "6-gate",
         "7-approved", "8-agentcore"]

CAPTIONS = {
    "1-letter":    "Day Thirty works a California insurance denial end to end and stops before anything is filed. Every case here is a real published denial.",
    "2-record":    "California publishes every independent medical review since 2001. Overturns rose from 25% in 2001 to 72.34% in 2025, counted from it.",
    "3-deadline":  "The deadline comes from the statute, not a model: 30 days after the grievance the clock starts, HSC 1374.30(j)(3), six months under (k).",
    "4-precedent": "The overturn rate for denials like this one, counted over the state's own decisions, and what persuaded the reviewers in the cases that won.",
    "5-draft":     "Claude Haiku 4.5 on Amazon Bedrock drafts the appeal from those findings. Brackets mark the specifics only the patient can fill in.",
    "6-gate":      "Then it stops. A Strands interrupt hands the exact letter to a person. Sign it, or don't. Nothing leaves without a signature.",
    "7-approved":  "Approved: the finished application, the date it must reach DMHC, and the real channels. There is no API, so the last step is yours.",
    "8-agentcore": "The same agent on Amazon Bedrock AgentCore: a real published denial in, 14.6 seconds round trip, stopped at the gate, nothing filed.",
}
# ------------------------------------------------------------------ END CONFIG

for k, c in CAPTIONS.items():
    assert len(c) <= 140, f"{k}: {len(c)} characters, limit is 140"
assert NAMES == list(CAPTIONS), "NAMES and CAPTIONS must list the same names in the same order"
assert len(NAMES) <= 8, "eight is the ceiling; a gallery is a story, not an archive"
OUT.mkdir(parents=True, exist_ok=True)

WAIT_GATE = "new Promise(r => { const t = setInterval(() => { if (document.querySelector('#gate.on')) { clearInterval(t); r(true); } }, 250); })"
WAIT_STAMP = "new Promise(r => { const t = setInterval(() => { if (document.querySelector('#stamp.on')) { clearInterval(t); r(true); } }, 250); })"
WAIT_LETTER = "new Promise(r => { const t = setInterval(() => { const ta = document.querySelector('#ta'); if (ta && ta.value.length > 100) { clearInterval(t); r(true); } }, 200); })"


def scroll_to_note(pg, needle: str, offset: int = 40):
    pg.evaluate(
        "([needle, off]) => { const n = [...document.querySelectorAll('.note')].find(e => e.textContent.includes(needle));"
        " if (n) window.scrollTo({top: n.getBoundingClientRect().top + window.scrollY - off, behavior: 'auto'}); }",
        [needle, offset],
    )


def letterbox(src: Image.Image) -> Image.Image:
    bg = src.getpixel((2, 2))
    target_h = src.width * 2 // 3
    canvas = Image.new("RGB", (src.width, target_h), bg)
    canvas.paste(src, (0, (target_h - src.height) // 2))
    return canvas


with sync_playwright() as p:
    b = p.chromium.launch(headless=True)

    # --- the app, one real run ---------------------------------------------------------
    ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=1, color_scheme="light")
    pg = ctx.new_page()
    pg.goto(APP, wait_until="load", timeout=60_000)
    pg.evaluate("document.fonts.ready")
    pg.evaluate(WAIT_LETTER)
    pg.wait_for_timeout(600)
    pg.screenshot(path=str(OUT / "1-letter.png"))

    pg.click("#run")
    pg.evaluate(WAIT_GATE)
    pg.wait_for_timeout(1500)  # marks finish drawing, notes settle

    # the intake note sits directly above the deadline note; start there so neither is cut
    scroll_to_note(pg, "Read it", 28)
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(OUT / "3-deadline.png"))

    scroll_to_note(pg, "overturned", 14)
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(OUT / "4-precedent.png"))

    pg.evaluate("window.scrollTo({top: document.querySelector('#appeal').getBoundingClientRect().top + window.scrollY - 24, behavior: 'auto'})")
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(OUT / "5-draft.png"))

    pg.evaluate("window.scrollTo({top: document.querySelector('#gate').getBoundingClientRect().top + window.scrollY - 560, behavior: 'auto'})")
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(OUT / "6-gate.png"))

    pg.click("#sign")
    pg.evaluate(WAIT_STAMP)
    pg.wait_for_timeout(2500)  # the closing note and the scroll to the end of the sheet
    pg.evaluate("window.scrollTo({top: document.querySelector('#stamp').getBoundingClientRect().top + window.scrollY - 700, behavior: 'auto'})")
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(OUT / "7-approved.png"))
    ctx.close()

    # --- the replays of real output, 16:9 then letterboxed ------------------------------
    ctx = b.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1, color_scheme="dark")
    pg = ctx.new_page()
    for name, mode, wait in [("2-record", "trend", 9000), ("8-agentcore", "invoke", 14000)]:
        pg.goto(f"{REPLAY}?mode={mode}", wait_until="load", timeout=60_000)
        pg.wait_for_timeout(wait)
        tmp = OUT / f"_{name}-16x9.png"
        pg.screenshot(path=str(tmp))
        letterbox(Image.open(tmp).convert("RGB")).save(OUT / f"{name}.png")
        tmp.unlink()
    ctx.close()
    b.close()

lines = ["# Image gallery, upload in this order", "",
         "One caption per image. Copy the block contents only.", ""]
for name in NAMES:
    lines += [f"## {name}.png", "", "```", CAPTIONS[name], "```", ""]
(OUT / "captions.md").write_text("\n".join(lines), encoding="utf-8")

for name in NAMES:
    f = OUT / f"{name}.png"
    im = Image.open(f)
    ratio = im.width / im.height
    ok = "ok " if abs(ratio - 1.5) < 0.01 and f.stat().st_size < 5_000_000 else "BAD"
    print(f"  {ok} {f.name:<20} {im.width}x{im.height}  {f.stat().st_size // 1024:>4} KB   caption {len(CAPTIONS[name]):>3}/140")
print(f"\n{len(NAMES)} images + captions.md in {OUT.relative_to(ROOT)}")

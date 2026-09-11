"""Fail if the README and the measurements disagree.

Every headline number in README.md has to appear in a report that a script wrote from
data. This reads those reports, derives the exact strings the README is allowed to
claim, and fails the build if any of them is missing from the README or if the README
quotes a figure the reports do not support.

The point is that prose drifts and data does not. A number gets updated in a report and
forgotten in a paragraph, or a paragraph gets rewritten from memory. This catches both.
It exists as a check rather than a note because a check runs and a note gets skipped.

  python eval/check_claims.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
EVAL = ROOT / "eval"


def load(name: str) -> dict:
    p = EVAL / name
    if not p.exists():
        print(f"MISSING REPORT: {p.relative_to(ROOT)}. Run the eval that writes it.")
        sys.exit(2)
    return json.loads(p.read_text(encoding="utf-8"))


def pct(a: int, b: int) -> str:
    """Format the way a person writes it: 66.7%, but 100% rather than 100.0%."""
    if not b:
        return "n/a"
    v = a / b * 100
    return f"{v:.0f}%" if abs(v - round(v)) < 1e-9 else f"{v:.1f}%"


def main() -> int:
    readme = README.read_text(encoding="utf-8")
    failures: list[str] = []
    checked = 0

    def must_contain(claim: str, why: str) -> None:
        nonlocal checked
        checked += 1
        if claim not in readme:
            failures.append(f"README lacks {claim!r}  ({why})")

    # --- corpus and split ----------------------------------------------------------------
    sp = load("split_report.json")
    must_contain(f"**{sp['corpus_total']:,}**", "total published decisions in the corpus")
    must_contain(f"{sp['train']:,}", "size of the precedent corpus")
    must_contain(f"{sp['test']:,}", "size of the held-out set")

    # --- retrieval coverage ------------------------------------------------------------
    cov = load("coverage_report.json")
    n = cov["held_out"]
    must_contain(f"**{pct(cov['with_rate'], n)}**", "share of held-out denials with a published rate")
    must_contain(f"**{pct(cov['with_exemplar'], n)}**", "share with at least one exemplar")
    must_contain(f"**{pct(cov['tightest_tier'], n)}**", "share at the tightest tier")
    must_contain(f"**{pct(cov['no_exemplar'], n)}**", "share with no exemplar")
    must_contain(f"**{cov['rate_min']:.1%} to {cov['rate_max']:.1%}**", "range of published rates")

    # --- intake --------------------------------------------------------------------------
    it = load("intake_report.json")
    for key, why in [
        ("grounds_exact", "grounds recovered"),
        ("denial_date_exact", "denial date recovered"),
        ("treatment_category_exact", "treatment category exact"),
        ("diagnosis_category_exact", "diagnosis category exact"),
        ("diagnosis_category_equivalent", "diagnosis category with synonyms"),
    ]:
        a, b = it[key]
        must_contain(f"**{a}/{b} ({pct(a, b)})**", why)

    # --- grounding -----------------------------------------------------------------------
    g = load("grounding_report.json")
    a, b = g["numeric_claims"]["grounded"], g["numeric_claims"]["total"]
    must_contain(f"**{a}/{b} ({pct(a, b)})**", "numeric claims grounded")
    a, b = g["named_authorities"]["grounded"], g["named_authorities"]["total"]
    must_contain(f"**{a}/{b} ({pct(a, b)})**", "named authorities grounded")
    nc = g["negative_control"]
    must_contain(f"**{nc['caught']}/{nc['total']}**", "negative control")

    # --- ablation ------------------------------------------------------------------------
    ab = load("ablation_report.json")
    wr, wo = ab["record_ablation"]["with_record"], ab["record_ablation"]["without_record"]
    must_contain(f"| with the record | {wr['pct_claims']} | **{wr['sourced']} "
                 f"({pct(wr['sourced'], wr['pct_claims'])})** |",
                 "ablation: with-record row")
    must_contain(f"| without it | {wo['pct_claims']}, in {wo['letters_asserting_a_rate']} of "
                 f"{ab['runs']} letters | **0** |", "ablation: without-record row")
    rates = wo["asserted_rates"]
    if rates:
        must_contain(" and ".join([", ".join(rates[:-1]), rates[-1]]) if len(rates) > 1 else rates[0],
                     "the rates the model invented without the record")
    e1 = ab["engine_ablation"]["plan_silent"]
    e2 = ab["engine_ablation"]["plan_answered_day_120"]
    must_contain(f"| plan silent | {e1['exact']}/{ab['runs']} | {e1['early']} | {e1['late']} |",
                 "engine ablation, silent timeline")
    must_contain(f"| plan answered on day 120 | {e2['exact']}/{ab['runs']} | {e2['early']} | "
                 f"**{e2['late']}** |", "engine ablation, late-answer timeline")

    # --- numbers in the README that no report backs ------------------------------------
    # Any bold percentage in the README must be derivable from a report. This is the
    # direction the check most often catches: a figure typed from memory.
    backed = set()
    for report in (sp, cov, it, g, ab):
        text = json.dumps(report)
        backed.update(re.findall(r"\d+(?:\.\d+)?", text))
        backed.update(f"{int(x):,}" for x in re.findall(r"\b\d{4,}\b", text))
    # Percentages the reports imply but do not store literally.
    backed.update({
        pct(cov["with_rate"], n)[:-1], pct(cov["with_exemplar"], n)[:-1],
        pct(cov["tightest_tier"], n)[:-1], pct(cov["no_exemplar"], n)[:-1],
        f"{cov['rate_min']*100:.1f}", f"{cov['rate_max']*100:.1f}",
    })
    for key in ("grounds_exact", "denial_date_exact", "treatment_category_exact",
                "diagnosis_category_exact", "diagnosis_category_equivalent"):
        a_, b_ = it[key]
        backed.add(pct(a_, b_)[:-1])
    for pair in (g["numeric_claims"], g["named_authorities"]):
        backed.add(pct(pair["grounded"], pair["total"])[:-1])

    # Figures the README takes from a primary source it cites inline (KFF, DMHC's own
    # trend, the statute sweep in eval/deadline_divergence.py) or states as part of a
    # method rather than a result. Listed here so they are visible, not silently allowed.
    EXTERNAL = {
        "85", "262,982", "1", "66",            # KFF 2024, cited in the README
        "72.3", "25",                           # DMHC trend, eval/trend.py
        "17.9", "1.8", "29.2", "82.7",          # eval/deadline_divergence.py sweep
        "30.0", "33.3",                         # intake before the taxonomy fix
        "40", "50", "60",                       # rates the model invented in the ablation
        "5", "6", "0",                          # ablation table cells
        "4.9", "7.0",                           # ambiguous subcategory shares
        "12,570", "46",                         # embedding attempt, abandoned
        "100",
    }

    bold_numbers = re.findall(r"\*\*(\d[\d,]*(?:\.\d+)?)%?\*\*", readme)
    for num in bold_numbers:
        plain = num.replace(",", "")
        if num in backed or plain in backed or num in EXTERNAL or plain in EXTERNAL:
            continue
        failures.append(f"README bolds {num!r} and no report or cited source backs it")

    print(f"claims checked against reports: {checked}")
    print(f"bold figures audited: {len(bold_numbers)}")
    if failures:
        print(f"\nFAIL: {len(failures)} disagreement(s) between README and data")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK: every checked claim in README.md matches a measurement on disk")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

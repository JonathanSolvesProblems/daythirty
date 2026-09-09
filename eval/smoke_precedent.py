"""Run the precedent index against real held-out denials and check the leak controls.

Two things are being verified here, not one:
  1. Retrieval returns something usable on real 2025-26 cases.
  2. The reasoning handed to a drafting prompt does NOT contain the verdict. If it does,
     the model is reading the answer key and every downstream number is worthless.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from overturn.precedent import PrecedentIndex, reasoning_of  # noqa: E402

TEST = ROOT / "data" / "split" / "test.jsonl"

VERDICT_WORDS = re.compile(
    r"should be overturned|should be upheld|Final Result|denial should|"
    r"is not medically necessary for the treatment of this patient\.$",
    re.I,
)


def main() -> None:
    idx = PrecedentIndex()
    print(f"precedent index: {len(idx):,} published decisions, 2016-2024\n")

    test = [json.loads(l) for l in TEST.open(encoding="utf-8")]
    print(f"held-out cases: {len(test):,}\n")

    # --- leak check across the whole training corpus --------------------------------
    leaks = 0
    checked = 0
    for r in idx.records:
        f = r.get("findings", "")
        if not f:
            continue
        checked += 1
        if VERDICT_WORDS.search(reasoning_of(f)):
            leaks += 1
    print(f"LEAK CHECK: {leaks:,} of {checked:,} stripped narratives still contain a "
          f"verdict phrase ({leaks/max(checked,1):.3%})")
    if leaks:
        print("  ^ any non-zero number here has to be driven to zero before drafting.\n")
    else:
        print("  clean\n")

    # --- retrieval on real held-out cases ---------------------------------------------
    shown = 0
    for rec in test:
        if shown >= 3:
            break
        res = idx.query(rec["case"], k=2)
        if not res.exemplars:
            continue
        shown += 1
        c = rec["case"]
        print("=" * 78)
        print(f"HELD-OUT CASE ({rec['year']}): {c['DiagnosisSubCategory']} / "
              f"{c['TreatmentSubCategory']} / {c['Type']}")
        print(f"  actual determination (hidden from the agent): "
              f"{'OVERTURNED' if rec['label'] else 'UPHELD'}")
        print(f"  cohort: {res.cohort_overturned}/{res.cohort_n} overturned "
              f"= {res.cohort_rate:.1%}  [matched on {res.cohort_tier}]")
        for n in res.notes:
            print(f"  note: {n}")
        for i, ex in enumerate(res.exemplars, 1):
            print(f"\n  --- exemplar {i} ({ex.year}, tier {ex.tier}) ---")
            if ex.specialty:
                print(f"  reviewer: board-certified in {ex.specialty}")
            print(f"  {ex.reasoning[:420]}...")
        print()


if __name__ == "__main__":
    sys.exit(main())

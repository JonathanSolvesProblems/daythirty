"""How often can the state's published record actually say anything about a real denial?

Run over all 3,276 held-out 2025-26 cases. This is a coverage measurement, not an
accuracy one: it asks whether California has published a close enough decision to argue
from, which is a property of the corpus rather than of my code.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daythirty.precedent import PrecedentIndex  # noqa: E402

TEST = ROOT / "data" / "split" / "test.jsonl"


def main() -> None:
    idx = PrecedentIndex()
    test = [json.loads(line) for line in TEST.open(encoding="utf-8")]
    print(f"precedent corpus: {len(idx):,} decisions (2016-2024)")
    print(f"held-out denials: {len(test):,} (2025-26)\n")

    with_exemplars = 0
    with_rate = 0
    tiers = Counter()
    ex_tiers = Counter()
    rates = []
    n_ex = Counter()

    for rec in test:
        res = idx.query(rec["case"], k=3)
        if res.cohort_rate is not None:
            with_rate += 1
            tiers[res.cohort_tier] += 1
            rates.append(res.cohort_rate)
        if res.exemplars:
            with_exemplars += 1
            ex_tiers[res.exemplars[0].tier] += 1
        n_ex[len(res.exemplars)] += 1

    n = len(test)
    print(f"got a published overturn rate:      {with_rate:,}/{n:,}  ({with_rate/n:.1%})")
    print(f"got at least one usable exemplar:   {with_exemplars:,}/{n:,}  "
          f"({with_exemplars/n:.1%})")
    print(f"\nexemplars returned per case:")
    for k in sorted(n_ex):
        print(f"  {k}: {n_ex[k]:,}  ({n_ex[k]/n:5.1%})")

    print(f"\ncohort tier used for the rate:")
    for k, v in tiers.most_common():
        print(f"  {v:>6,}  ({v/n:5.1%})  {k}")

    print(f"\nclosest exemplar tier achieved:")
    for k, v in ex_tiers.most_common():
        print(f"  {v:>6,}  ({v/n:5.1%})  {k}")

    if rates:
        print(f"\npublished overturn rate quoted to the patient:")
        print(f"  median {statistics.median(rates):.1%}, "
              f"min {min(rates):.1%}, max {max(rates):.1%}")


if __name__ == "__main__":
    sys.exit(main())

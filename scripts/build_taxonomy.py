"""Derive California's classification vocabulary from the published corpus.

Two files are written into the package, because the agent needs them at runtime:

  taxonomy.json         the valid category values, so a model can never invent one
  subcategory_map.json  every subcategory paired with the category the state most often
                        filed it under

The second file is the one that matters. Asking a model to guess that California files
"Speech Therapy" under "Autism Related Tx" is asking it to infer something that is not
inferable from a letter. The state already answered it 42,749 times, so it is a lookup.

Where a subcategory has been filed under more than one category over the years, the modal
one wins. That is the state's own most common answer rather than a judgement of mine, and
the count of ambiguous entries is printed so the residual error is visible.

  python scripts/build_taxonomy.py
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10_000_000)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "imr-determinations.csv"
PKG = ROOT / "src" / "daythirty"

PAIRS = [
    ("diagnosis", "DiagnosisSubCategory", "DiagnosisCategory"),
    ("treatment", "TreatmentSubCategory", "TreatmentCategory"),
]


def main() -> int:
    if not RAW.exists():
        print(f"missing {RAW}. Run scripts/fetch_corpus.py first.", file=sys.stderr)
        return 1

    cats: dict[str, Counter] = {c: Counter() for c in
                                ("DiagnosisCategory", "TreatmentCategory", "Type")}
    sub: dict[str, defaultdict] = {k: defaultdict(Counter) for k, _, _ in PAIRS}

    with RAW.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            for c in cats:
                v = (row.get(c) or "").strip()
                if v:
                    cats[c][v] += 1
            for key, subcol, catcol in PAIRS:
                s = (row.get(subcol) or "").strip()
                c = (row.get(catcol) or "").strip()
                if s and c:
                    sub[key][s][c] += 1

    taxonomy = {c: sorted(v) for c, v in cats.items()}
    (PKG / "taxonomy.json").write_text(
        json.dumps(taxonomy, indent=1, sort_keys=True), encoding="utf-8"
    )

    mapping = {k: {s: c.most_common(1)[0][0] for s, c in sub[k].items()} for k, _, _ in PAIRS}
    (PKG / "subcategory_map.json").write_text(
        json.dumps(mapping, indent=1, sort_keys=True), encoding="utf-8"
    )

    for c, v in taxonomy.items():
        print(f"{c}: {len(v)} distinct values")
    for key, _, _ in PAIRS:
        ambiguous = sum(1 for v in sub[key].values() if len(v) > 1)
        total = len(sub[key])
        print(f"{key} subcategories: {total}, of which {ambiguous} "
              f"({ambiguous/total:.1%}) the state has filed under more than one category")
    print(f"\nwrote {PKG.relative_to(ROOT)}/taxonomy.json and subcategory_map.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

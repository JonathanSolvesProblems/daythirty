"""Build a leak-free temporal split of the California IMR corpus, then measure the
deterministic precedent-lookup baseline on the held-out years.

Leak controls, all deliberate:

  1. The `Findings` narrative is written by the reviewer AFTER deciding, and states the
     verdict outright. It is therefore stripped from every test case. The agent sees
     only what a patient actually holds in their hand on the day of the denial:
     the condition, the treatment that was refused, and the grounds the plan cited.
  2. The split is temporal, not random. Precedent may only be retrieved from cases
     decided strictly BEFORE the held-out period, so the agent can never cite a
     neighbour that is itself part of the answer key.
  3. `ReferenceID` is dropped; its prefix encodes case type and year.

Ground truth is the `Determination` column: the published decision of a
California-contracted independent physician reviewer. Nothing here is authored by us.
"""

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

csv.field_size_limit(10_000_000)

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "imr-determinations.csv"
OUT = ROOT / "data" / "split"

TEST_FROM_YEAR = 2025

# DMHC only began publishing the structured "Findings / Final Result / Credentials"
# narrative in 2015, and only reached ~98% coverage in 2016 (eval/structure_by_year.py).
# Cases before that are 500 to 1,300 characters of unstructured prose and cannot be used
# as precedent, so the index starts at 2016 rather than silently including them.
TRAIN_FROM_YEAR = 2016

# Exactly the fields a patient can read off their own denial letter.
CASE_FIELDS = [
    "DiagnosisCategory",
    "DiagnosisSubCategory",
    "TreatmentCategory",
    "TreatmentSubCategory",
    "Type",
    "AgeRange",
    "PatientGender",
    "IMRType",
]

OVERTURNED = "Overturned Decision of Health Plan"


def to_label(determination: str) -> int:
    return 1 if determination == OVERTURNED else 0


def case_of(row: dict) -> dict:
    return {f: (row.get(f) or "").strip() for f in CASE_FIELDS}


def main() -> None:
    train, test = [], []
    with RAW.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            det = row["Determination"]
            if det not in (OVERTURNED, "Upheld Decision of Health Plan"):
                continue
            try:
                year = int(row["ReportYear"])
            except (TypeError, ValueError):
                continue
            rec = {
                "year": year,
                "case": case_of(row),
                "label": to_label(det),
            }
            if year >= TEST_FROM_YEAR:
                test.append(rec)
            elif year >= TRAIN_FROM_YEAR:
                # Findings kept ONLY on the train side; this is the precedent the
                # agent is allowed to read and cite.
                rec["findings"] = row.get("Findings") or ""
                train.append(rec)
            # Pre-2016 cases are dropped entirely: no usable narrative to cite.

    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "train.jsonl").open("w", encoding="utf-8") as fh:
        for r in train:
            fh.write(json.dumps(r) + "\n")
    with (OUT / "test.jsonl").open("w", encoding="utf-8") as fh:
        for r in test:
            fh.write(json.dumps(r) + "\n")

    print(f"train ({TRAIN_FROM_YEAR}-{TEST_FROM_YEAR - 1}): {len(train):,}")
    print(f"test  (>= {TEST_FROM_YEAR}):      {len(test):,}")
    base = sum(r["label"] for r in test) / len(test)
    print(f"test overturn base rate:  {base:.4f}")
    print(f"majority-class accuracy:  {max(base, 1 - base):.4f}   <- the number to beat")

    # ---- Deterministic precedent-lookup baseline -------------------------------
    # Back off through progressively coarser cohorts until one has enough history.
    keys = [
        ("DiagnosisSubCategory", "TreatmentSubCategory", "Type"),
        ("DiagnosisCategory", "TreatmentSubCategory", "Type"),
        ("DiagnosisCategory", "TreatmentCategory", "Type"),
        ("TreatmentCategory", "Type"),
        ("Type",),
    ]
    tables = [defaultdict(lambda: [0, 0]) for _ in keys]
    for r in train:
        for i, k in enumerate(keys):
            cell = tables[i][tuple(r["case"][f] for f in k)]
            cell[0] += r["label"]
            cell[1] += 1

    MIN_N = 20
    correct = 0
    used = Counter()
    prior = sum(r["label"] for r in train) / len(train)
    for r in test:
        rate, tier = prior, "global"
        for i, k in enumerate(keys):
            cell = tables[i].get(tuple(r["case"][f] for f in k))
            if cell and cell[1] >= MIN_N:
                rate, tier = cell[0] / cell[1], "+".join(k)
                break
        used[tier] += 1
        if int(rate >= 0.5) == r["label"]:
            correct += 1

    acc = correct / len(test)
    print(f"\nprecedent-lookup baseline: {acc:.4f}  ({correct:,}/{len(test):,})")
    print(f"lift over majority class:  {acc - max(base, 1 - base):+.4f}")
    print("\ncohort tier actually used:")
    for k, v in used.most_common():
        print(f"  {v:>6,}  {k}")


if __name__ == "__main__":
    sys.exit(main())

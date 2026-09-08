"""Measure how mechanically parseable the reviewers' published narratives are.

Anything I can pull out with a regex is gold the reviewer authored. Anything needing
judgement is gold I authored. This script measures which is which, so the headline
metric can be built on the first kind.
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(10_000_000)
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "imr-determinations.csv"

SEC_FINDINGS = re.compile(r"Findings:", re.I)
SEC_RESULT = re.compile(r"Final Result:", re.I)
SEC_CREDS = re.compile(r"Credentials/Qualifications:", re.I)

# The credentials sentence is templated. Pull the specialty phrase out of it.
SPECIALTY = re.compile(
    r"reviewer is board[‐‑‒–—-]?certified in ([^.]+?)(?:,? and is actively practicing|\.)",
    re.I,
)

# Recurring clinical predicates, in the reviewers' own recurring phrasing.
PREDICATES = {
    "failed prior therapy": r"has failed|failed multiple|failed (?:several|other|prior|two|three)|did not respond to|inadequate response",
    "intolerance to alternative": r"due to side effects|adverse (?:effect|reaction)|could not tolerate|intoleran",
    "established/continuing therapy": r"successfully managed|has been (?:stable|maintained)|continuation of|ongoing therapy|currently receiving",
    "meets labeled/FDA criteria": r"meeting FDA criteria|FDA[‐‑‒–—\- ]approved|labeled indication|per the label",
    "literature supports": r"medical literature supports|literature supports|published (?:studies|literature)|evidence supports",
    "guideline supports": r"guidelines? (?:support|recommend)|is recommended",
    "lower level of care inadequate": r"lower level of care|less intensive|outpatient (?:treatment|setting) (?:is|was) (?:not|insufficient)",
    "no acute change / stable": r"does not show an acute change|clinically stable|no acute",
    "not medically necessary": r"is not medically necessary|was not medically necessary",
    "experimental/unproven": r"experimental|investigational|unproven",
}


def main() -> None:
    n = 0
    have = Counter()
    spec_hit = 0
    specialties = Counter()
    pred_hits = Counter()
    pred_per_case = Counter()

    with RAW.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            text = row.get("Findings") or ""
            if not text.strip():
                continue
            n += 1
            if SEC_FINDINGS.search(text):
                have["Findings:"] += 1
            if SEC_RESULT.search(text):
                have["Final Result:"] += 1
            if SEC_CREDS.search(text):
                have["Credentials/Qualifications:"] += 1

            m = SPECIALTY.search(text)
            if m:
                spec_hit += 1
                s = re.sub(r"\s+", " ", m.group(1)).strip().lower()
                s = re.sub(r"^(a|an)\s+", "", s)
                specialties[s] += 1

            k = 0
            for name, pat in PREDICATES.items():
                if re.search(pat, text, re.I):
                    pred_hits[name] += 1
                    k += 1
            pred_per_case[k] += 1

    print(f"records with non-empty Findings: {n:,}\n")
    print("template section present:")
    for k, v in have.most_common():
        print(f"  {v/n:7.2%}  {k}")

    print(f"\nboard specialty extracted by regex: {spec_hit:,} ({spec_hit/n:.2%})")
    print(f"distinct specialty strings: {len(specialties):,}")
    print("\ntop 15 specialties:")
    for k, v in specialties.most_common(15):
        print(f"  {v:>6,}  {v/n:6.2%}  {k[:70]}")

    print("\nclinical predicate hit rate (reviewer's own recurring phrasing):")
    for k, v in pred_hits.most_common():
        print(f"  {v:>6,}  {v/n:6.2%}  {k}")

    print("\npredicates matched per case:")
    for k in sorted(pred_per_case):
        v = pred_per_case[k]
        print(f"  {k} predicates: {v:>6,}  ({v/n:5.1%})")


if __name__ == "__main__":
    sys.exit(main())

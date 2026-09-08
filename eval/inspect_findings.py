"""Look at what the reviewers actually cite in their published Findings.

The question this answers: is there a gold signal in the reviewer's own words that I
can extract deterministically, so the thing being scored was authored by California's
independent reviewer and not by me? If the narratives name real external authorities
(guidelines, criteria sets, literature), the grading target is external. If they are
purely free-form clinical prose, I would have to invent the rubric, and the metric
collapses back into grading my own homework.
"""

import csv
import random
import re
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(10_000_000)
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "imr-determinations.csv"
OVERTURNED = "Overturned Decision of Health Plan"

# Real, externally maintained authorities. None of these are mine; they are the
# guideline bodies and criteria sets that actually govern US coverage decisions.
AUTHORITIES = {
    "MCG/Milliman": r"\bMCG\b|Milliman",
    "InterQual": r"InterQual",
    "NCCN": r"\bNCCN\b|National Comprehensive Cancer Network",
    "ASAM": r"\bASAM\b|American Society of Addiction Medicine",
    "CMS/Medicare": r"\bCMS\b|Medicare|\bLCD\b|\bNCD\b",
    "FDA": r"\bFDA\b|Food and Drug Administration",
    "Cochrane": r"Cochrane",
    "ACR": r"\bACR\b|American College of Radiology",
    "ACOG": r"\bACOG\b|American College of Obstetricians",
    "AAP": r"\bAAP\b|American Academy of Pediatrics",
    "ADA": r"American Diabetes Association|American Dental Association",
    "AHA/ACC": r"American Heart Association|American College of Cardiology",
    "APA": r"American Psychiatric Association|\bDSM-?5?\b",
    "Hayes": r"\bHayes\b",
    "UpToDate": r"UpToDate",
    "peer-reviewed lit": r"peer-reviewed|peer reviewed|published literature|clinical trial|randomized",
    "guideline (generic)": r"guideline",
    "medical necessity criteria": r"medical necessity criteri|criteria for",
}


def main() -> None:
    n_over = 0
    hits = Counter()
    any_hit = 0
    samples = []
    rng = random.Random(7)

    with RAW.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if row["Determination"] != OVERTURNED:
                continue
            try:
                if int(row["ReportYear"]) < 2025:
                    continue
            except (TypeError, ValueError):
                continue
            text = row.get("Findings") or ""
            n_over += 1
            found = [name for name, pat in AUTHORITIES.items() if re.search(pat, text, re.I)]
            for name in found:
                hits[name] += 1
            if found:
                any_hit += 1
            if len(samples) < 3 and rng.random() < 0.05:
                samples.append((row["TreatmentSubCategory"], text))

    print(f"held-out overturned cases (2025-26): {n_over:,}")
    print(f"cases naming at least one external authority: {any_hit:,} ({any_hit/n_over:.1%})\n")
    print("authority mention rate:")
    for name, c in hits.most_common():
        print(f"  {c:>5,}  {c/n_over:6.1%}  {name}")

    print("\n" + "=" * 78)
    print("SAMPLE FINDINGS (verbatim, to see the actual shape of the gold text)")
    print("=" * 78)
    for treat, text in samples:
        print(f"\n--- treatment: {treat}")
        print(text[:1800])


if __name__ == "__main__":
    sys.exit(main())

"""Profile the California DMHC Independent Medical Review corpus.

This is the external grader for the project: every determination in this file was
made by a California-contracted independent physician reviewer and published by the
Department of Managed Health Care. Nothing in it was authored here.

Source: https://data.chhs.ca.gov/dataset/independent-medical-review-imr-determinations-trend
"""

import csv
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(10_000_000)

RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "imr-determinations.csv"

STRUCTURED = [
    "DiagnosisCategory",
    "DiagnosisSubCategory",
    "TreatmentCategory",
    "TreatmentSubCategory",
    "Type",
    "AgeRange",
    "PatientGender",
    "IMRType",
]


def main() -> None:
    counts = {f: Counter() for f in STRUCTURED}
    determination = Counter()
    year = Counter()
    blank_structured = Counter()
    rows = 0

    with RAW.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        print("columns:", reader.fieldnames)
        for row in reader:
            rows += 1
            determination[row["Determination"]] += 1
            year[row["ReportYear"]] += 1
            for f in STRUCTURED:
                v = (row.get(f) or "").strip()
                counts[f][v] += 1
                if not v:
                    blank_structured[f] += 1

    print(f"\nrows: {rows:,}")

    print("\n--- Determination (the ground truth label) ---")
    for k, v in determination.most_common():
        print(f"  {v:>7,}  {v/rows:6.2%}  {k!r}")

    print("\n--- ReportYear ---")
    ys = sorted(year.items(), key=lambda kv: kv[0])
    print(f"  range: {ys[0][0]} .. {ys[-1][0]}")
    for k, v in ys[-8:]:
        print(f"  {k}: {v:,}")

    print("\n--- Cardinality of the fields available to the agent at denial time ---")
    for f in STRUCTURED:
        print(f"  {f:<22} distinct={len(counts[f]):>5}  blank={blank_structured[f]:,}")

    print("\n--- Type (denial grounds) ---")
    for k, v in counts["Type"].most_common():
        print(f"  {v:>7,}  {v/rows:6.2%}  {k!r}")

    print("\n--- Top 12 DiagnosisCategory ---")
    for k, v in counts["DiagnosisCategory"].most_common(12):
        print(f"  {v:>7,}  {k!r}")

    print("\n--- Top 12 TreatmentCategory ---")
    for k, v in counts["TreatmentCategory"].most_common(12):
        print(f"  {v:>7,}  {k!r}")


if __name__ == "__main__":
    sys.exit(main())

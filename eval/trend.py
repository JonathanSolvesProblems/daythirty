"""Overturn rate by year, to check whether the 2025-26 rate is a real trend or an artifact."""

import csv
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(10_000_000)
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "imr-determinations.csv"
OVERTURNED = "Overturned Decision of Health Plan"


def main() -> None:
    by_year = defaultdict(lambda: [0, 0])
    by_year_type = defaultdict(lambda: [0, 0])
    with RAW.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            det = row["Determination"]
            if det not in (OVERTURNED, "Upheld Decision of Health Plan"):
                continue
            y = row["ReportYear"]
            cell = by_year[y]
            cell[0] += det == OVERTURNED
            cell[1] += 1
            t = by_year_type[(y, row["Type"])]
            t[0] += det == OVERTURNED
            t[1] += 1

    print("year   n      overturn%")
    for y in sorted(by_year):
        o, n = by_year[y]
        print(f"{y}  {n:>6,}   {o/n:6.2%}")

    print("\nby denial grounds, recent years")
    print("year  grounds                        n      overturn%")
    for y in [str(v) for v in range(2021, 2027)]:
        for t in ("Medical Necessity", "Experimental/Investigational", "Urgent Care"):
            cell = by_year_type.get((y, t))
            if not cell:
                continue
            o, n = cell
            print(f"{y}  {t:<28} {n:>5,}   {o/n:6.2%}")


if __name__ == "__main__":
    sys.exit(main())

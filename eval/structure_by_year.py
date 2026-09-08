"""Template coverage by year.

The corpus spans 25 years and DMHC clearly changed its publication format over that
time. What matters is coverage in the held-out years (2025-26) and in the years the
precedent index draws from, not the lifetime average.
"""

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(10_000_000)
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "imr-determinations.csv"

CREDS = re.compile(r"Credentials/Qualifications:", re.I)
RESULT = re.compile(r"Final Result:", re.I)
# Looser: any "board-certified in X" phrasing, however the sentence ends.
SPECIALTY = re.compile(r"board[‐‑‒–—\-]?certified in\s+([^.]{3,160})", re.I)


def main() -> None:
    stats = defaultdict(lambda: {"n": 0, "creds": 0, "result": 0, "spec": 0, "len": 0})

    with RAW.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            text = row.get("Findings") or ""
            y = row["ReportYear"]
            s = stats[y]
            s["n"] += 1
            s["len"] += len(text)
            if CREDS.search(text):
                s["creds"] += 1
            if RESULT.search(text):
                s["result"] += 1
            if SPECIALTY.search(text):
                s["spec"] += 1

    print("year      n    avg_len   Final Result:   Credentials:   specialty")
    for y in sorted(stats):
        s = stats[y]
        n = s["n"]
        print(
            f"{y}  {n:>5,}  {s['len']//max(n,1):>7,}   "
            f"{s['result']/n:>11.1%}   {s['creds']/n:>11.1%}   {s['spec']/n:>8.1%}"
        )


if __name__ == "__main__":
    sys.exit(main())

"""Why does verdict text survive the strip? Look at the actual leaking narratives."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daythirty.precedent import reasoning_of  # noqa: E402

TRAIN = ROOT / "data" / "split" / "train.jsonl"

PATTERNS = {
    "should be overturned": r"should be overturned",
    "should be upheld": r"should be upheld",
    "Final Result": r"Final Result",
    "denial should": r"denial should",
    "trailing not-med-nec": r"is not medically necessary for the treatment of this patient\.$",
}


def main() -> None:
    which = Counter()
    samples: dict[str, str] = {}
    n = 0
    for line in TRAIN.open(encoding="utf-8"):
        r = json.loads(line)
        f = r.get("findings", "")
        if not f:
            continue
        n += 1
        stripped = reasoning_of(f)
        for name, pat in PATTERNS.items():
            if re.search(pat, stripped, re.I):
                which[name] += 1
                if name not in samples:
                    idx = re.search(pat, stripped, re.I).start()
                    samples[name] = stripped[max(0, idx - 260):idx + 160]

    print(f"narratives checked: {n:,}\n")
    print("which phrase survives:")
    for k, v in which.most_common():
        print(f"  {v:>6,}  {k}")

    print("\n" + "=" * 78)
    for k, s in samples.items():
        print(f"\n--- sample where '{k}' survived ---")
        print(s.replace("\n", " "))


if __name__ == "__main__":
    sys.exit(main())

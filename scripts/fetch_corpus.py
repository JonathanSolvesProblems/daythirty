"""Fetch the California DMHC Independent Medical Review corpus.

The corpus is public data published by the state, so it is downloaded rather than
committed. A clean clone runs this first and every later script works.

  python scripts/fetch_corpus.py

Source: California Health and Human Services Open Data Portal
  https://data.chhs.ca.gov/dataset/independent-medical-review-imr-determinations-trend
Published by the Department of Managed Health Care.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

URL = (
    "https://data.chhs.ca.gov/dataset/b79b3447-4c10-4ae6-84e2-1076f83bb24e/resource/"
    "3340c5d7-4054-4d03-90e0-5f44290ed095/download/"
    "independent-medical-review-imr-determinations-trends.csv"
)

DEST = Path(__file__).resolve().parents[1] / "data" / "raw" / "imr-determinations.csv"


def main() -> int:
    if DEST.exists():
        print(f"already present: {DEST} ({DEST.stat().st_size / 1e6:.1f} MB)")
        print("delete it to re-download")
        return 0

    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading from data.chhs.ca.gov ...")
    try:
        with urllib.request.urlopen(URL, timeout=300) as resp, DEST.open("wb") as fh:
            digest = hashlib.sha256()
            while chunk := resp.read(1 << 20):
                fh.write(chunk)
                digest.update(chunk)
    except Exception as exc:  # noqa: BLE001
        if DEST.exists():
            DEST.unlink()
        print(f"download failed: {exc}", file=sys.stderr)
        print(
            "The dataset is also reachable through the portal page linked in this "
            "file's docstring.",
            file=sys.stderr,
        )
        return 1

    size = DEST.stat().st_size
    print(f"saved {DEST} ({size / 1e6:.1f} MB)")
    print(f"sha256 {digest.hexdigest()}")
    print(
        "\nNote: the state republishes this file as new determinations are adopted, so "
        "the hash moves over time. It is printed so a given run can be pinned, not as a "
        "fixed expected value."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

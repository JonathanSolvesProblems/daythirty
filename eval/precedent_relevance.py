"""Are the retrieved exemplars actually about this case, or only superficially similar?

Coverage (eval/precedent_coverage.py) says whether an exemplar EXISTS for a held-out
denial. This measures whether the exemplars the agent retrieves RESEMBLE the case, and
it is graded by something the agent never sees: the state physician's own findings for
that held-out case, which are stripped from test.jsonl and read here straight from the
raw corpus.

For every held-out denial with a usable reviewer narrative:

  matched     the exemplars `find_precedent` returns, exactly as the agent gets them
  category    the same number of random overturned cases sharing only the diagnosis
              category (what "superficially similar" looks like in this corpus)
  random      the same number of random overturned cases from anywhere in the pool

Each exemplar's reasoning is compared to the held-out reviewer's reasoning by TF-IDF
cosine similarity over the train narratives, with the verdict boilerplate cut from both
sides so the comparison is about clinical reasoning, not about the words "medically
necessary". Same pool, same k, same scorer for all three; only the selection differs.

Two numbers come out. The mean similarity of each selection, and the share of cases
where the matched exemplars beat each control. The flip side is reported too: the share
where taxonomy matching did NO better than a same-category random draw is exactly the
"superficial similarity" a reader would worry about, in a number rather than a caveat.

    python eval/precedent_relevance.py
"""

from __future__ import annotations

import csv
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daythirty.precedent import (  # noqa: E402
    MIN_EXEMPLAR_SCORE, OVERTURNED, PrecedentIndex, is_clean_reasoning, reasoning_of,
)

csv.field_size_limit(10_000_000)
RAW = ROOT / "data" / "raw" / "imr-determinations.csv"
OUT = ROOT / "eval" / "precedent_relevance_report.json"
TEST_FROM_YEAR = 2025
K = 3
SEED = 20260913
MIN_CHARS = 120

_TOKEN = re.compile(r"[a-z][a-z\-]{2,}")
# Words that appear in nearly every IMR narrative and say nothing about the case.
_STOP = set("""
the and for that with this was were are has have had not from which who been being
into than then there their they them its his her she him you your our are also may
can will would should could about after before over under between both each other
any all more most such into upon within without because while where when what
patient patients enrollee enrollees plan health reviewer reviewers physician
physicians request requested requests treatment treatments medical medically
necessary necessity case cases denial denied review reviewed determination
""".split())


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


class Tfidf:
    """Plain TF-IDF with cosine, fitted on the precedent pool's narratives."""

    def __init__(self, docs: list[str]) -> None:
        df: Counter = Counter()
        for d in docs:
            df.update(set(tokens(d)))
        n = len(docs)
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}

    def vec(self, text: str) -> dict[str, float]:
        tf = Counter(tokens(text))
        if not tf:
            return {}
        v = {t: (1 + math.log(c)) * self.idf.get(t, 1.0) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    @staticmethod
    def cos(a: dict[str, float], b: dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(t, 0.0) for t, x in a.items())


def held_out_cases() -> list[dict]:
    """Held-out denials with the reviewer's findings attached, from the raw corpus."""
    rows = []
    with RAW.open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            try:
                year = int(row["ReportYear"])
            except (TypeError, ValueError):
                continue
            if year < TEST_FROM_YEAR:
                continue
            if row["Determination"] not in ("Overturned Decision of Health Plan",
                                            "Upheld Decision of Health Plan"):
                continue
            reasoning = reasoning_of(row.get("Findings") or "")
            if len(reasoning) < MIN_CHARS:
                continue
            case = {f: (row.get(f) or "").strip() for f in (
                "DiagnosisCategory", "DiagnosisSubCategory", "TreatmentCategory",
                "TreatmentSubCategory", "Type", "AgeRange", "PatientGender", "IMRType")}
            rows.append({"year": year, "case": case, "reasoning": reasoning})
    return rows


def main() -> int:
    rng = random.Random(SEED)
    index = PrecedentIndex()

    # The pool the agent draws exemplars from: overturned, clean, long enough to argue from.
    pool = []
    for r in index.records:
        if r["label"] != OVERTURNED:
            continue
        reasoning = reasoning_of(r.get("findings", ""))
        if len(reasoning) < MIN_CHARS or not is_clean_reasoning(reasoning):
            continue
        pool.append({"case": r["case"], "reasoning": reasoning})
    by_category: dict[str, list[dict]] = defaultdict(list)
    for p in pool:
        by_category[p["case"]["DiagnosisCategory"]].append(p)

    tfidf = Tfidf([p["reasoning"] for p in pool])
    pool_vecs = {id(p): tfidf.vec(p["reasoning"]) for p in pool}

    held = held_out_cases()
    scored = 0
    sums = {"matched": 0.0, "category": 0.0, "random": 0.0}
    wins = {"vs_category": 0, "vs_random": 0, "ties_or_losses_vs_category": 0}
    per_tier: dict[str, list[float]] = defaultdict(list)
    skipped_no_exemplar = 0

    for h in held:
        res = index.query(h["case"], k=K)
        if not res.exemplars:
            skipped_no_exemplar += 1
            continue
        target = tfidf.vec(h["reasoning"])
        k = len(res.exemplars)

        m = sum(Tfidf.cos(target, tfidf.vec(e.reasoning)) for e in res.exemplars) / k

        same_cat = [p for p in by_category.get(h["case"]["DiagnosisCategory"], [])]
        if len(same_cat) < k:
            same_cat = pool
        c = sum(Tfidf.cos(target, pool_vecs[id(p)]) for p in rng.sample(same_cat, k)) / k
        r = sum(Tfidf.cos(target, pool_vecs[id(p)]) for p in rng.sample(pool, k)) / k

        scored += 1
        sums["matched"] += m
        sums["category"] += c
        sums["random"] += r
        wins["vs_category"] += m > c
        wins["vs_random"] += m > r
        wins["ties_or_losses_vs_category"] += m <= c
        per_tier[res.exemplars[0].tier].append(m - c)

    means = {k_: v / scored for k_, v in sums.items()}
    report = {
        "grader": "the state physician reviewer's own findings for each held-out case, "
                  "never shown to the agent; TF-IDF cosine over train narratives",
        "held_out_with_narrative": len(held),
        "scored": scored,
        "skipped_no_exemplar": skipped_no_exemplar,
        "k": K,
        "min_exemplar_score": MIN_EXEMPLAR_SCORE,
        "pool_size": len(pool),
        "mean_similarity": {k_: round(v, 4) for k_, v in means.items()},
        "matched_beats_category_pct": round(100 * wins["vs_category"] / scored, 1),
        "matched_beats_random_pct": round(100 * wins["vs_random"] / scored, 1),
        "no_better_than_category_pct": round(100 * wins["ties_or_losses_vs_category"] / scored, 1),
        "lift_over_category": round(means["matched"] - means["category"], 4),
        "lift_over_random": round(means["matched"] - means["random"], 4),
        "mean_lift_over_category_by_tier": {
            t: {"n": len(v), "lift": round(sum(v) / len(v), 4)} for t, v in sorted(per_tier.items())
        },
        "seed": SEED,
    }
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"held-out with reviewer narrative: {len(held):,}   scored: {scored:,}   "
          f"no exemplar (skipped): {skipped_no_exemplar:,}")
    print(f"pool of overturned, clean exemplars: {len(pool):,}\n")
    print("mean similarity to the reviewer's own reasoning for this case")
    for k_, v in means.items():
        print(f"  {k_:<10} {v:.4f}")
    print(f"\nmatched beats same-category random: {report['matched_beats_category_pct']}% of cases")
    print(f"matched beats random:               {report['matched_beats_random_pct']}% of cases")
    print(f"no better than same-category random: {report['no_better_than_category_pct']}% of cases")
    print("\nlift over same-category random, by tier of the best exemplar")
    for t, d in report["mean_lift_over_category_by_tier"].items():
        print(f"  {d['n']:>6,}  {d['lift']:+.4f}  {t}")
    print(f"\nwritten {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

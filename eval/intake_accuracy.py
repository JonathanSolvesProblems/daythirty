"""Can Nova recover California's own classification from a denial letter?

Every published case already carries a category the state assigned. So: render a real
held-out case as the letter a plan would have sent, written only in specific clinical
language, hand it to Nova, and check whether the category it returns is the one
California recorded.

The letter never contains a category name. Recovering "Skin Subcutaneous" from "plaque
psoriasis" is inference against a label the state authored years ago and that I cannot
influence.

Two scores are reported, because DMHC relabelled its own taxonomy over the years and
several categories are duplicates in different words ("Resp System" and "Respiratory
System" both exist). Strict exact match is the honest floor; the equivalence-aware score
uses the synonym table below, which is published here rather than hidden.

  python eval/intake_accuracy.py --runs 40
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daythirty.intake import parse_denial_letter, render_denial_letter  # noqa: E402

TEST = ROOT / "data" / "split" / "test.jsonl"

# DMHC's own label drift. Each group is one clinical concept the state has written more
# than one way across the years. Grouping them is a judgement call, so it is stated
# explicitly and the strict score is reported alongside.
EQUIVALENT = [
    {"Resp System", "Respiratory System"},
    {"Endo/Metabolic", "Endocrine/Metabolic"},
    {"Digest System", "Digestive System/ GI"},
    {"Musculoskeletal", "Orth/Musculoskeletal"},
    {"Skin Disorders", "Skin Subcutaneous"},
    {"Infectious Disease", "Infect/Parasit Dx"},
    {"Mental Disorder", "Mental Behav Neur"},
    {"Circulatory System", "Cardiac/Circ Problem"},
    {"Genitourinary Sys", "GU/ Kidney Disorder"},
    {"Diseases of Blood", "Blood Related Disord"},
    {"Nervous System", "CNS/ Neuromusc Dis"},
    {"Neoplasms (Tumor)", "Cancer"},
    {"Pregnancy Childbirth", "Pregnancy/Childbirth", "OB-GYN/ Pregnancy"},
    {"Ear and Mastoid", "Ears/Nose/Throat"},
    {"Disease Eye Adnexa", "Vision"},
    {"Morbid Obesity", "Endocrine/Metabolic", "Endo/Metabolic"},
    {"Injury Poison Oth", "Trauma/ Injuries"},
]

# The same drift exists on the treatment side, found the same way: by reading the misses
# rather than by assuming. "Ortho Proc Serv" and "Orthopedic Proc" are one concept.
EQUIVALENT_TX = [
    {"Ortho Proc Serv", "Orthopedic Proc"},
    {"Diag Imag & Screen", "Radio Proc", "Radiology"},
    {"Acute Med Svc Inpt", "Eval and Mgmt"},
    {"Rehab/ Svc - Outpt", "Rehab/ Svc - Inpt"},
    {"Medicine Serv Proc", "Pharmacy"},
]
EQUIVALENT_ALL = EQUIVALENT + EQUIVALENT_TX


def equivalent(a: str, b: str) -> bool:
    if a == b:
        return True
    return any(a in g and b in g for g in EQUIVALENT_ALL)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=40)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    rows = [json.loads(line) for line in TEST.open(encoding="utf-8")]
    sample = [rows[(i * 79) % len(rows)] for i in range(args.runs)]
    denial = (date.today() - timedelta(days=95)).isoformat()

    lock = threading.Lock()
    stats = Counter()
    misses: list[str] = []
    tx_misses: list[str] = []
    corrections = Counter()

    def work(rec: dict) -> None:
        c = rec["case"]
        letter = render_denial_letter(c, denial)
        try:
            got = parse_denial_letter(letter)
        except Exception as exc:  # noqa: BLE001
            with lock:
                stats["error"] += 1
                if stats["error"] <= 3:
                    print(f"  error: {type(exc).__name__}: {str(exc)[:120]}")
            return

        with lock:
            stats["n"] += 1
            for corr in got.corrections:
                corrections[corr.split(" ")[0]] += 1

            dx_exact = got.diagnosis_category == c["DiagnosisCategory"]
            dx_equiv = equivalent(got.diagnosis_category, c["DiagnosisCategory"])
            tx_exact = got.treatment_category == c["TreatmentCategory"]
            tx_equiv = equivalent(got.treatment_category, c["TreatmentCategory"])
            gr_exact = got.grounds == c["Type"]

            stats["dx_exact"] += dx_exact
            stats["dx_equiv"] += dx_equiv
            stats["tx_exact"] += tx_exact
            stats["tx_equiv"] += tx_equiv
            stats["grounds"] += gr_exact
            stats["date"] += (got.denial_date == denial)
            stats["dxsub"] += (got.diagnosis_subcategory == c["DiagnosisSubCategory"])
            stats["txsub"] += (got.treatment_subcategory == c["TreatmentSubCategory"])

            if not dx_equiv and len(misses) < 12:
                misses.append(
                    f"    DX  {c['DiagnosisSubCategory'][:26]:<26} "
                    f"state={c['DiagnosisCategory']:<22} nova={got.diagnosis_category}"
                )
            if not tx_equiv and len(tx_misses) < 14:
                tx_misses.append(
                    f"    TX  {c['TreatmentSubCategory'][:26]:<26} "
                    f"state={c['TreatmentCategory']:<22} nova={got.treatment_category}"
                )

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(work, sample))

    n = stats["n"]
    if not n:
        print("no successful extractions")
        return 1

    print(f"\n{'=' * 74}")
    print(f"letters read by Nova: {n}   (errors: {stats['error']})")
    print(f"{'=' * 74}")
    print(f"  diagnosis category, exact match to California's label : "
          f"{stats['dx_exact']}/{n}  ({stats['dx_exact']/n:.1%})")
    print(f"  diagnosis category, allowing DMHC's own synonyms      : "
          f"{stats['dx_equiv']}/{n}  ({stats['dx_equiv']/n:.1%})")
    print(f"  treatment category, exact match                       : "
          f"{stats['tx_exact']}/{n}  ({stats['tx_exact']/n:.1%})")
    print(f"  treatment category, allowing DMHC's own synonyms      : "
          f"{stats['tx_equiv']}/{n}  ({stats['tx_equiv']/n:.1%})")
    print(f"  diagnosis SUBcategory recovered exactly                : "
          f"{stats['dxsub']}/{n}  ({stats['dxsub']/n:.1%})")
    print(f"  treatment SUBcategory recovered exactly                : "
          f"{stats['txsub']}/{n}  ({stats['txsub']/n:.1%})")
    print(f"  denial grounds, exact match                           : "
          f"{stats['grounds']}/{n}  ({stats['grounds']/n:.1%})")
    print(f"  denial date read off the letter                       : "
          f"{stats['date']}/{n}  ({stats['date']/n:.1%})")

    if corrections:
        print(f"\n  off-taxonomy values Nova returned, snapped deterministically:")
        for k, v in corrections.most_common():
            print(f"    {v:>3}x  {k}")

    if misses or tx_misses:
        print(f"\n  misses (California's label vs Nova's):")
        for m in misses + tx_misses:
            print(m)

    report = {
        "letters": n,
        "errors": stats["error"],
        "model": "us.amazon.nova-lite-v1:0",
        "diagnosis_category_exact": [stats["dx_exact"], n],
        "diagnosis_category_equivalent": [stats["dx_equiv"], n],
        "treatment_category_exact": [stats["tx_exact"], n],
        "grounds_exact": [stats["grounds"], n],
        "denial_date_exact": [stats["date"], n],
        "note": (
            "Ground truth is the category California assigned to each published case. "
            "The rendered letter contains only the specific condition and treatment, "
            "never a category name, so recovering the category is inference against a "
            "label the state authored and I cannot influence."
        ),
    }
    (ROOT / "eval" / "intake_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(f"\nwritten: eval/intake_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

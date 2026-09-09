"""Run Day Thirty against a real published denial, end to end.

Nothing here is seeded. The case facts come from a held-out 2025-26 record in
California's own published corpus, the precedent comes from decisions the state
published in 2016-2024, the deadline comes from the statute, and the letter is written
live by the model on Bedrock.

  python run_agent.py               # interactive: it stops and asks you to approve
  python run_agent.py --approve     # auto-approve, for a scripted run
  python run_agent.py --case 7      # a specific held-out case
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from daythirty.agent import build_agent  # noqa: E402
from daythirty.intake import parse_denial_letter, render_denial_letter  # noqa: E402
from daythirty.precedent import PrecedentIndex  # noqa: E402

TEST = ROOT / "data" / "split" / "test.jsonl"
RULE = "=" * 78


def pick_case(want: int | None) -> dict:
    idx = PrecedentIndex()
    rows = [json.loads(line) for line in TEST.open(encoding="utf-8")]
    usable = [r for r in rows if idx.query(r["case"], k=1).exemplars]
    return usable[(want or 0) % len(usable)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", type=int, default=0)
    ap.add_argument("--approve", action="store_true", help="skip the prompt and approve")
    args = ap.parse_args()

    rec = pick_case(args.case)
    c = rec["case"]

    denial = date.today() - timedelta(days=95)
    grievance = denial + timedelta(days=9)

    letter = render_denial_letter(c, denial.isoformat())

    print(RULE)
    print("THE DENIAL LETTER")
    print(RULE)
    print(letter)

    print(RULE)
    print("AMAZON NOVA READS IT")
    print(RULE)
    intake = parse_denial_letter(letter)
    print(f"  condition read from the letter : {intake.condition_text}")
    print(f"  treatment read from the letter : {intake.treatment_text}")
    print(f"  grounds                        : {intake.grounds}")
    print(f"  denial date                    : {intake.denial_date}")
    print(f"  -> California's category       : {intake.diagnosis_category} / "
          f"{intake.treatment_category}")
    for corr in intake.corrections:
        print(f"  correction: {corr}")
    print(f"\n  the state's own filing for this case: "
          f"{c['DiagnosisCategory']} / {c['TreatmentCategory']}")
    print(f"  the state's determination: "
          f"{'OVERTURNED' if rec['label'] else 'UPHELD'}   (the agent cannot see this)")
    print()

    agent = build_agent()
    prompt = f"""My health plan denied coverage and I want to appeal to the state.

Denial letter date: {intake.denial_date or denial.isoformat()}
I filed a grievance with my plan on: {grievance.isoformat()}
My plan has not answered the grievance.

What was denied, read from my denial letter:
- Diagnosis category: {intake.diagnosis_category}
- Diagnosis: {intake.diagnosis_subcategory or intake.condition_text}
- Treatment category: {intake.treatment_category}
- Treatment refused: {intake.treatment_subcategory or intake.treatment_text}
- The plan's stated grounds: {intake.grounds}
- Me: {c['AgeRange']}, {c['PatientGender']}

Work out my deadline, find out how cases like mine were actually decided, and draft
my appeal."""

    result = agent(prompt)

    if not result.interrupts:
        print("\n" + RULE)
        print("NO APPROVAL GATE WAS REACHED. The agent did not try to file.")
        print(RULE)
        return 1

    itr = result.interrupts[0]
    reason = itr.reason if isinstance(itr.reason, dict) else {}

    print("\n" + RULE)
    print("STOPPED. NOTHING HAS BEEN FILED.")
    print(RULE)
    print(f"  action  : {reason.get('action')}")
    print(f"  deadline: {reason.get('deadline')}")
    print(f"  summary : {reason.get('summary')}")
    print()

    if args.approve:
        approved, note = True, "approved non-interactively"
        print("  [--approve] approving without prompting")
    else:
        answer = input("  File this appeal? [y/N] ").strip().lower()
        approved = answer in {"y", "yes"}
        note = "approved by the patient" if approved else "declined by the patient"

    resumed = agent([{
        "interruptResponse": {
            "interruptId": itr.id,
            "response": {"approved": approved, "note": note},
        }
    }])

    print("\n" + RULE)
    print("RESULT")
    print(RULE)
    print(resumed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

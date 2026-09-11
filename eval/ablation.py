"""What does each piece actually contribute? Switch it off and measure the difference.

Every entry at a sponsored hackathon asserts its tools were essential. This measures it.
The same model, the same denials, the same prompt, with one tool removed at a time:

  Arm A  full agent: statute engine + California's published record + the gate
  Arm B  the record switched off: the model argues from its own knowledge
  Arm C  the statute engine switched off: the model computes the deadline itself

Two things are scored, and both have an answer the model cannot influence.

  Deadline error   The statute fixes the date. Arm C's date is compared to it, in days.
                   Being late by any margin loses the right to appeal.
  Unsourced claims Arm B has no record to cite. Every percentage it writes is therefore
                   a number it could not have known for this case. Counted, not judged.

  python eval/ablation.py --runs 8
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strands.hooks import AfterToolCallEvent  # noqa: E402

from daythirty.agent import (  # noqa: E402
    SYSTEM_PROMPT,
    build_agent,
    compute_filing_deadline,
    file_appeal,
    find_precedent,
)
from daythirty.deadlines import imr_filing_deadline  # noqa: E402
from daythirty.precedent import PrecedentIndex  # noqa: E402

TEST = ROOT / "data" / "split" / "test.jsonl"

# No trailing \b: "%" is not a word character, so a boundary after it never matches a
# following space. That mistake reported 0/0 claims on letters full of percentages.
PCT = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent\b)", re.I)
ISO = re.compile(r"\b(20\d\d-\d\d-\d\d)\b")

# The system prompt uses backslash continuations, so at runtime each numbered step is a
# single line with no newlines in it. Substitutions therefore match on the step's opening
# words and replace through to the next step. Each one asserts it actually changed the
# text, because a silent no-op here would run the ablated arm with the full prompt and
# a missing tool, and measure confusion instead of contribution.


def _swap_step(prompt: str, step_start: str, replacement: str) -> str:
    pattern = re.compile(re.escape(step_start) + r".*?(?=\n\n\d\. |\n\nHard rules:)", re.S)
    out, n = pattern.subn(replacement, prompt, count=1)
    assert n == 1, f"ablation prompt substitution did not match: {step_start!r}"
    return out


# Arm B: the same instructions minus the record, so the only variable is the tool.
NO_RECORD_PROMPT = _swap_step(
    SYSTEM_PROMPT,
    "2. Find out how comparable denials were actually decided",
    "2. There is no precedent tool available. Argue from your own knowledge of how "
    "independent medical reviews of denials like this are decided, including any "
    "overturn rates you believe apply.",
)

# Arm C: told the rule in words, the way a careful person would look it up, and asked to
# compute the date itself.
NO_ENGINE_PROMPT = _swap_step(
    SYSTEM_PROMPT,
    "1. Compute the filing deadline with `compute_filing_deadline`",
    "1. Compute the filing deadline yourself. Under Cal. Health & Safety Code section "
    "1374.30 an enrollee may apply for independent medical review within six months of "
    "the qualifying event, and the enrollee is not required to stay in the plan's "
    "grievance process for more than 30 days. State the deadline as an ISO date, "
    "YYYY-MM-DD, on its own line beginning 'DEADLINE:'.",
)


def prompt_for(c: dict, denial: date, grievance: date, answered: date | None = None) -> str:
    status = (
        f"My plan answered the grievance on {answered.isoformat()} and upheld the denial."
        if answered else "My plan has not answered the grievance."
    )
    return f"""My health plan denied coverage and I want to appeal to the state.

Denial letter date: {denial.isoformat()}
I filed a grievance with my plan on: {grievance.isoformat()}
{status}

What was denied:
- Diagnosis category: {c['DiagnosisCategory']}
- Diagnosis: {c['DiagnosisSubCategory']}
- Treatment category: {c['TreatmentCategory']}
- Treatment refused: {c['TreatmentSubCategory']}
- The plan's stated grounds: {c['Type']}
- Me: {c['AgeRange']}, {c['PatientGender']}

Work out my deadline, find out how cases like mine were actually decided, and draft
my appeal."""


def letter_from(result) -> str:
    if result.interrupts and isinstance(result.interrupts[0].reason, dict):
        return result.interrupts[0].reason.get("letter", "") or ""
    return str(result)


def run_arm(name: str, tools: list, system_prompt: str, cases: list[dict],
            denial: date, grievance: date, answered: date | None = None) -> list[dict]:
    out = []
    for i, rec in enumerate(cases):
        c = rec["case"]
        chunks: list[str] = []

        def capture(event: AfterToolCallEvent) -> None:
            try:
                chunks.append(json.dumps(event.result, default=str))
            except Exception:  # noqa: BLE001
                chunks.append(str(event.result))

        agent = build_agent(tools=tools, system_prompt=system_prompt)
        agent.add_hook(capture, AfterToolCallEvent)
        t0 = time.time()
        try:
            result = agent(prompt_for(c, denial, grievance, answered))
        except Exception as exc:  # noqa: BLE001
            print(f"  {name} run {i+1}: ERROR {type(exc).__name__}")
            continue
        text = letter_from(result) + "\n" + str(result)
        out.append({
            "case": c,
            "text": text,
            "context": "\n".join(chunks),
            "gate": bool(result.interrupts),
            "seconds": round(time.time() - t0, 1),
        })
        print(f"  {name} run {i+1}: {'gate' if result.interrupts else 'no gate'} "
              f"{time.time()-t0:5.1f}s  [{c['DiagnosisSubCategory'][:24]}]")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=8)
    args = ap.parse_args()

    idx = PrecedentIndex()
    rows = [json.loads(line) for line in TEST.open(encoding="utf-8")]
    usable = [r for r in rows if idx.query(r["case"], k=1).exemplars]
    cases = [usable[(i * 173) % len(usable)] for i in range(args.runs)]

    denial = date.today() - timedelta(days=95)
    grievance = denial + timedelta(days=9)
    truth = imr_filing_deadline(denial, grievance).deadline

    # Second timeline for the engine ablation: the plan sat on the grievance for 120 days
    # and then upheld the denial. Under § 1374.30(j)(3) the clock still started on day 30,
    # so the true deadline is unchanged. Counting from the plan's answer, which is what a
    # person naturally does, lands roughly 90 days late and forfeits the appeal.
    answered = grievance + timedelta(days=120)
    truth_late = imr_filing_deadline(denial, grievance, plan_upheld_on=answered).deadline
    assert truth_late == truth, "the qualifying event is day 30 either way"

    print(f"cases: {len(cases)}   statutory deadline: {truth}")
    print(f"late-answer timeline: plan answered {answered}, deadline still {truth_late}\n")

    print("ARM A: full agent")
    a = run_arm("A", [compute_filing_deadline, find_precedent, file_appeal],
                SYSTEM_PROMPT, cases, denial, grievance)
    print("\nARM B: California's record switched off")
    b = run_arm("B", [compute_filing_deadline, file_appeal],
                NO_RECORD_PROMPT, cases, denial, grievance)
    print("\nARM C1: statute engine switched off, plan silent")
    c_ = run_arm("C1", [find_precedent, file_appeal],
                 NO_ENGINE_PROMPT, cases, denial, grievance)
    print("\nARM C2: statute engine switched off, plan answered on day 120")
    c2 = run_arm("C2", [find_precedent, file_appeal],
                 NO_ENGINE_PROMPT, cases, denial, grievance, answered)

    # --- record ablation --------------------------------------------------------------
    def pct_claims(r: dict) -> list[str]:
        body = re.sub(r"\[[^\]]*\]", " ", r["text"])
        return [m.group(0) for m in PCT.finditer(body)]

    def sourced(claim: str, ctx: str) -> bool:
        m = re.match(r"(\d+(?:\.\d+)?)", claim)
        want = float(m.group(1))
        for d in re.findall(r"\b0?\.\d+\b", ctx):
            if round(float(d) * 100) == round(want) or abs(float(d)*100 - want) < 0.01:
                return True
        return claim.lower().replace(" ", "") in ctx.lower().replace(" ", "")

    a_claims = [x for r in a for x in pct_claims(r)]
    a_sourced = sum(1 for r in a for x in pct_claims(r) if sourced(x, r["context"]))
    b_claims = [x for r in b for x in pct_claims(r)]
    # Arm B has no record, so a percentage it writes has no source it was given.
    b_letters_with_pct = sum(1 for r in b if pct_claims(r))

    # --- engine ablation --------------------------------------------------------------
    def model_dates(arm: list[dict], exclude: set[str]) -> list[int]:
        out = []
        for r in arm:
            m = re.search(r"DEADLINE:\s*(20\d\d-\d\d-\d\d)", r["text"])
            found = [d for d in ISO.findall(r["text"]) if d not in exclude]
            pick = m.group(1) if m else (found[-1] if found else None)
            if pick:
                try:
                    out.append((datetime.strptime(pick, "%Y-%m-%d").date() - truth).days)
                except ValueError:
                    pass
        return out

    known = {denial.isoformat(), grievance.isoformat(), answered.isoformat()}
    c_dates = model_dates(c_, known)
    c2_dates = model_dates(c2, known)

    print(f"\n{'=' * 74}")
    print("ABLATION 1: California's published record")
    print(f"{'=' * 74}")
    print(f"  with the record    : {a_sourced}/{len(a_claims)} percentage claims sourced "
          f"to the record ({(a_sourced/len(a_claims)) if a_claims else 0:.0%})")
    print(f"  record switched off: {len(b_claims)} percentage claims across "
          f"{len(b)} letters, {b_letters_with_pct} letters assert a rate, "
          f"0 of them sourced (there is no source)")
    if b_claims:
        print(f"  rates the model asserted with nothing to cite: "
              f"{', '.join(sorted(set(b_claims))[:8])}")

    def summarise(label: str, dates: list[int]) -> dict:
        late = sum(1 for d in dates if d > 0)
        early = sum(1 for d in dates if d < 0)
        exact = sum(1 for d in dates if d == 0)
        print(f"  {label}: {len(dates)} dates computed by the model")
        print(f"    exact: {exact}   early: {early}   LATE: {late}")
        print(f"    error in days: {sorted(dates)}")
        if late:
            print("    ^ late means the filing window is missed and the appeal is lost")
        return {"error_days": sorted(dates), "late": late, "early": early, "exact": exact}

    print(f"\n{'=' * 74}")
    print("ABLATION 2: the statute engine")
    print(f"{'=' * 74}")
    print(f"  statutory deadline, both timelines: {truth}")
    eng1 = summarise("engine off, plan silent      ", c_dates) if c_dates else {}
    eng2 = summarise("engine off, plan answered late", c2_dates) if c2_dates else {}

    report = {
        "runs": args.runs,
        "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "record_ablation": {
            "with_record": {"pct_claims": len(a_claims), "sourced": a_sourced},
            "without_record": {"pct_claims": len(b_claims),
                               "letters_asserting_a_rate": b_letters_with_pct,
                               "sourced": 0,
                               "asserted_rates": sorted(set(b_claims))},
        },
        "engine_ablation": {
            "statutory_deadline": truth.isoformat(),
            "plan_silent": eng1,
            "plan_answered_day_120": eng2,
        },
        "gate_reached": {"A": sum(r["gate"] for r in a), "B": sum(r["gate"] for r in b),
                         "C1": sum(r["gate"] for r in c_), "C2": sum(r["gate"] for r in c2)},
    }
    (ROOT / "eval" / "ablation_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwritten: eval/ablation_report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

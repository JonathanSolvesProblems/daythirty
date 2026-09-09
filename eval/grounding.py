"""Is every specific claim in the drafted appeal actually in the record it was given?

This is a faithfulness measurement, and it is deliberately deterministic. No model grades
another model here. The procedure:

  1. Capture, via a Strands hook, exactly what the tools returned to the agent. That is
     the entire evidence base it was allowed to argue from: California's published
     reviewer reasoning, the cohort rate, and the statutory deadline computation.
  2. Extract every checkable specific from the letter the model wrote: numeric claims
     with units or percentages, and named authorities.
  3. Check each one against the captured context.

Anything specific in the letter that is absent from the context is unsupported. It may
still be true, since real clinical conventions exist outside this corpus, but the agent
did not get it from the record and cannot cite it. Reporting those honestly is the point;
a check that can never mark the project down is not a check.

  python eval/grounding.py --runs 8
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strands.hooks import AfterToolCallEvent  # noqa: E402

from daythirty.agent import build_agent  # noqa: E402
from daythirty.precedent import PrecedentIndex  # noqa: E402

TEST = ROOT / "data" / "split" / "test.jsonl"

# A number carrying a unit or a percent sign is a factual claim about the world.
# Dates and section numbers are excluded: those come from the deadline tool and are
# checked separately by the deadline engine's own tests.
NUMERIC = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|percent|mg\b|mcg\b|ml\b|milligrams?)",
    re.I,
)

# Real, externally-defined clinical authorities. This list is not my invention: these
# are the bodies whose guidelines actually govern US coverage decisions, and the same
# set is used in eval/inspect_findings.py against the reviewers' own narratives.
# Matching against a fixed roster is far more precise than harvesting capitalised
# phrases, which turned out to catch letter headings like "Medical History".
AUTHORITIES = [
    "American Academy of Dermatology", "National Psoriasis Foundation",
    "American College of Rheumatology", "National Comprehensive Cancer Network",
    "American Society of Addiction Medicine", "American Academy of Pediatrics",
    "American College of Obstetricians", "American Diabetes Association",
    "American Heart Association", "American College of Cardiology",
    "American Psychiatric Association", "American Academy of Neurology",
    "American College of Radiology", "American Urological Association",
    "American Thoracic Society", "Infectious Diseases Society of America",
    "Food and Drug Administration", "Centers for Medicare", "Cochrane",
    "InterQual", "Milliman", "MCG", "UpToDate", "NCCN", "ASAM", "AAD", "FDA",
    "World Health Organization", "National Institutes of Health",
]


def make_capture() -> tuple[list[str], object]:
    """A hook that records exactly what each tool handed back to the model.

    The registry reads `__name__` off the callback, so this has to be a plain function
    rather than a callable object.
    """
    chunks: list[str] = []

    def capture_tool_result(event: AfterToolCallEvent) -> None:
        try:
            chunks.append(json.dumps(event.result, default=str))
        except Exception:  # noqa: BLE001
            chunks.append(str(event.result))

    return chunks, capture_tool_result


def strip_brackets(text: str) -> str:
    """Placeholders are instructions to the patient, not claims by the agent."""
    return re.sub(r"\[[^\]]*\]", " ", text)


def claims_in(letter: str) -> tuple[set[str], set[str]]:
    """The two kinds of specific the agent could get wrong: a number, or an authority."""
    body = strip_brackets(letter)
    numeric = {m.group(0).strip().lower() for m in NUMERIC.finditer(body)}
    named = {a for a in AUTHORITIES if re.search(rf"\b{re.escape(a)}\b", body, re.I)}
    return numeric, named


def normalise(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


# The tools return a rate as a decimal (0.6493) and the model correctly writes it as a
# percentage (64.93%, or rounded to 65%). A literal substring check cannot see through
# that conversion and reports a perfectly grounded number as a fabrication. Likewise the
# reviewers write "Food and Drug Administration" where the letter writes "FDA".
ALIASES = {
    "fda": ["food and drug administration"],
    "mcg": ["milliman"],
    "nccn": ["national comprehensive cancer network"],
    "asam": ["american society of addiction medicine"],
    "aad": ["american academy of dermatology"],
    "centers for medicare": ["cms", "medicare"],
}

_DECIMAL = re.compile(r"\b0?\.\d+\b")
_PCT_CLAIM = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:%|percent)$", re.I)


def grounded(claim: str, context: str) -> bool:
    c = normalise(context)
    n = normalise(claim)

    if n in c or n.replace(" ", "") in c.replace(" ", ""):
        return True

    for alias in ALIASES.get(n, []):
        if alias in c:
            return True

    # A percentage claim is grounded if any decimal in the context equals it, allowing
    # for the model rounding 0.6493 to "65%".
    m = _PCT_CLAIM.match(n)
    if m:
        want = float(m.group(1))
        for d in _DECIMAL.findall(context):
            pct = float(d) * 100
            if abs(pct - want) < 0.01 or round(pct) == round(want):
                return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=8)
    args = ap.parse_args()

    idx = PrecedentIndex()
    rows = [json.loads(line) for line in TEST.open(encoding="utf-8")]
    usable = [r for r in rows if idx.query(r["case"], k=1).exemplars]

    denial = date.today() - timedelta(days=95)
    grievance = denial + timedelta(days=9)

    tot_num = tot_num_ok = 0
    tot_prop = tot_prop_ok = 0
    unsupported = Counter()
    letters = 0
    # Union of every context, so the negative control runs against the largest possible
    # haystack. If a fabrication survives that, the checker is genuinely too loose.
    context_parts: list[str] = []

    for i in range(args.runs):
        rec = usable[(i * 211) % len(usable)]
        c = rec["case"]
        chunks, capture = make_capture()
        agent = build_agent()
        agent.add_hook(capture, AfterToolCallEvent)

        prompt = f"""My health plan denied coverage and I want to appeal to the state.

Denial letter date: {denial.isoformat()}
I filed a grievance with my plan on: {grievance.isoformat()}
My plan has not answered the grievance.

What was denied:
- Diagnosis category: {c['DiagnosisCategory']}
- Diagnosis: {c['DiagnosisSubCategory']}
- Treatment category: {c['TreatmentCategory']}
- Treatment refused: {c['TreatmentSubCategory']}
- The plan's stated grounds: {c['Type']}
- Me: {c['AgeRange']}, {c['PatientGender']}

Work out my deadline, find out how cases like mine were actually decided, and draft
my appeal."""

        try:
            result = agent(prompt)
        except Exception as exc:  # noqa: BLE001
            print(f"run {i+1}: ERROR {type(exc).__name__}: {exc}")
            continue

        if not result.interrupts or not isinstance(result.interrupts[0].reason, dict):
            print(f"run {i+1}: no letter produced")
            continue

        letter = result.interrupts[0].reason.get("letter", "")
        if not letter:
            continue
        letters += 1

        ctx = "\n".join(chunks)
        context_parts.append(ctx)
        numeric, proper = claims_in(letter)
        n_ok = sum(1 for x in numeric if grounded(x, ctx))
        p_ok = sum(1 for x in proper if grounded(x, ctx))

        tot_num += len(numeric); tot_num_ok += n_ok
        tot_prop += len(proper); tot_prop_ok += p_ok

        for x in numeric:
            if not grounded(x, ctx):
                unsupported[f"NUM  {x}"] += 1
        for x in proper:
            if not grounded(x, ctx):
                unsupported[f"NAME {x}"] += 1

        print(f"run {i+1}: numeric {n_ok}/{len(numeric)}  named {p_ok}/{len(proper)}  "
              f"[{c['DiagnosisSubCategory'][:26]}]")

    all_context = "\n".join(context_parts)

    # --- negative control -----------------------------------------------------------
    # A grounding check that never fails is not a check. These claims are plausible in
    # an appeal letter and are absent from every context, so each one MUST be flagged
    # unsupported. If any pass, the checker is too permissive and the headline above is
    # worthless.
    print(f"\n{'=' * 70}")
    print("NEGATIVE CONTROL: fabricated claims that must all be caught")
    fakes = [
        "42.7%", "13.3%", "88 mg", "American Academy of Ophthalmology",
        "InterQual", "Milliman", "World Health Organization",
    ]
    caught = 0
    for f in fakes:
        ok = not grounded(f, all_context)
        caught += ok
        print(f"  {'caught  ' if ok else 'MISSED  '}{f}")
    print(f"  negative control: {caught}/{len(fakes)} fabrications correctly flagged")
    if caught < len(fakes):
        print("  ^ the checker is too permissive; the grounding rate above is not "
              "trustworthy until this is 100%")

    print(f"\n{'=' * 70}")
    print(f"letters analysed: {letters}")
    print(f"distinct decimals available in tool context: "
          f"{len(set(_DECIMAL.findall(all_context)))}")
    print(f"numeric claims (percent / dose): {tot_num_ok}/{tot_num} grounded"
          + (f" ({tot_num_ok/tot_num:.1%})" if tot_num else "  [none asserted]"))
    print(f"named clinical authorities:      {tot_prop_ok}/{tot_prop} grounded"
          + (f" ({tot_prop_ok/tot_prop:.1%})" if tot_prop else "  [none asserted]"))

    if unsupported:
        print("\nUNSUPPORTED SPECIFICS (the agent asserted these; the record did not):")
        for k, v in unsupported.most_common(25):
            print(f"    {v}x  {k}")
    else:
        print("\nno unsupported specifics found")

    report = {
        "letters_analysed": letters,
        "numeric_claims": {"grounded": tot_num_ok, "total": tot_num},
        "named_authorities": {"grounded": tot_prop_ok, "total": tot_prop},
        "unsupported": dict(unsupported),
        "negative_control": {"caught": caught, "total": len(fakes), "claims": fakes},
        "distinct_decimals_in_context": len(set(_DECIMAL.findall(all_context))),
        "model": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "note": (
            "Grounding is checked mechanically against exactly what the tools returned "
            "to the model, captured by a Strands AfterToolCallEvent hook. No model "
            "grades another model here. The negative control exists because a checker "
            "that cannot fail proves nothing."
        ),
    }
    out = ROOT / "eval" / "grounding_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwritten: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

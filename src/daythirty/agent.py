"""The Day Thirty agent.

Three tools and one gate:

  compute_filing_deadline   Deterministic. No model touches the date arithmetic, because
                            a hallucinated deadline is the one error that cannot be
                            recovered from: miss it and the right to appeal is gone.
  find_precedent            Deterministic retrieval over 22,090 decisions California
                            published. The model reads them; it does not invent them.
  file_appeal               Raises a human interrupt. Nothing is ever filed without a
                            person approving that specific letter.

The model writes the appeal. That is deliberate: the drafted letter is the artifact the
headline number is measured on, so the sponsor's model has to be the thing producing it,
not a template with the model bolted alongside.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from strands import Agent, ToolContext, tool
from strands.models import BedrockModel

from daythirty.deadlines import imr_filing_deadline
from daythirty.precedent import PrecedentIndex

# Verified by invocation on 2026-09-09. Opus 5 and Sonnet 5 are not entitled on this
# account; Haiku 4.5 and the Nova family are. See memory: aws-bedrock-environment.
DRAFTING_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
REGION = "us-east-1"

_INDEX: PrecedentIndex | None = None


def _index() -> PrecedentIndex:
    global _INDEX
    if _INDEX is None:
        _INDEX = PrecedentIndex()
    return _INDEX


def _parse(d: str) -> date:
    return datetime.strptime(d.strip(), "%Y-%m-%d").date()


_FIELD_WORDS = {
    "DiagnosisCategory": "diagnosis area",
    "DiagnosisSubCategory": "diagnosis",
    "TreatmentCategory": "treatment area",
    "TreatmentSubCategory": "treatment",
    "Type": "denial grounds",
}


def _describe_cohort(tier: str | None, case: dict[str, str]) -> str:
    """Say in plain English which denials the published rate actually covers."""
    if tier is None:
        return "No published rate: too few comparable decisions at any level of match."
    parts = []
    for field in tier.split("+"):
        value = (case.get(field) or "").strip()
        parts.append(f"{_FIELD_WORDS.get(field, field)} '{value}'")
    scope = ", ".join(parts)
    unmatched = [f for f in _FIELD_WORDS if f not in tier.split("+")]
    breadth = ""
    if unmatched:
        breadth = (
            " This rate is NOT limited to this specific "
            + " or ".join(_FIELD_WORDS[f] for f in unmatched)
            + "; it covers every published case sharing the fields listed above."
        )
    return f"All published California IMR decisions matching {scope}.{breadth}"


@tool
def compute_filing_deadline(
    denial_date: str,
    grievance_filed: str,
    plan_upheld_on: str = "",
    expedited: bool = False,
) -> dict[str, Any]:
    """Compute the last day to apply to California DMHC for independent medical review.

    Dates are YYYY-MM-DD. `plan_upheld_on` is empty when the plan has not answered.
    Set `expedited` only where Health & Safety Code section 1368.01 expedited review
    applies.

    Returns the deadline, the qualifying event it runs from, and the statutory
    reasoning. Do not compute or adjust any date yourself; use only what this returns.
    """
    result = imr_filing_deadline(
        denial_date=_parse(denial_date),
        grievance_filed=_parse(grievance_filed),
        plan_upheld_on=_parse(plan_upheld_on) if plan_upheld_on.strip() else None,
        expedited=expedited,
    )
    return {
        "deadline": result.deadline.isoformat(),
        "qualifying_event": result.qualifying_event.isoformat(),
        "qualifying_event_basis": result.qualifying_event_basis,
        "statutory_reasoning": result.reasoning,
        "caveats": result.caveats,
        "days_remaining_from_today": (result.deadline - date.today()).days,
        "common_error": (
            "Counting six months from the plan's answer instead of from the qualifying "
            "event puts the deadline roughly (response time - 30) days too late."
        ),
    }


@tool
def find_precedent(
    diagnosis_category: str,
    diagnosis_subcategory: str,
    treatment_category: str,
    treatment_subcategory: str,
    grounds: str,
) -> dict[str, Any]:
    """Find published California IMR decisions closest to this denial.

    `grounds` is what the plan cited, one of: "Medical Necessity",
    "Experimental/Investigational", "Urgent Care".

    Returns the overturn rate California actually recorded for comparable denials, and
    the reasoning independent physician reviewers gave in cases they overturned. Argue
    only from what comes back here. Never invent a case, a rate, or a citation.
    """
    res = _index().query(
        {
            "DiagnosisCategory": diagnosis_category,
            "DiagnosisSubCategory": diagnosis_subcategory,
            "TreatmentCategory": treatment_category,
            "TreatmentSubCategory": treatment_subcategory,
            "Type": grounds,
        },
        k=3,
    )
    # The rate is computed over whatever tier had enough published cases, which is often
    # broader than this specific condition. Saying so in plain English is not optional:
    # left to a `matched_on` field alone, a model will quote a pharmacy-wide rate as if
    # it were specific to the patient's diagnosis. Observed doing exactly that.
    describes = _describe_cohort(res.cohort_tier, {
        "DiagnosisCategory": diagnosis_category,
        "DiagnosisSubCategory": diagnosis_subcategory,
        "TreatmentCategory": treatment_category,
        "TreatmentSubCategory": treatment_subcategory,
        "Type": grounds,
    })

    return {
        "published_overturn_rate": (
            None if res.cohort_rate is None else round(res.cohort_rate, 4)
        ),
        "cohort_size": res.cohort_n,
        "cohort_overturned": res.cohort_overturned,
        "matched_on": res.cohort_tier,
        "rate_describes": describes,
        "rate_is_specific_to_this_condition": (
            res.cohort_tier is not None and "DiagnosisSubCategory" in res.cohort_tier
        ),
        "notes": res.notes,
        "exemplars": [
            {
                "year": e.year,
                "reviewer_specialty": e.specialty,
                "matched_on": e.tier,
                "reviewer_reasoning": e.reasoning,
            }
            for e in res.exemplars
        ],
        "source": (
            "California Department of Managed Health Care, published Independent "
            "Medical Review determinations, 2016-2024."
        ),
    }


@tool(context=True)
def file_appeal(
    tool_context: ToolContext,
    letter: str,
    deadline: str,
    summary: str,
) -> str:
    """Submit the drafted appeal. Requires explicit human approval of this exact letter.

    Call this only once the letter is complete. Execution pauses here until a person
    approves or rejects.
    """
    decision = tool_context.interrupt(
        name="approve_filing",
        reason={
            "action": "File IMR application with California DMHC",
            "deadline": deadline,
            "summary": summary,
            "letter": letter,
        },
    )
    if isinstance(decision, dict):
        approved = bool(decision.get("approved"))
        note = str(decision.get("note", ""))
    else:
        approved = str(decision).strip().lower() in {"yes", "y", "approve", "approved", "true"}
        note = ""

    if not approved:
        return f"NOT FILED. The person declined. {note}".strip()
    return (
        f"FILED. IMR application submitted to California DMHC, on or before {deadline}. "
        f"{note}".strip()
    )


SYSTEM_PROMPT = """\
You are Day Thirty. You work a California health insurance denial end to end for the \
person who was denied, and you are on their side.

How you work:

1. Compute the filing deadline with `compute_filing_deadline`. Never do date arithmetic \
yourself and never restate a date the tool did not give you. Missing this deadline ends \
the person's right to appeal, so it is the one thing that must be exact.

2. Find out how comparable denials were actually decided with `find_precedent`. \
Everything you argue must come from what that tool returns. If it returns no exemplars, \
say so plainly rather than filling the gap.

3. Draft the appeal letter, in this same turn. Write it as the patient, addressed to the \
California Department of Managed Health Care. Ground every clinical argument in the \
reasoning independent reviewers actually gave in the returned cases. Refer to those \
findings in general terms; do not fabricate case numbers. The letter is plain text that \
will be printed and mailed: no markdown, no asterisks, no # headings. Section titles are \
just lines of text.

4. Call `file_appeal` with the finished letter. A person approves or rejects it. You do \
not file anything yourself.

Hard rules:

- Never invent a statute, a section number, a case, an overturn rate or a date.
- Cite only `Cal. Health & Safety Code section 1374.30` and what the tools return.

- QUOTING THE PUBLISHED RATE. When you state the overturn rate you must also state what \
population it covers, using the `rate_describes` field. If \
`rate_is_specific_to_this_condition` is false, you must NOT phrase the rate as though it \
applies to this diagnosis or this drug. Say "denials of this general type" and name the \
actual scope. Attaching a broad rate to a specific condition is the worst error you can \
make here, worse than having no rate at all, because it misleads someone deciding \
whether to fight.

- DRAFT, DO NOT INTERVIEW. You will not have the patient's full clinical history, and \
that is expected. Write the complete letter anyway, marking each missing specific in \
square brackets, like [dates you tried this medication]. The brackets ARE the \
deliverable. They are not a reason to wait.

- ALWAYS CALL `file_appeal`, IN THE SAME TURN AS THE DRAFT. Your turn is not finished \
until you have called it. Do not ask the patient to fill the brackets first. Do not \
say you will file "once you provide these details". Do not end on a list of questions \
or a description of what you are about to do next. Draft the letter, then call \
`file_appeal` with it. A person reviews it at that gate, which is exactly where they \
fill the brackets and decide. Ending your turn without calling `file_appeal` is a \
failure, because it leaves the person with homework instead of a filing.

- If the published rate is low, say so. The person deserves an honest read, not \
encouragement. An appeal is still theirs to make.
- You are not a lawyer and this is not legal advice. Say that once, at the end.
"""


ALL_TOOLS = [compute_filing_deadline, find_precedent, file_appeal]


def build_agent(
    model_id: str = DRAFTING_MODEL,
    region: str = REGION,
    tools: list | None = None,
    system_prompt: str = SYSTEM_PROMPT,
) -> Agent:
    """The agent as the demo runs it.

    `tools` and `system_prompt` are overridable so the ablation in eval/ablation.py can
    run the identical model with a tool removed and measure what that tool contributed.
    The demo never passes them.
    """
    return Agent(
        model=BedrockModel(
            model_id=model_id,
            region_name=region,
            max_tokens=8192,
            # Low, because the failure mode observed at 0.3 was behavioural drift: the
            # agent sometimes drafted the letter and then offered to file it later
            # instead of calling the tool, which loses the approval gate entirely.
            temperature=0.1,
        ),
        tools=ALL_TOOLS if tools is None else tools,
        system_prompt=system_prompt,
    )

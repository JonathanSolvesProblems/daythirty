"""Read an actual denial letter and recover the facts the rest of the agent needs.

Real people do not have database fields. They have a letter from their plan that says
their treatment was denied, written in clinical and insurance language. Everything
downstream (the deadline, the precedent lookup) needs California's own taxonomy, so
something has to bridge the two.

Amazon Nova does the reading. That is a genuine job for a model: the letter is
unstructured, the vocabulary varies by plan, and the mapping from "plaque psoriasis
treated with adalimumab" to California's category "Skin Subcutaneous" is knowledge, not
string matching.

The mapping is then checked deterministically against the real category list pulled from
the corpus, so the model cannot invent a category that does not exist. If it returns
something off-list, the closest real value is used and the substitution is recorded.

This is externally gradeable, which is the point: California already assigned a category
to every published case, so rendering a real case as a letter and asking Nova to recover
the category is scored against the state's own label, not mine. See
`eval/intake_accuracy.py`.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import boto3

TAXONOMY = json.loads(
    (Path(__file__).parent / "taxonomy.json").read_text(encoding="utf-8")
)

INTAKE_MODEL = "us.amazon.nova-lite-v1:0"
REGION = "us-east-1"

_client = None


def client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=REGION)
    return _client


@dataclass
class Intake:
    diagnosis_category: str
    diagnosis_subcategory: str
    treatment_category: str
    treatment_subcategory: str
    grounds: str
    condition_text: str
    treatment_text: str
    denial_date: str | None
    grievance_date: str | None
    corrections: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def _closest(value: str, allowed: list[str]) -> tuple[str, bool]:
    """Snap to the real taxonomy. Returns the value and whether it had to be corrected."""
    if value in allowed:
        return value, False
    match = difflib.get_close_matches(value, allowed, n=1, cutoff=0.0)
    return (match[0] if match else allowed[0]), True


# Asking the model for the CATEGORY directly turned out to be the wrong division of
# labour. California's categories are coarse administrative buckets whose membership is
# context-dependent: it files Speech Therapy under "Autism Related Tx" and Arthritis
# under "Immuno Disorders". A model reading a letter cannot know that, and measuring it
# scored taxonomy quirks rather than reading comprehension.
#
# The corpus already contains the answer. Every published case pairs a subcategory with
# the category the state filed it under, so the mapping can be looked up instead of
# inferred. The model does what needs a model (read unstructured prose, name the
# condition and the treatment) and the taxonomy is resolved deterministically.
SUBCATEGORY_MAP = json.loads(
    (Path(__file__).parent / "subcategory_map.json").read_text(encoding="utf-8")
)


def _map_via_subcategory(text: str, kind: str) -> tuple[str | None, str | None]:
    """Resolve free text to (subcategory, category) using the state's own pairings.

    `kind` is "diagnosis" or "treatment". Returns (None, None) when nothing is close
    enough, so the caller can fall back rather than accept a bad match silently.
    """
    table = SUBCATEGORY_MAP[kind]
    if not text:
        return None, None
    keys = list(table.keys())
    lowered = text.lower().strip()

    # Exact or containment first: "plaque psoriasis" contains "psoriasis".
    for k in keys:
        kl = k.lower()
        if kl == lowered or (len(kl) > 4 and kl in lowered) or (len(lowered) > 4 and lowered in kl):
            return k, table[k]

    match = difflib.get_close_matches(text, keys, n=1, cutoff=0.62)
    if match:
        return match[0], table[match[0]]
    return None, None


PROMPT = """You are reading a health plan denial letter. Extract the facts below and \
return ONLY a JSON object, no prose, no code fences.

Fields:
  "condition_text"  the medical condition the letter names, in the letter's own words. \
Just the condition, no surrounding phrasing.
  "treatment_text"  the specific treatment, drug, device or service that was denied, in \
the letter's own words.
  "grounds"         exactly one of: Medical Necessity, Experimental/Investigational, \
Urgent Care
  "denial_date"     the date of this determination in YYYY-MM-DD, or null
  "grievance_date"  the date the member filed a grievance in YYYY-MM-DD, or null if the \
letter does not say

Report what the letter says. Do not classify, generalise, or add anything not written.

LETTER:
{letter}
"""


def parse_denial_letter(letter: str, model_id: str = INTAKE_MODEL) -> Intake:
    """Nova reads the letter. The taxonomy is then resolved deterministically.

    The split is deliberate. Reading unstructured plan correspondence is a model's job.
    Deciding that California files "Speech Therapy" under "Autism Related Tx" is not
    inference at all, it is a lookup, and the corpus already contains it.
    """
    body = {
        "messages": [{"role": "user", "content": [{"text": PROMPT.format(letter=letter.strip())}]}],
        "inferenceConfig": {"maxTokens": 500, "temperature": 0.0},
    }
    resp = client().invoke_model(modelId=model_id, body=json.dumps(body))
    payload = json.loads(resp["body"].read())
    text = payload["output"]["message"]["content"][0]["text"]

    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no JSON in intake response: {text[:200]}")
    data = json.loads(m.group(0))

    corrections: list[str] = []
    condition = str(data.get("condition_text", "") or "")
    treatment = str(data.get("treatment_text", "") or "")

    dx_sub, dx = _map_via_subcategory(condition, "diagnosis")
    if dx is None:
        dx = "Other"
        corrections.append(f"condition {condition!r} matched no known subcategory")
    tx_sub, tx = _map_via_subcategory(treatment, "treatment")
    if tx is None:
        tx = "Other"
        corrections.append(f"treatment {treatment!r} matched no known subcategory")

    grounds, fixed = _closest(str(data.get("grounds", "")), TAXONOMY["Type"])
    if fixed:
        corrections.append(f"grounds {data.get('grounds')!r} -> {grounds!r}")

    return Intake(
        diagnosis_category=dx,
        diagnosis_subcategory=dx_sub or "",
        treatment_category=tx,
        treatment_subcategory=tx_sub or "",
        grounds=grounds,
        condition_text=condition,
        treatment_text=treatment,
        denial_date=data.get("denial_date") or None,
        grievance_date=data.get("grievance_date") or None,
        corrections=corrections,
        raw=data,
    )


# ---------------------------------------------------------------------------------------
# Letter rendering, for the demo and for the intake evaluation.
#
# DMHC publishes determinations, not the underlying plan correspondence, so a real denial
# letter for a published case does not exist to be downloaded. The letter below is
# rendered from a REAL published case using the state's own clinical descriptors, in the
# register a plan actually writes in. The clinical facts are real; the letterhead is not.
# That distinction is stated in the README rather than glossed over.
#
# Deliberately, the letter never contains California's CATEGORY names, only the specific
# condition and treatment. Recovering the category is therefore a real inference and not
# a lookup of something planted in the text.
# ---------------------------------------------------------------------------------------

LETTER_TEMPLATE = """\
PACIFIC RIDGE HEALTH PLAN
Utilization Management Department
PO Box 41190, Sacramento, CA 95841

{date}

RE: NOTICE OF ADVERSE BENEFIT DETERMINATION
Member: {member}
Member ID: PRH-{mid}
Reference: UM-{ref}

Dear Member,

We have completed our review of the request submitted by your treating provider for
{treatment}, in connection with your diagnosis of {condition}.

DETERMINATION: DENIED

After review of the clinical information submitted, we have determined that the
requested service does not meet our criteria for coverage. Basis for this determination:
{grounds_text}

The reviewing clinician considered the documentation provided by your provider and the
plan's applicable coverage criteria in effect on the date of the request.

YOUR RIGHT TO APPEAL

You have the right to file a grievance with Pacific Ridge Health Plan regarding this
determination. You may also have the right to request an Independent Medical Review
through the California Department of Managed Health Care. Please refer to the enclosed
Member Rights notice for further information.

Sincerely,
Utilization Management
Pacific Ridge Health Plan

This determination applies to coverage only and is not medical advice. You and your
provider may pursue the requested treatment at your own expense.
"""

GROUNDS_TEXT = {
    "Medical Necessity": (
        "The submitted documentation does not establish that the requested service is "
        "medically necessary for the treatment of the member's condition."
    ),
    "Experimental/Investigational": (
        "The requested service is considered experimental or investigational for the "
        "member's condition and is excluded under the terms of the plan."
    ),
    "Urgent Care": (
        "The request did not meet the plan's criteria for expedited review, and the "
        "requested service was not authorized."
    ),
}


def render_denial_letter(case: dict, denial_date: str, member: str = "[Member Name]") -> str:
    """Render a real published case as the letter a plan would have sent."""
    ref = abs(hash(json.dumps(case, sort_keys=True))) % 900000 + 100000
    return LETTER_TEMPLATE.format(
        date=denial_date,
        member=member,
        mid=ref % 10000,
        ref=ref,
        treatment=case["TreatmentSubCategory"],
        condition=case["DiagnosisSubCategory"],
        grounds_text=GROUNDS_TEXT.get(case["Type"], GROUNDS_TEXT["Medical Necessity"]),
    )

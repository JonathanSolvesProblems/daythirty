"""Find the published decisions closest to a new denial, and what won them.

The corpus is 22,090 California Independent Medical Review determinations from 2016 to
2024, each decided by a state-contracted independent physician reviewer and published by
the Department of Managed Health Care. Nothing in it was written here, and the agent may
only read cases decided before the held-out period, so it can never cite a neighbour that
is part of the answer key.

Two different things come out of this module and they must not be confused:

  `cohort_rate`  How often denials like this one were overturned. This is a count over
                 the state's published record. It is a fact about California, not a
                 prediction, and the module refuses to report it below MIN_COHORT.

  `exemplars`    Specific overturned cases whose reviewer explained why. These are what
                 the appeal argues from. The reviewer's words, not mine.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

TRAIN = Path(__file__).resolve().parents[2] / "data" / "split" / "train.jsonl"

# Below this, a rate over the state's record is too thin to quote to a patient.
MIN_COHORT = 20

# An exemplar is only precedent if it is about roughly the same thing. Matching on
# TreatmentCategory alone puts a Saxenda obesity case forward as precedent for a
# hepatitis antiviral denial, which is worse than returning nothing, so the floor is
# DiagnosisCategory + TreatmentCategory + Type. Cases below it get an honest refusal.
MIN_EXEMPLAR_SCORE = 40

# Match tiers, most specific first. The score is the tier weight; ties break on recency.
TIERS: list[tuple[tuple[str, ...], int]] = [
    (("DiagnosisSubCategory", "TreatmentSubCategory", "Type"), 100),
    (("DiagnosisSubCategory", "TreatmentSubCategory"), 80),
    (("DiagnosisCategory", "TreatmentSubCategory", "Type"), 60),
    (("DiagnosisCategory", "TreatmentCategory", "Type"), 40),
    (("TreatmentCategory", "Type"), 20),
    (("TreatmentCategory",), 10),
]

OVERTURNED = 1

# Keep only the reviewer's clinical reasoning, dropping the verdict and the credentials
# boilerplate. This is NOT an answer-key control: held-out cases carry no narrative at
# all, and exemplars are deliberately filtered to overturned cases, so their outcome is
# the selection criterion rather than a leak. It is a drafting-quality control. Feeding
# "the Health Plan's denial should be overturned" into a prompt teaches the model to
# produce conclusions instead of arguments.
#
# DMHC used at least three formats across 2016-2024, found by measurement rather than
# assumption (eval/inspect_leaks.py):
#   - "Final Result:" as a header (newer)
#   - "Final Results:" plural, on multi-reviewer panel cases
#   - no header at all, the verdict running inline as "The reviewer determined that ..."
_CUTS = [
    re.compile(r"Final Results?\s*:", re.I),
    re.compile(r"The reviewer determined that", re.I),
    re.compile(r"\d+ of \d+ reviewers determined", re.I),
    re.compile(r"Credentials/Qualifications\s*:", re.I),
    re.compile(r"The reviewer is board[‐-―\-\s]?certified", re.I),
]
_LEAD = re.compile(r"^\s*(?:Findings\s*:\s*)?(?:The physician reviewer found that\s*)?"
                   r"(?:Nature of Statutory Criteria/Case Summary\s*:\s*)?", re.I)


def reasoning_of(findings: str) -> str:
    """The reviewer's clinical reasoning, with verdict and credentials removed."""
    text = findings
    for cut in _CUTS:
        text = cut.split(text, maxsplit=1)[0]
    return _LEAD.sub("", text, count=1).strip()


# Roughly 0.3% of overturned narratives still end on conclusory language after the cuts
# above, because DMHC's formats are not fully consistent. With 12,570 candidates and only
# three needed, the right move is to discard those rather than tolerate them.
_RESIDUAL_VERDICT = re.compile(
    r"should be overturned|should be upheld|denial should|Final Result|"
    r"is not medically necessary for the treatment of this patient\.\s*$",
    re.I,
)


def is_clean_reasoning(text: str) -> bool:
    """True when no conclusory verdict language survives in the reasoning."""
    return not _RESIDUAL_VERDICT.search(text)


def specialty_of(findings: str) -> str | None:
    """The reviewer's board specialty, where DMHC published it (2024 onward)."""
    m = re.search(r"board[‐-―\-]?certified in\s+([^.]{3,160})", findings, re.I)
    if not m:
        return None
    return re.sub(r"\s+", " ", m.group(1)).strip().rstrip(",")


@dataclass
class Exemplar:
    year: int
    case: dict
    reasoning: str
    specialty: str | None
    tier: str
    score: int


@dataclass
class PrecedentResult:
    cohort_n: int
    cohort_overturned: int
    cohort_rate: float | None
    cohort_tier: str | None
    exemplars: list[Exemplar] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def rate_is_reportable(self) -> bool:
        return self.cohort_rate is not None


class PrecedentIndex:
    def __init__(self, path: Path = TRAIN) -> None:
        self.records: list[dict] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                self.records.append(json.loads(line))

        # One dict per tier, so a query is a hash lookup rather than a scan of 22,090.
        self._buckets: list[dict[tuple[str, ...], list[dict]]] = []
        for fields, _ in TIERS:
            bucket: dict[tuple[str, ...], list[dict]] = {}
            for r in self.records:
                bucket.setdefault(self._key(r["case"], fields), []).append(r)
            self._buckets.append(bucket)

    def __len__(self) -> int:
        return len(self.records)

    @staticmethod
    def _key(case: dict, fields: tuple[str, ...]) -> tuple[str, ...]:
        return tuple((case.get(f) or "").strip() for f in fields)

    def cohort(self, case: dict) -> tuple[list[dict], str | None]:
        """Widen from the most specific tier until enough published cases exist."""
        for i, (fields, _) in enumerate(TIERS):
            want = self._key(case, fields)
            if any(v == "" for v in want):
                continue
            hits = self._buckets[i].get(want, [])
            if len(hits) >= MIN_COHORT:
                return hits, "+".join(fields)
        return [], None

    def query(self, case: dict, k: int = 3) -> PrecedentResult:
        hits, tier = self.cohort(case)
        notes: list[str] = []

        if not hits:
            notes.append(
                f"Fewer than {MIN_COHORT} published decisions match this case at any "
                "tier, so no overturn rate is reported for it."
            )
            return PrecedentResult(0, 0, None, None, [], notes)

        overturned = [r for r in hits if r["label"] == OVERTURNED]
        rate = len(overturned) / len(hits)

        # Exemplars are drawn only from cases that were overturned, because the appeal
        # argues from what persuaded a reviewer, not from what failed to.
        candidates: list[Exemplar] = []
        for r in overturned:
            matched: tuple[str, int] | None = None
            for fields, weight in TIERS:
                if self._key(r["case"], fields) == self._key(case, fields):
                    matched = ("+".join(fields), weight)
                    break
            if matched is None or matched[1] < MIN_EXEMPLAR_SCORE:
                continue
            reasoning = reasoning_of(r.get("findings", ""))
            if len(reasoning) < 120:
                continue  # too thin to argue from
            if not is_clean_reasoning(reasoning):
                continue  # conclusory language survived the cuts; plenty more available
            candidates.append(
                Exemplar(
                    year=r["year"],
                    case=r["case"],
                    reasoning=reasoning,
                    specialty=specialty_of(r.get("findings", "")),
                    tier=matched[0],
                    score=matched[1],
                )
            )

        # Closest tier first, then most recent, so the argument cited is both the best
        # match and the most current statement of what persuades a reviewer.
        candidates.sort(key=lambda e: (-e.score, -e.year))
        picked = candidates[:k]

        if not picked:
            notes.append(
                "No published decision matches this diagnosis and treatment closely "
                "enough to argue from. The overturn rate below is still real, but it is "
                "drawn from a broader population than this specific case."
            )
        if len(overturned) < MIN_COHORT:
            notes.append(
                f"Only {len(overturned)} of {len(hits)} matched cases were overturned, "
                "so the exemplars are drawn from a small pool."
            )

        return PrecedentResult(
            cohort_n=len(hits),
            cohort_overturned=len(overturned),
            cohort_rate=rate,
            cohort_tier=tier,
            exemplars=picked,
            notes=notes,
        )

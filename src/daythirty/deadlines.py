"""Statutory deadline computation for a California Independent Medical Review.

No model runs in this file. Every rule below is a citation, and the citation is the
point: the standard being applied was written by the California Legislature, not here.

The chain, verified against leginfo.legislature.ca.gov:

  Cal. Health & Safety Code § 1374.30(k)
      "An enrollee may apply to the department for an independent medical review of a
      decision to deny, modify, or delay health care services ... within six months of
      any of the qualifying periods or events under subdivision (j)."

  Cal. Health & Safety Code § 1374.30(j)(3)
      "The enrollee has filed a grievance with the plan or its contracting provider
      pursuant to Section 1368, and the disputed decision is upheld or the grievance
      remains unresolved after 30 days. The enrollee shall not be required to participate
      in the plan's grievance process for more than 30 days. In the case of a grievance
      that requires expedited review pursuant to Section 1368.01, the enrollee shall not
      be required to participate in the plan's grievance process for more than three
      days."

  Cal. Civ. Code § 14
      "The word 'month' means a calendar month, unless otherwise expressed."

  Cal. Civ. Code § 10
      "The time in which any act provided by law is to be done is computed by excluding
      the first day and including the last, unless the last day is a holiday, and then it
      is also excluded."

  Cal. Civ. Code § 7
      "Holidays within the meaning of this code are every Sunday and such other days as
      are specified or provided for as holidays in the Government Code."

  Cal. Gov. Code § 6700
      The holiday list itself, transcribed in CA_HOLIDAY_RULES below.

The clock that people get wrong: the six months does NOT run from the denial letter. It
runs from the qualifying event, which is itself the EARLIER of the day the plan upheld
the grievance and the thirtieth day after the grievance was filed. Counting from the
denial is the single most common way to lose the right to appeal entirely.

This is a hackathon project and not legal advice. It computes a date; it does not tell
anyone what to do about it.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta

# --------------------------------------------------------------------------------------
# Cal. Gov. Code § 6700, via Cal. Civ. Code § 7
# --------------------------------------------------------------------------------------

# Fixed calendar dates. (month, day, name)
FIXED_HOLIDAYS: list[tuple[int, int, str]] = [
    (1, 1, "January 1"),
    (2, 12, "Lincoln Day"),
    (3, 31, "Farmworkers Day"),
    (4, 24, "Genocide Remembrance Day"),
    (6, 19, "Juneteenth"),
    (7, 4, "July 4"),
    (9, 9, "Admission Day"),
    (11, 11, "Veterans Day"),
    (12, 25, "December 25"),
]

# "The nth <weekday> in <month>". Weekday is Monday=0 per date.weekday().
# A negative ordinal means counting back from the end of the month.
NTH_WEEKDAY_HOLIDAYS: list[tuple[int, int, int, str]] = [
    (1, 0, 3, "Dr. Martin Luther King, Jr. Day"),   # third Monday in January
    (2, 0, 3, "third Monday in February"),
    (5, 0, -1, "last Monday in May"),
    (9, 0, 1, "first Monday in September"),
    (9, 4, 4, "Native American Day"),               # fourth Friday in September
    (10, 0, 2, "Columbus Day"),                     # second Monday in October
]

# Two § 6700 holidays are defined astronomically rather than by calendar date:
#
#   "The date corresponding with the second new moon following the winter solstice, or
#    the third new moon following the winter solstice should an intercalary month
#    intervene, known as 'Lunar New Year'"
#
#   "The 15th day of the month of Kartik in the Hindu lunar calendar of each year, known
#    as 'Diwali'"
#
# These cannot be derived from a Gregorian calendar alone. They are supplied as data
# rather than computed, and any year missing from these tables is reported by
# `unverified_years()` instead of being silently treated as having no such holiday.
# Populating a year here requires a cited source; nothing in these tables is estimated.
LUNAR_NEW_YEAR: dict[int, date] = {}
DIWALI: dict[int, date] = {}

GOOD_FRIDAY_NOTE = (
    "Good Friday is a holiday under § 6700 only 'from 12 noon until 3 p.m.', a partial "
    "day. It is not treated as a full-day holiday for deadline computation, and that "
    "choice is recorded here rather than buried."
)


def _nth_weekday(year: int, month: int, weekday: int, ordinal: int) -> date:
    """The nth <weekday> of a month. Negative ordinal counts back from the end."""
    days_in_month = calendar.monthrange(year, month)[1]
    matches = [
        date(year, month, d)
        for d in range(1, days_in_month + 1)
        if date(year, month, d).weekday() == weekday
    ]
    return matches[ordinal - 1] if ordinal > 0 else matches[ordinal]


def statutory_holidays(year: int) -> dict[date, str]:
    """Every full-day § 6700 holiday in a given year, excluding Sundays.

    Sundays are handled separately in `is_holiday` because § 7 names them directly and
    listing all 52 here would obscure the statutory list.
    """
    out: dict[date, str] = {}
    for month, day, name in FIXED_HOLIDAYS:
        out[date(year, month, day)] = name
    for month, weekday, ordinal, name in NTH_WEEKDAY_HOLIDAYS:
        out[_nth_weekday(year, month, weekday, ordinal)] = name
    if year in LUNAR_NEW_YEAR:
        out[LUNAR_NEW_YEAR[year]] = "Lunar New Year"
    if year in DIWALI:
        out[DIWALI[year]] = "Diwali"
    return out


def unverified_years(years: list[int]) -> list[int]:
    """Years where the astronomically-defined holidays are not yet supplied.

    A deadline computed in such a year is correct unless it happens to land on Lunar New
    Year or Diwali, which cannot be ruled out. The caller is told rather than reassured.
    """
    return [y for y in years if y not in LUNAR_NEW_YEAR or y not in DIWALI]


def is_holiday(d: date) -> tuple[bool, str | None]:
    """Cal. Civ. Code § 7: every Sunday, plus the Government Code list."""
    if d.weekday() == 6:
        return True, "Sunday"
    name = statutory_holidays(d.year).get(d)
    return (True, name) if name else (False, None)


# --------------------------------------------------------------------------------------
# Cal. Civ. Code §§ 10 and 14
# --------------------------------------------------------------------------------------


def add_calendar_months(start: date, months: int) -> date:
    """Add calendar months per Cal. Civ. Code § 14.

    Where the target month is shorter than the start day, the date clamps to the last day
    of that month: six months from August 31 is February 28 (or 29 in a leap year), not
    March 2 or 3. This is one of the two places hand-counting reliably diverges.
    """
    total = start.month - 1 + months
    year = start.year + total // 12
    month = total % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def roll_off_holiday(d: date) -> tuple[date, list[str]]:
    """Cal. Civ. Code § 10: if the last day is a holiday, it is also excluded.

    Excluding it moves the deadline to the next day that is not itself a holiday, so
    consecutive holidays chain (a Saturday holiday followed by Sunday rolls to Monday).
    """
    trail: list[str] = []
    cur = d
    while True:
        holiday, name = is_holiday(cur)
        if not holiday:
            return cur, trail
        trail.append(f"{cur.isoformat()} excluded ({name})")
        cur += timedelta(days=1)


# --------------------------------------------------------------------------------------
# The IMR clock
# --------------------------------------------------------------------------------------


@dataclass
class DeadlineResult:
    qualifying_event: date
    qualifying_event_basis: str
    deadline: date
    naive_deadline: date
    differs_from_naive: bool
    reasoning: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)


def qualifying_event(
    grievance_filed: date,
    plan_upheld_on: date | None = None,
    expedited: bool = False,
) -> tuple[date, str]:
    """Cal. Health & Safety Code § 1374.30(j)(3).

    The qualifying event is the earlier of the day the plan upheld the disputed decision
    and the day the enrollee stops being required to stay in the grievance process: the
    thirtieth day after filing, or the third day where § 1368.01 expedited review applies.
    """
    limit_days = 3 if expedited else 30
    # § 10: exclude the first day, so the clock starts the day after filing.
    exhaustion = grievance_filed + timedelta(days=limit_days)
    basis = (
        f"§ 1374.30(j)(3): grievance unresolved after {limit_days} days"
        f"{' (expedited, § 1368.01)' if expedited else ''}"
    )
    if plan_upheld_on is not None and plan_upheld_on < exhaustion:
        return plan_upheld_on, "§ 1374.30(j)(3): plan upheld the disputed decision"
    return exhaustion, basis


def imr_filing_deadline(
    denial_date: date,
    grievance_filed: date,
    plan_upheld_on: date | None = None,
    expedited: bool = False,
) -> DeadlineResult:
    """The last day to apply to DMHC for independent medical review.

    `denial_date` is not used in the computation. It is accepted so the result can show
    the naive count beside the statutory one, because counting six months from the denial
    letter is the error this exists to prevent.
    """
    event, basis = qualifying_event(grievance_filed, plan_upheld_on, expedited)

    six_months = add_calendar_months(event, 6)  # § 1374.30(k), § 14
    deadline, trail = roll_off_holiday(six_months)  # § 10

    reasoning = [
        f"Qualifying event {event.isoformat()} - {basis}",
        f"§ 1374.30(k): six months from the qualifying event -> {six_months.isoformat()}",
    ]
    reasoning.extend(trail)
    if deadline != six_months:
        reasoning.append(f"§ 10: deadline moves to {deadline.isoformat()}")

    naive, _ = roll_off_holiday(add_calendar_months(denial_date, 6))
    naive_plain = add_calendar_months(denial_date, 6)

    caveats = []
    if unverified_years([six_months.year, deadline.year]):
        caveats.append(
            "Lunar New Year and Diwali dates are not supplied for this year, so a "
            "deadline falling on either could not be checked. See § 6700."
        )

    return DeadlineResult(
        qualifying_event=event,
        qualifying_event_basis=basis,
        deadline=deadline,
        naive_deadline=naive_plain,
        differs_from_naive=(deadline != naive_plain),
        reasoning=reasoning,
        caveats=caveats,
    )

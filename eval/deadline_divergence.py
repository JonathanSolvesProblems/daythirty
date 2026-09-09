"""How far wrong does the intuitive count go, and in which direction?

This is exhaustive rather than sampled. It walks every grievance-filing date across a
real four-year calendar and every plan-response lag from 0 to 180 days, so there is no
set of cases for me to have chosen. Every rule applied comes from the statute.

The intuitive count modelled here is the one a person actually makes: "the plan finally
answered me, so I have six months from that." Cal. Health & Safety Code § 1374.30(j)(3)
says otherwise. The enrollee "shall not be required to participate in the plan's
grievance process for more than 30 days", so the clock starts on day 30 whether or not
the plan has answered. Every day the plan takes beyond 30 is a day the enrollee believes
they still have and does not.
"""

from __future__ import annotations

import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from daythirty.deadlines import (  # noqa: E402
    add_calendar_months,
    imr_filing_deadline,
    roll_off_holiday,
)

START = date(2026, 1, 1)
END = date(2029, 12, 31)
MAX_RESPONSE_LAG = 180


def main() -> None:
    total = 0
    late = 0            # intuitive deadline is LATER than the statute allows: rights lost
    overshoot_days: list[int] = []
    LATE_LAGS: list[int] = []
    arithmetic_only = 0  # qualifying event identified correctly, arithmetic still wrong
    holiday_moves = 0
    clamp_moves = 0

    day = START
    while day <= END:
        for lag in range(0, MAX_RESPONSE_LAG + 1):
            total += 1
            responded = day + timedelta(days=lag)

            r = imr_filing_deadline(
                denial_date=day,
                grievance_filed=day,
                plan_upheld_on=responded,
            )

            # The intuitive count: six months from the plan's final answer, no § 10.
            intuitive = add_calendar_months(responded, 6)

            if intuitive > r.deadline:
                late += 1
                overshoot_days.append((intuitive - r.deadline).days)
                LATE_LAGS.append(lag)

            # Now the narrower question: someone who correctly identifies the qualifying
            # event but does the date arithmetic by hand, without § 10 or § 14.
            raw = add_calendar_months(r.qualifying_event, 6)
            rolled, trail = roll_off_holiday(raw)
            if rolled != raw:
                holiday_moves += 1
                arithmetic_only += 1
            if r.qualifying_event.day != raw.day:
                clamp_moves += 1

        day += timedelta(days=1)

    print(f"window: {START} .. {END}, response lag 0..{MAX_RESPONSE_LAG} days")
    print(f"combinations evaluated: {total:,}\n")

    print("--- The qualifying-event error: counting from the plan's answer ---")
    print("Under § 1374.30(j)(3) the clock starts on day 30 whatever the plan does, so")
    print("if the plan answers on day D > 30, counting six months from that answer")
    print("puts the deadline roughly D - 30 days too late. 'Roughly' is load-bearing:")
    if overshoot_days:
        dev = [d - (l - 30) for d, l in zip(overshoot_days, LATE_LAGS)]
        exact = sum(1 for x in dev if x == 0)
        print(f"  overstatement equals (lag - 30) exactly in {exact/len(dev):.1%} of "
              f"late cases")
        print(f"  deviation from (lag - 30): min {min(dev)}, max {max(dev)} days")
        print("  the deviation comes from month lengths (§ 14) and the holiday")
        print("  exclusion (§ 10), so the rule of thumb is 'about lag - 30 days',")
        print("  and only the engine gives the actual date.")
        print(f"  worst case in this sweep: {max(overshoot_days)} days "
              f"(a plan answering on day {MAX_RESPONSE_LAG})")
    print()
    print("  NOT REPORTED AS A HEADLINE: the share of combinations that are late")
    print(f"  ({late:,} of {total:,}) is determined by the sweep range I chose, not by")
    print("  California. Quoting it would be my own parameter dressed as a finding.")
    print("  A real-world rate needs a published distribution of plan response times.")

    print("\n--- The arithmetic errors: right event, hand-counted date ---")
    print("These ARE parameter-free: they are properties of California's calendar.")
    print(f"deadlines landing on a statutory holiday, moved by Civ. Code § 10: "
          f"{holiday_moves/total:.1%}")
    print(f"  (Sundays under § 7, plus the Gov. Code § 6700 list)")
    print(f"month-length clamping under Civ. Code § 14: {clamp_moves/total:.1%}")
    print(f"  (six months from the 29th, 30th or 31st of a long month)")


if __name__ == "__main__":
    sys.exit(main())

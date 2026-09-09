"""Tests for the statutory deadline engine.

Each test names the provision it is testing. A test that cannot name a citation is
testing my opinion rather than the law, and does not belong here.
"""

from datetime import date

import pytest

from daythirty.deadlines import (
    add_calendar_months,
    imr_filing_deadline,
    is_holiday,
    qualifying_event,
    roll_off_holiday,
    statutory_holidays,
)


# --- Cal. Civ. Code § 14, "month" means a calendar month --------------------------------


def test_six_months_clamps_to_short_month():
    # Six months from August 31 is the last day of February, not March 2 or 3.
    assert add_calendar_months(date(2025, 8, 31), 6) == date(2026, 2, 28)


def test_six_months_clamps_in_leap_year():
    assert add_calendar_months(date(2027, 8, 31), 6) == date(2028, 2, 29)


def test_six_months_crosses_year_boundary():
    assert add_calendar_months(date(2025, 10, 15), 6) == date(2026, 4, 15)


def test_six_months_ordinary_case():
    assert add_calendar_months(date(2026, 1, 15), 6) == date(2026, 7, 15)


# --- Cal. Civ. Code § 7, holidays --------------------------------------------------------


def test_every_sunday_is_a_holiday():
    # 2026-09-06 is a Sunday.
    assert date(2026, 9, 6).weekday() == 6
    assert is_holiday(date(2026, 9, 6))[0] is True


def test_fixed_statutory_holiday():
    holiday, name = is_holiday(date(2026, 6, 19))
    assert holiday is True
    assert name == "Juneteenth"


def test_nth_weekday_holiday_mlk():
    # "The third Monday in January". In 2026 that is January 19.
    holidays = statutory_holidays(2026)
    assert holidays[date(2026, 1, 19)] == "Dr. Martin Luther King, Jr. Day"


def test_nth_weekday_holiday_last_monday_in_may():
    holidays = statutory_holidays(2026)
    assert date(2026, 5, 25) in holidays


def test_ordinary_weekday_is_not_a_holiday():
    assert is_holiday(date(2026, 9, 8))[0] is False


# --- Cal. Civ. Code § 10, the last day ---------------------------------------------------


def test_holiday_last_day_is_excluded():
    # 2026-12-25 is a holiday; the deadline moves off it.
    landed, trail = roll_off_holiday(date(2026, 12, 25))
    assert landed > date(2026, 12, 25)
    assert any("December 25" in t for t in trail)


def test_consecutive_holidays_chain():
    # 2027-12-25 is a Saturday, so the 26th is a Sunday: both are excluded and the
    # deadline lands on Monday the 27th.
    assert date(2027, 12, 25).weekday() == 5
    landed, trail = roll_off_holiday(date(2027, 12, 25))
    assert landed == date(2027, 12, 27)
    assert len(trail) == 2


def test_non_holiday_is_returned_unchanged():
    landed, trail = roll_off_holiday(date(2026, 9, 8))
    assert landed == date(2026, 9, 8)
    assert trail == []


# --- Cal. Health & Safety Code § 1374.30(j)(3), the qualifying event ---------------------


def test_qualifying_event_is_thirty_days_when_plan_stays_silent():
    event, basis = qualifying_event(date(2026, 3, 1))
    assert event == date(2026, 3, 31)
    assert "30 days" in basis


def test_qualifying_event_is_the_upheld_date_when_earlier():
    event, basis = qualifying_event(date(2026, 3, 1), plan_upheld_on=date(2026, 3, 12))
    assert event == date(2026, 3, 12)
    assert "upheld" in basis


def test_plan_upheld_after_thirty_days_does_not_extend_the_clock():
    # The enrollee "shall not be required to participate ... for more than 30 days", so a
    # late upholding cannot push the qualifying event out.
    event, _ = qualifying_event(date(2026, 3, 1), plan_upheld_on=date(2026, 5, 1))
    assert event == date(2026, 3, 31)


def test_expedited_review_uses_three_days():
    event, basis = qualifying_event(date(2026, 3, 1), expedited=True)
    assert event == date(2026, 3, 4)
    assert "expedited" in basis


# --- The whole clock, § 1374.30(k) -------------------------------------------------------


def test_deadline_runs_from_the_qualifying_event_not_the_denial():
    # A denial on Jan 5 with a grievance filed Feb 20 and no plan response: the qualifying
    # event is Mar 22, so the deadline is Sep 22, not Jul 5.
    r = imr_filing_deadline(
        denial_date=date(2026, 1, 5),
        grievance_filed=date(2026, 2, 20),
    )
    assert r.qualifying_event == date(2026, 3, 22)
    assert r.deadline == date(2026, 9, 22)
    assert r.naive_deadline == date(2026, 7, 5)
    assert r.differs_from_naive is True


def test_reasoning_cites_the_statute():
    r = imr_filing_deadline(date(2026, 1, 5), date(2026, 2, 20))
    joined = " ".join(r.reasoning)
    assert "1374.30(k)" in joined
    assert "1374.30(j)(3)" in joined


def test_unsupplied_astronomical_holidays_are_reported_not_hidden():
    # Lunar New Year and Diwali tables are empty, so every result must say so rather
    # than imply the year was fully checked.
    r = imr_filing_deadline(date(2026, 1, 5), date(2026, 2, 20))
    assert any("Lunar New Year" in c for c in r.caveats)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))

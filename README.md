# Overturn

An agent that works a California health insurance denial end to end: it tracks the
statutory clock, finds how people actually won cases like yours, drafts the appeal, and
stops for your approval before anything is filed.

Built with the Strands Agents SDK for the AWS Agents for Humans Hackathon.

> Not legal advice. This computes dates and drafts a document. It does not tell anyone
> what to do, and it does not practise law.

## Why

Last year insurers denied roughly **85 million** in-network claims on HealthCare.gov.
Consumers appealed **262,982** of them, an appeal rate **under 1%**, and insurers upheld
**66%** of the appeals they did receive.
([KFF, ACA Marketplace 2024](https://www.kff.org/patient-consumer-protections/claims-denials-and-appeals-in-aca-marketplace-plans-in-2024/))

When those denials instead reach an independent physician through California's
Independent Medical Review system, **72.3% were overturned in 2025**, up from 25% in 2001.
([California DMHC, published determinations](https://data.chhs.ca.gov/dataset/independent-medical-review-imr-determinations-trend))

An insurer reviewing its own denial upholds it two times in three. An independent
physician reviewing the same kind of denial overturns it nearly three times in four. The
entire gap is people not filing.

## The deadline nobody knows is running

Under `Cal. Health & Safety Code § 1374.30(j)(3)`, an enrollee "shall not be required to
participate in the plan's grievance process for more than 30 days." So thirty days after
the grievance is filed, whether or not the plan has answered, the qualifying event occurs
and `§ 1374.30(k)` starts a **six month** clock.

Counting six months from the plan's eventual answer therefore puts the deadline roughly
`(response time − 30)` days too late. If the plan takes four months to say no, someone
counting from the no is already about three months past their real deadline.

`src/overturn/deadlines.py` computes this from the statute. Every rule cites its
provision:

| Provision | Rule |
|---|---|
| `Health & Safety Code § 1374.30(k)` | six months from the qualifying event |
| `Health & Safety Code § 1374.30(j)(3)` | qualifying event: upheld, or 30 days (3 if expedited under § 1368.01) |
| `Civ. Code § 14` | "month" means a calendar month, so the date clamps to month length |
| `Civ. Code § 10` | exclude the first day, include the last, and exclude the last if it is a holiday |
| `Civ. Code § 7` | holidays are every Sunday plus the Government Code list |
| `Gov. Code § 6700` | the holiday list itself |

### What the arithmetic actually does

Swept exhaustively across every grievance-filing date from 2026 through 2029 and every
plan response time from 0 to 180 days (264,441 combinations, `eval/deadline_divergence.py`):

- **17.9%** of computed deadlines land on a day the statute excludes and must move under
  `§ 10`. That is a property of California's calendar, not of any case selection.
- **1.8%** are changed by month-length clamping under `§ 14`.
- The "response time minus 30 days" shortcut gives the right date only **29.2%** of the
  time, deviating by −5 to +3 days.

**What is deliberately not claimed:** the share of those 264,441 combinations where the
intuitive count runs late is 82.7%, and that figure is meaningless. It is fixed by the
0-to-180-day sweep I chose, not by anything about California. Turning it into a headline
would be a parameter of mine dressed up as a finding. A real-world rate needs a published
distribution of plan grievance response times, which is not yet wired in.

### Known gap

Two `§ 6700` holidays are defined astronomically rather than by calendar date: Lunar New
Year ("the second new moon following the winter solstice") and Diwali ("the 15th day of
the month of Kartik in the Hindu lunar calendar"). These cannot be derived from a
Gregorian calendar. They are supplied as data, the tables are currently empty, and every
result carries a caveat saying so rather than implying the year was fully checked.

## The corpus

California publishes every Independent Medical Review determination it has ever made:
**42,749** decisions from 2001 to 2026, each one made by a state-contracted independent
physician reviewer, including the reviewer's written reasoning.

Splits are temporal and leak-controlled (`eval/build_split.py`): precedent is retrieved
only from 2016 to 2024, held-out cases are 2025 to 2026, and the reviewer's narrative is
stripped from every held-out case because it states the verdict outright.

## Status

Under construction for the September 14 2026 deadline. See `DEMO_SCRIPT.md` for the
locked narration.

## Licence

MIT. See `LICENSE`.

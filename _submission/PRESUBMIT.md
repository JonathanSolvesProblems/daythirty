# Pre-submit gate, run 2026-09-12 (T-minus 48 hours)

Deadline: 2026-09-14, 5:00pm PDT.

## The eight checks

| # | Check | State | Evidence |
|---|---|---|---|
| 1 | The headline number exists as a number | **PASS** | `eval/ablation_report.json`, `eval/grounding_report.json`, `eval/intake_report.json`, `eval/coverage_report.json`, `eval/split_report.json`. No cell reads pending. `eval/check_claims.py` fails `pytest` if the README drifts from them. |
| 2 | Demo runs on real evidence, nothing seeded | **PASS, with a disclosure** | Every case is a real held-out DMHC determination. The deadline, precedent, letter and gate are produced by the system live. No seed script injects displayed state. The letter's letterhead is rendered because DMHC publishes determinations, not plan correspondence; the README says so under Honest limitations. |
| 3 | Every form field proofread rendered, logged out | **NOT YET POSSIBLE** | Nothing is submitted yet. Run this the moment the Devpost page exists: open it in a private window and read title, tagline and story top to bottom. |
| 4 | Drafting file contains only final values | **PASS** | `_submission/devpost.md`: one field per fenced block, no prose inside a block, notes below all values. The video field deliberately has no block until a URL exists. |
| 5 | Public-access check, logged out | **PARTIAL** | Repo: `https://github.com/JonathanSolvesProblems/daythirty` returns 200 unauthenticated and `raw.githubusercontent.com` serves the README. Clean clone runs `pytest` green with no setup. Video: not recorded. Project page: not submitted. Gallery: organiser-gated, not a signal; check once it opens. |
| 6 | Deliverables named and located | **PASS**, table below | |
| 7 | Headline number traces to the technology credited | **PASS** | Drafting model is `us.anthropic.claude-haiku-4-5-20251001-v1:0` in `src/daythirty/agent.py`; intake is `us.amazon.nova-lite-v1:0` in `src/daythirty/intake.py`; every report JSON records its `model` field; the README credits those exact models and nothing else. |
| 8 | The name's promise is visible in the demo | **PASS** | "Day 30 → the clock starts July 18, 2026, whether they answer or not" is drawn in the margin on screen (`_submission/shots/2-deadline.png`). |

## Deliverables, per the rules page

| Required | Where |
|---|---|
| Text description of purpose and functionality | `_submission/devpost.md`, section "About the project" |
| Public repo, MIT or Apache | https://github.com/JonathanSolvesProblems/daythirty, `LICENSE` is MIT |
| README | `README.md` at the repo root |
| Architecture diagram | `_submission/architecture.png`, and the mermaid source in `README.md` |
| Demo video, 5 minutes max, working project end to end | **NOT YET RECORDED.** Narration in `DEMO_SCRIPT.md`, 80 seconds. |
| AWS Builder ID | `jon.knight.andrei@gmail.com`, confirmed on the Builder ID profile page |
| Optional: live demo link | Not public. The web UI runs locally; the AgentCore runtime requires IAM to invoke. |
| Optional: builder.aws publication (up to +0.6) | `_submission/blog.md`, not yet published |
| Strands Agents explicitly named in the submission | Yes, in the pitch, the description and "Built with" |

## Gallery images for the form

`_submission/shots/1-first-load.png` through `5-filed.png`, light theme, 2560×1440.
Story order: the letter, the deadline drawn, the precedent, the gate, filed.

## What only Jonathan can do

1. Record the 80-second narration from `DEMO_SCRIPT.md` and hand over the audio.
2. Submit at https://agentsforhumans.devpost.com/ using `_submission/devpost.md`.
3. Publish `_submission/blog.md` at https://builder.aws.com/ and add the URL to the form.
4. After submitting, run check 3 and check 5: open the live project page logged out.

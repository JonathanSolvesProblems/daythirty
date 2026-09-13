# Agents for Humans: Day Thirty, a Strands agent that fights a health insurance denial and stops for your OK

Last year insurers denied about 85 million in-network claims on HealthCare.gov. Consumers appealed 262,982 of them. That is under one percent, and of those appeals, insurers upheld 66%.

Here is the number that made me build this. When the same kind of denial reaches an independent physician through California's Independent Medical Review system, **72.3% were overturned in 2025**. An insurer reviewing its own denial upholds it two times in three. An independent doctor reviewing it overturns it nearly three times in four. The whole gap is people not filing.

Part of why they do not file is a clock nobody tells them about. Under Cal. Health & Safety Code § 1374.30(j)(3), an enrollee "shall not be required to participate in the plan's grievance process for more than 30 days." Thirty days after you file a grievance, whether or not the plan has answered, a six month clock starts. If the plan takes four months to say no and you count six months from the no, you are three months late and never had a chance.

So: Day Thirty. An agent built on the Strands Agents SDK and Amazon Bedrock that works the denial end to end in the background, and interrupts a person exactly once, to approve the letter it wrote.

## What it does

1. **Amazon Nova reads the denial letter.** Real people have a letter from their plan, not database fields. Nova pulls out the condition, the treatment, the grounds and the dates.
2. **The deadline is computed from the statute.** No model touches the date. Every rule cites its provision: § 1374.30(k) for six months, § 1374.30(j)(3) for the qualifying event, Civ. Code § 14 for calendar-month arithmetic, § 10 for the holiday exclusion, § 7 and Gov. Code § 6700 for what counts as a holiday.
3. **It retrieves how California actually decided comparable denials.** The state publishes every IMR determination it has ever made: 42,749 of them, each decided by a state-contracted physician with the reasoning attached. Day Thirty argues only from what those reviewers found persuasive.
4. **Claude Haiku 4.5 drafts the appeal**, grounded in that record.
5. **It stops.** A Strands interrupt hands the exact letter to the person. Nothing is filed without approval, and the software does not file after it either: DMHC publishes no API for IMR applications, so approval produces the finished package with the due date and DMHC's real channels (online, fax, mail), and the person sends it. The page says "that last step is yours" rather than stamping something it did not do.

## The Strands pieces that mattered

Three tools and one interrupt, all plain `@tool` functions.

`compute_filing_deadline(denial_date, grievance_filed, plan_upheld_on, expedited)` is deterministic. It cites the statute and returns the date with its reasoning.

`find_precedent(diagnosis_category, diagnosis_subcategory, treatment_category, treatment_subcategory, grounds)` is retrieval over 22,090 published decisions. It returns the cohort overturn rate, a plain-English description of exactly which denials that rate covers, and exemplar reasoning from cases that won.

`file_appeal(tool_context, letter, deadline, summary)` is declared with `@tool(context=True)` and does one thing: it calls `tool_context.interrupt(name="approve_filing", reason={...})` with the exact letter.

That interrupt is the whole product claim in one call. The agent returns with `result.interrupts` populated, the person reads the letter, and the run resumes with an `interruptResponse` carrying their decision. The Everyday Agents track description says the best agents "only ping you when there's a real decision to make." This is that ping.

## Where I drew the line between model and code

Nova reads the letter, because reading unstructured correspondence needs a model. But I originally asked Nova for California's category directly and it scored 30% exact. Reading the misses showed why: the state files Speech Therapy under "Autism Related Tx" and Arthritis under "Immuno Disorders", classifying by patient context and disease mechanism. A letter does not contain that. It is not inference, it is a lookup, and the corpus already answered it 42,749 times. So the model reads and the state's own filings classify. That moved diagnosis category from 30.0% to 66.7% and treatment category from 33.3% to 83.3%, scored against the label California itself assigned.

Same logic on the deadline. A hallucinated date is the one error that cannot be recovered from, so the model never computes one.

## Switching the pieces off

Every entry at a sponsored hackathon says its tools were essential. I measured it. Same model, same six real denials, one tool removed at a time.

**Without California's record**, the model invented overturn rates of 40%, 50% and 60% in half the letters, with nothing to cite. The state's published figures for those cohorts run from 64% to 95%. With the record, 12 of 12 rate claims trace to the published figure.

**Without the statute engine**, told the rule in words, the model counted six months from the plan's answer and landed 86 days late in 5 of 6 cases. That is the appeal forfeited. Exactly the mistake the project exists to prevent.

## Are the exemplars about the case?

Retrieval is graded by the reviewer, not by me: for each held-out denial, the retrieved exemplars' reasoning is compared with the state physician's own findings for that case, which the agent never sees, against random cases and same-category random cases from the same pool. Retrieved exemplars score 0.245 mean similarity to the reviewer's reasoning against 0.093 for a same-category random draw and 0.035 for random, and beat the same-category draw in 87.8% of 2,754 cases. In the other 12.2% taxonomy matching did no better than category-random, almost all of it at the coarsest tier the floor allows, which is where semantic retrieval would go next.

## The check that fails the build

`eval/check_claims.py` reads every measurement report on disk and fails if the README quotes a number the data does not support. It runs under `pytest`. On its first run it found seven disagreements, two of them real: a combined figure the report file did not store, and a corpus count no script had written down. Prose drifts; data does not.

## What it does not do

It does not predict whether you will win. That was the original plan and it was measured out on day one: the held-out overturn base rate is 71.89%, precedent lookup scores 0.7234, a lift of +0.005. What is worth saying is not a prediction. The published overturn rate for a matched cohort ranges from 5.0% to 98.6%, and telling someone that California's reviewers overturned denials like theirs 98.6% of the time, or 5%, is a count over the state's record rather than a guess.

Two holidays in Gov. Code § 6700 are defined astronomically (Lunar New Year, Diwali) and are supplied as data with empty tables; every result says so. California only. Not legal advice.

## Running it on Amazon Bedrock AgentCore

The same agent is deployed on Amazon Bedrock AgentCore Runtime, built as an ARM64 container by CodeBuild, so it works in the background rather than on a laptop. Invoked with a real published GERD denial, the runtime returns in about 14 seconds with the intake, the statutory deadline and a drafted appeal stopped at the gate, and its response says in words that nothing has been filed. Locally, the web surface is one page: the insurer's typeset letter, marked up by hand in a litigator's ink as each tool returns, with a signature line for the gate, because you sign an appeal to file it.

## Try it

1. `git clone https://github.com/JonathanSolvesProblems/daythirty` and `cd daythirty`
2. `python -m venv .venv` then `.venv/Scripts/pip install -r requirements.txt`
3. `pytest` runs 20 tests with no AWS needed
4. `python scripts/fetch_corpus.py` pulls 85 MB from California's open data portal, then `python eval/build_split.py` and `python scripts/build_taxonomy.py`
5. `.venv/Scripts/uvicorn app:app --port 8030` and open the page it serves on port 8030

Click "Work this denial", and sign it or don't. It needs AWS credentials with Bedrock access in us-east-1 (Claude Haiku 4.5 and Amazon Nova Lite through the us inference profiles). A run takes 15 to 35 seconds and costs about a cent.

Demo video (2 min): https://www.youtube.com/watch?v=cKe6B5hYq5s

Code, evaluation reports and honest limitations: https://github.com/JonathanSolvesProblems/daythirty

Built for the AWS Agents for Humans hackathon, Everyday Agents track.

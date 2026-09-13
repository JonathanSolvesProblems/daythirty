# Devpost submission, Day Thirty

## Project name

```
Day Thirty
```

## Elevator pitch

```
Your insurance appeal, argued from 22,090 decisions California's own physicians published, ready to sign before the day-thirty clock runs out.
```

## Track

```
Everyday Agents
```

## Repository

```
https://github.com/JonathanSolvesProblems/daythirty
```

## Built with

```
strands-agents, amazon-bedrock, amazon-bedrock-agentcore, amazon-nova, claude-haiku-4-5, python, boto3, fastapi, uvicorn, server-sent-events, javascript, html, css, svg, docker, aws-codebuild, amazon-ecr, amazon-cloudwatch, pytest, playwright, california-dmhc-open-data
```

## About the project

```
## Inspiration

Last year insurers denied about 85 million in-network claims on HealthCare.gov. Consumers appealed 262,982 of them, under 1%, and insurers upheld 66% of the appeals they received (KFF, 2024). When the same kind of denial reaches an independent physician through California's Independent Medical Review, 72.3% were overturned in 2025.

An insurer reviewing its own denial upholds it two times in three. An independent doctor overturns it nearly three times in four. The entire gap is people not filing.

Part of why they do not file is a clock nobody tells them about. Under Cal. Health & Safety Code § 1374.30(j)(3), an enrollee "shall not be required to participate in the plan's grievance process for more than 30 days." So thirty days after you file a grievance, whether or not your plan has answered, a six month clock starts. If the plan takes four months to say no and you count six months from the no, you are already three months late. That is where the name comes from.

## What it does

Day Thirty works a California health insurance denial end to end, in the background, and interrupts only for one decision.

1. Amazon Nova reads the denial letter and pulls out the condition, the treatment, the grounds and the dates. California's own category taxonomy is then resolved by lookup against the state's filings, not by the model.
2. The filing deadline is computed from the statute, with every rule citing its provision: HSC § 1374.30(k) and (j)(3), Civ. Code § 14, § 10, § 7, Gov. Code § 6700. No model touches the date, because a hallucinated deadline is the one error that cannot be recovered from.
3. It retrieves how California actually decided comparable denials, from the 22,090 Independent Medical Review determinations the state published between 2016 and 2024, each one made by a state-contracted physician reviewer with the reasoning attached.
4. Claude Haiku 4.5 on Bedrock drafts the appeal, arguing only from what those reviewers found persuasive.
5. It stops. A Strands interrupt hands the exact letter to a person. Nothing is filed without approval, and nothing is filed by the software after it either: DMHC has no API, so approval produces the finished application with the due date and DMHC's real channels (online, fax, mail), and the person sends it. The page says "that last step is yours" on screen.

## How I built it

Strands Agents SDK with three tools and a human interrupt, on Amazon Bedrock. Two models doing different jobs: Nova Lite reads unstructured correspondence, Haiku 4.5 writes the letter. Two deterministic engines the models are not allowed near: the statute clock and the taxonomy lookup. The gate is `tool_context.interrupt`: the run returns with the letter in `result.interrupts`, a person decides, and the run resumes with their answer.

The corpus is public data from California's Department of Managed Health Care: 42,749 published determinations from 2001 to 2026, fetched by script. Splits are temporal and leak-controlled. Precedent comes only from 2016 to 2024; the 3,276 held-out cases are 2025 to 2026, with the reviewer's narrative stripped because it states the verdict.

The same agent is deployed on Amazon Bedrock AgentCore Runtime (ARM64 container built by CodeBuild), so it works in the background rather than on a laptop. Invoked with a real published denial it returns in about 14 seconds with the intake, the statutory deadline and the drafted appeal stopped at the gate. The web surface is a single page: the insurer's typeset letter, marked up by hand in a litigator's ink, with a signature line for the gate, because you sign an appeal to file it.

## What I measured, and who graded it

Every number below was graded by something I did not write.

Deadline to a drafted appeal waiting at the approval gate: 15.1 seconds median, gate reached 5 of 5 across five different real denials.

Nova reading the denial letter, scored against the category California itself assigned to that case: grounds 30/30, denial date 30/30, treatment category 25/30 exact, diagnosis category 20/30 exact and 26/30 allowing the state's own synonyms.

Grounding, checked mechanically against what the tools returned and with a negative control that must catch seven planted fabrications: 18/18 numeric claims and 12/13 named authorities traced to the record across 20 letters, 7/7 fabrications caught. The one miss is named in the README.

Retrieval coverage across all 3,276 held-out denials: 91.5% get a published overturn rate for their situation, 84.1% get a usable exemplar to argue from, 72.4% at the tightest match. The published rate ranges from 5.0% to 98.6%, which is why the agent reports it rather than predicting an outcome: outcome prediction was measured on day one at +0.005 over a constant and dropped.

## The ablation

Same model, same six real denials, one tool switched off at a time.

Without California's record, the model invented overturn rates of 40%, 50% and 60% in half the letters, with nothing to cite. With it, 12 of 12 rate claims trace to the state's published figure.

Without the statute engine, on the timeline where the plan sat on the grievance for 120 days, the model counted six months from the plan's answer and landed 86 days late in 5 of 6 cases. That is the appeal forfeited. It was told the rule in words and still did not apply it.

## Challenges I ran into

Outcome prediction was the original headline and it was dead: the held-out overturn base rate is 71.89% and precedent lookup scores 0.7234, a lift of +0.005. The product had to be a reporter, not a predictor.

The first live run quoted a pharmacy-wide overturn rate as though it were specific to psoriasis biologics. The tool now returns a plain-English description of exactly what population the rate covers, and the prompt forbids attaching a broad rate to a specific condition.

Asking Nova for California's category directly scored 30%. Reading the misses showed the state files Speech Therapy under Autism Related Tx and Arthritis under Immuno Disorders, classifying by patient context. That is not inference, it is a lookup, so the boundary moved: the model reads, the state's own filings classify. Diagnosis went from 30.0% to 66.7% and treatment from 33.3% to 83.3%.

A Nova embeddings index for the 15.9% of denials with no close taxonomy match was built and abandoned on throttling. The script stays; the README says the index is not built.

## Accomplishments that I'm proud of

eval/check_claims.py reads every measurement report and fails the build if the README quotes a number the data does not support. On its first run it found seven disagreements, two of them real. It runs under pytest, and it now audits the gallery captions on this page too.

The ablation above. Every entry at a sponsored hackathon says its tools were essential; I switched them off one at a time and measured what each one contributed.

The page used to stamp FILED after approval when nothing had been submitted, because DMHC has no API. I caught it before recording the demo and fixed the product rather than the wording: approval now hands over the finished application, the due date and the real channels, and the page says "that last step is yours". The tagline says "ready to sign" instead of "filed" for the same reason.

## What I learned

A model told the rule in words still gets the date wrong. Given "the clock starts thirty days after the grievance, whether or not the plan answers", Haiku counted from the plan's answer in 5 of 6 late-answer cases. Anything where a wrong answer cannot be recovered from belongs in code that cites its provision, and the model should be handed the result.

The boundary between model and lookup is an empirical question, not a design taste. Nova reads a letter well and classifies it badly, because California's categories encode patient context that a letter does not contain. Moving that one step from the model to the state's own filings doubled the score.

A sentence must never be more real than the artifact behind it. "Filed" was one word, and it would have put a claim on the judged surface that the code did not back.

Reporting beats predicting when the honest lift over a constant is +0.005. The published rate for a matched cohort runs from 5.0% to 98.6%, and telling someone that number, with its exact scope, is worth more than a guess dressed as a forecast.

## What's next for Day Thirty

The astronomical holidays in Gov. Code § 6700 (Lunar New Year, Diwali) are supplied as data and the tables are empty; every result says so. Semantic retrieval for the taxonomy gap. Other states' clocks. And the last step: DMHC publishes no API for IMR applications, so today approval hands the person the finished package and the channels, and they send it. If DMHC ever exposes one, that is where the gate's "yes" would go.
```

## Video

```
https://www.youtube.com/watch?v=cKe6B5hYq5s
```

## Architecture diagram (file upload)

```
_submission/architecture.png
```

## AWS Builder ID

```
jon.knight.andrei@gmail.com
```

## URL to your live demo link (optional)

Left blank. The web surface runs locally against the judge's own AWS credentials, and the AgentCore runtime needs IAM in my account. See the notes below if a public deployment is stood up before the deadline.

## Testing instructions

```
Requirements: Python 3.11 or newer, and AWS credentials with Amazon Bedrock access in us-east-1 (Claude Haiku 4.5 and Amazon Nova Lite through the us.* inference profiles).

git clone https://github.com/JonathanSolvesProblems/daythirty
cd daythirty
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      (macOS/Linux: .venv/bin/pip)
pytest                                  20 tests: statute engine, precedent, claims check. No AWS needed.
python scripts/fetch_corpus.py          85 MB from California DMHC's open data portal
python eval/build_split.py              temporal, leak-controlled split
python scripts/build_taxonomy.py        the state's own category filings
.venv/Scripts/uvicorn app:app --port 8030

Open http://127.0.0.1:8030. A real published denial is loaded; the arrows pick another. Click "Work this denial" and watch the letter get marked up: the intake, the statutory deadline with its provisions, the published overturn rate for this kind of denial and what persuaded the reviewers, then the drafted appeal. The run stops at the signature line. "Sign it" stamps APPROVED, writes the application package to outbox/ and shows the due date and DMHC's filing channels. "Don't sign" and nothing leaves. A run takes 15 to 35 seconds and costs about a cent in Bedrock usage.

The same run in a terminal: python run_agent.py (asks for approval) or python run_agent.py --approve.

Measurements: python eval/check_claims.py verifies every number in the README against the reports in eval/. Each report can be regenerated (eval/intake_accuracy.py, eval/grounding.py, eval/precedent_coverage.py, eval/ablation.py); each makes Bedrock calls.

AgentCore: the deployed runtime is invokable only with IAM in my account, so it is not public. scripts/invoke_agentcore.py shows the call, and the README records a real invocation with its timing.
```

---

## Notes, not for pasting

- The elevator pitch is 142 characters. It carries the two things no competitor can say: the corpus, and the day-thirty mechanism. It says "ready to sign", not "filed", because DMHC has no API and the software does not file; the sentence must never be more real than the artifact.
- Every figure in "About the project" matches README.md, which `eval/check_claims.py` holds to the reports on disk. If a number changes, change the README first, let the check pass, then update this file.
- Track: Everyday Agents was chosen over Professional and Good Neighbor. The track description ("only ping you when there's a real decision to make") is the approval gate in the organisers' own words. Professional is a defensible alternative framed around patient advocates; Good Neighbor is where Instanter most likely sits and is the head-to-head to avoid.
- Video is the only field that cannot be filled until it is recorded.

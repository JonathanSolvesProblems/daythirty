# YouTube, Day Thirty demo

## Title

```
Day Thirty: an AI agent that argues your insurance appeal from 22,090 real decisions
```

## Description

```
Last year insurers denied about 85 million in-network claims on HealthCare.gov and fewer than 1 in 100 were appealed. When a denial reaches an independent physician in California, 72% get overturned. The gap is people not filing, and part of the reason is a deadline nobody tells them about: thirty days after you file a grievance with your plan, a six month clock starts, whether or not the plan has answered.

Day Thirty works a California health insurance denial end to end. You give it the denial letter. It computes the filing deadline straight out of the statute, looks up how California's independent reviewers actually decided comparable denials, drafts the appeal from what those reviewers found persuasive, and then stops. A person reads the letter and signs it. Nothing is filed without that signature, and the software never claims a filing it did not make: on approval you get the finished application, the due date, and exactly where the state takes it.

Chapters
0:00 The numbers
0:13 The clock nobody knows is running
0:29 You give it the letter
0:39 The deadline, computed from the statute
0:52 How California actually decided cases like this
1:09 The appeal, drafted
1:16 It stops. A person signs.
1:21 Approved and ready to file
1:28 Running on Amazon Bedrock AgentCore
1:39 72% overturned, 66% upheld
1:47 The only thing left is to sign

How it is built
Strands Agents SDK on Amazon Bedrock. Amazon Nova Lite reads the denial letter. Claude Haiku 4.5 drafts the appeal. Two things no model is allowed to touch: the deadline (a statute engine citing Health and Safety Code 1374.30, Civil Code 7, 10 and 14, Government Code 6700) and California's own category taxonomy (a lookup against the state's filings). The approval gate is a Strands interrupt. The same agent is deployed on Amazon Bedrock AgentCore.

Every number in the video has a source on screen at the moment it is spoken.
KFF, Claims Denials and Appeals in ACA Marketplace Plans in 2024: https://www.kff.org/patient-consumer-protections/claims-denials-and-appeals-in-aca-marketplace-plans-in-2024/
California DMHC, Independent Medical Review determinations, 42,749 published decisions: https://data.chhs.ca.gov/dataset/independent-medical-review-imr-determinations-trend
Cal. Health and Safety Code 1374.30: https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=HSC&sectionNum=1374.30.

Code, evaluation reports and honest limitations: https://github.com/JonathanSolvesProblems/daythirty
Built for the AWS Agents for Humans hackathon, Everyday Agents track.

Not legal advice. California only. Every case shown is a real published determination; the letterhead is rendered because the state publishes decisions, not plan correspondence.
```

## Tags

```
Day Thirty, health insurance appeal, insurance denial, denied claim, independent medical review, IMR, California DMHC, appeal deadline, prior authorization denial, medical necessity denial, Strands Agents, Amazon Bedrock, Bedrock AgentCore, AWS Agents for Humans, AWS hackathon, AI agent, Claude Haiku, Amazon Nova, human in the loop, healthcare AI, patient advocacy, KFF claims denials
```

## Notes, not for pasting

- Chapter times are beat starts in `broll/demo.mp4`: narration time plus the 3.5 s title card.
- Tags are 411 characters, under YouTube's 500 limit.
- Once the video is public, put its URL in the Video block of `devpost.md`.

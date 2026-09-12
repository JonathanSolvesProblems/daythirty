# Day Thirty, demo script

Written before the first commit, per the focus rule, and revised on 2026-09-12 against
the judging criteria and against what the product actually does. Narration is locked
first; footage is cut to the narration, never the other way round.

**Target: about 95 seconds.** Hard ceiling 5:00 by the rules, but the archive says 60 to
90, and the two sentences that push this past 90 are the two the Technical
Implementation criterion asks for by name (Strands, AgentCore).

**Name:** Day Thirty. It names the mechanism the whole project rests on, from
`HSC § 1374.30(j)(3)`: on the thirtieth day after the grievance is filed, the clock starts
whether or not the plan has answered. The name creates a question and the demo answers it
in the first fifteen seconds, which is the point. It promises nothing the product cannot
deliver.

---

## Narration

**[0:00]**
Last year insurers denied about eighty-five million in-network claims on HealthCare.gov.
Fewer than one in a hundred were ever appealed.

**[0:08]**
Here is why.

*(on screen: the denial letter, first load)*

To fight a denial in California, you file a grievance with your plan. Thirty days later,
whether or not your plan has answered, a six month clock starts. Almost nobody knows it
started. If your plan takes four months to say no, and you count six months from the no,
you are already three months past your deadline.

**[0:26]**
This is Day Thirty, a Strands agent on Amazon Bedrock. You give it the denial letter. It
does the rest.

*(on screen: Run. The letter gets marked up.)*

It reads the letter and computes the deadline straight out of the statute: Health and
Safety Code 1374.30, six months from the day-thirty qualifying event. No model touches
that date.

**[0:42]**
Then it looks up how people actually won.

*(on screen: the precedent note, the rate, what persuaded the reviewers)*

California publishes every independent medical review decision it has ever made,
forty-two thousand of them. Day Thirty pulls the ones closest to this case and reads what
the reviewing physician found persuasive.

**[0:56]**
And it writes the appeal.

*(on screen: the letter composing)*

Not a template. The grounds that won in cases like this one.

**[1:03]**
Then it stops.

*(on screen: the signature line)*

That is a Strands interrupt. The agent pauses mid-run and will not continue without you.
You read it. You sign it.

**[1:12]**
*(sign. The APPROVED stamp, the "Ready to file" note with the due date and the channels.)*

Now you have the finished application, the date it has to be in by, and exactly where the
state takes it. The same agent runs on Bedrock AgentCore, so it works in the background,
not on your laptop.

**[1:24]**
When a denial like this reaches an independent physician in California, seventy-two
percent get overturned. When the insurer reviews its own denial, it upholds sixty-six
percent.

**[1:33]**
The entire gap is people not filing.

With Day Thirty, the only thing left is to sign.

---

## Where each judging criterion lands

| Criterion | Where it is in the 95 seconds |
|---|---|
| Technological Implementation | "a Strands agent on Amazon Bedrock", "That is a Strands interrupt", "runs on Bedrock AgentCore". The interrupt is on screen as the signature line. |
| Design | The whole thing happens on one page a person would actually use: a letter, marked up by hand, a signature line, a stamp. No console, no JSON. |
| Potential Impact | 85 million denials, under 1% appealed, 72% overturned by an independent physician versus 66% upheld by the insurer. Every number has an outside source. |
| Creativity & Originality | The day-thirty clock from the statute and the 42,749-decision corpus. Nobody else in the field is arguing from the state's own reviewers. |
| Presentation | Problem in the first 25 seconds, the product end to end in the next 60, the number that makes it matter at the end. One case, one take. |

## Rules this script is holding itself to

- **Opens on a person and a number from outside this repo**, never on the architecture.
  KFF for the appeal rate, California DMHC for the overturn rate, the Legislature for the
  statute. A judge can check all three without reading a line of my code.
- **The climax is the signature and what it produces**, not an accuracy table. The eval is
  a closing receipt elsewhere and it is not in this script at all.
- **The word "deterministic" never appears.** The deadline engine is deterministic and
  that is an engineering fact for the README, not a pitch line.
- **Every frame is real, and no sentence is more real than the frame.** Real published
  case, real statute, real corpus. Nothing seeded. The script says "you give it the
  letter" because that is what happens, and "ready to file" because DMHC has no API and
  the software does not file. If a scene cannot be shot against real data it gets cut,
  not faked.
- **No em-dashes.** In the narration or anywhere else.
- **The approval gate is on screen** because the track description explicitly asks for an
  agent that "only pings you when there's a real decision to make."

## Shot list (what has to exist for this to be filmable)

1. A denial letter on the page, pasted in or loaded from the published record.
2. The deadline computed on screen with the statute subdivision visible.
3. Precedent: the published rate and what persuaded the reviewers, from the DMHC corpus.
4. The drafted appeal, composing live.
5. The signature line, and a person signing.
6. The APPROVED stamp with the due date, the outbox path and DMHC's channels.

All six exist as of 2026-09-12: `_submission/shots/1-first-load.png` through
`5-approved.png`.

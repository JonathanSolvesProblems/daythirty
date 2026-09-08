# Overturn — demo script

Written before the first commit, per the focus rule. Narration is locked first; footage
is cut to the narration, never the other way round.

**Target: 80 seconds.** Hard ceiling 5:00 by the rules, but the archive says 60 to 90.

**Name:** Overturn. It is the word California's own reviewers use in the determination
field (`Overturned Decision of Health Plan`). The name promises an outcome, and the demo
pays it with the state's published rate rather than with a claim of my own.

---

## Narration

**[0:00]**
Last year insurers denied about eighty-five million in-network claims on HealthCare.gov.
Fewer than one in a hundred were ever appealed.

**[0:09]**
This is why.

*(on screen: a denial letter)*

To fight it you file a grievance with your plan. Thirty days after that, whether or not
your plan has answered you, a six month clock starts running. Almost nobody knows it
started. If your plan takes four months to say no, and you count six months from the no,
you are already three months past the deadline and you never had a chance.

**[0:24]**
Overturn runs in the background and does the whole thing.

*(on screen: agent picks up the denial on its own)*

It reads the denial and computes the deadline straight out of the statute. Health and
Safety Code section 1374.30, subdivision (k), six months from the qualifying event in
subdivision (j)(3).

**[0:38]**
Then it looks up how people actually won.

*(on screen: precedent retrieval)*

California publishes every independent medical review decision it has ever made. Forty-two
thousand of them. Overturn pulls the ones closest to this case and reads what the
reviewing physician actually found persuasive.

**[0:52]**
And it writes the appeal.

*(on screen: the letter composing)*

Not a template. The specific grounds that won in cases like this one.

**[1:01]**
Then it stops.

*(on screen: approval gate)*

It will not send anything without you.

**[1:07]**
*(approve, file)*

**[1:12]**
When a denial like this reaches an independent physician in California, seventy-two
percent get overturned. When the insurer reviews its own denial, it upholds sixty-six
percent.

**[1:22]**
The entire gap is people not filing.

Overturn files.

---

## Rules this script is holding itself to

- **Opens on a person and a number from outside this repo**, never on the architecture.
  KFF for the appeal rate, California DMHC for the overturn rate, the Legislature for the
  statute. A judge can check all three without reading a line of my code.
- **The climax is the appeal being filed**, not an accuracy table. The eval is a closing
  receipt elsewhere, at most fifteen seconds, and it is not in this script at all.
- **The word "deterministic" never appears.** The deadline engine is deterministic and
  that is an engineering fact for the README, not a pitch line.
- **Every frame is real.** Real published case, real statute, real corpus. Nothing seeded.
  If a scene cannot be shot against real data it gets cut, not faked.
- **The approval gate is on screen** because the track description explicitly asks for an
  agent that "only pings you when there's a real decision to make."

## Shot list (what has to exist for this to be filmable)

1. A denial letter the agent ingests on its own, from a watched inbox or drop.
2. The deadline computed on screen with the statute subdivision visible.
3. Precedent retrieval showing real case IDs from the DMHC corpus.
4. The drafted appeal, composing live.
5. The approval interrupt, and a human approving it.
6. Confirmation of filing.

Anything not on this list is out of scope until all six are shot.

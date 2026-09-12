"""Day Thirty on Amazon Bedrock AgentCore Runtime.

The same agent as `run_agent.py` and `app.py`, hosted in AWS's managed runtime so it
runs in the background rather than on a laptop. One invocation reads the denial, computes
the deadline from the statute, retrieves the state's published precedent, drafts the
appeal, and stops at the gate. The response carries the drafted letter and the gate
payload. Nothing is filed by this runtime: filing is a human decision, and the response
says so.

Payload:
  {"letter": "<denial letter text>", "grievance_filed": "YYYY-MM-DD",
   "plan_upheld_on": "YYYY-MM-DD" | null, "age": "...", "gender": "..."}

  agentcore configure --entrypoint agentcore_app.py --name daythirty
  agentcore deploy
  agentcore invoke '{"letter": "...", "grievance_filed": "2026-06-18"}'
"""

from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from pathlib import Path

from bedrock_agentcore.runtime import BedrockAgentCoreApp

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from daythirty.agent import build_agent  # noqa: E402
from daythirty.intake import parse_denial_letter  # noqa: E402

app = BedrockAgentCoreApp()


@app.entrypoint
def work_denial(payload: dict) -> dict:
    t0 = time.time()
    letter = (payload or {}).get("letter", "")
    if not letter.strip():
        return {"error": "payload.letter is required: the text of the denial letter"}

    intake = parse_denial_letter(letter)
    denial_date = intake.denial_date or (date.today() - timedelta(days=95)).isoformat()
    grievance = payload.get("grievance_filed") or (
        date.fromisoformat(denial_date) + timedelta(days=9)
    ).isoformat()
    upheld = payload.get("plan_upheld_on")
    status = (
        f"My plan answered the grievance on {upheld} and upheld the denial."
        if upheld else "My plan has not answered the grievance."
    )

    prompt = f"""My health plan denied coverage and I want to appeal to the state.

Denial letter date: {denial_date}
I filed a grievance with my plan on: {grievance}
{status}

What was denied, read from my denial letter:
- Diagnosis category: {intake.diagnosis_category}
- Diagnosis: {intake.diagnosis_subcategory or intake.condition_text}
- Treatment category: {intake.treatment_category}
- Treatment refused: {intake.treatment_subcategory or intake.treatment_text}
- The plan's stated grounds: {intake.grounds}
- Me: {payload.get('age', '')}, {payload.get('gender', '')}

Work out my deadline, find out how cases like mine were actually decided, and draft
my appeal."""

    agent = build_agent()
    result = agent(prompt)

    out = {
        "intake": {
            "condition": intake.condition_text,
            "treatment": intake.treatment_text,
            "grounds": intake.grounds,
            "diagnosis_category": intake.diagnosis_category,
            "treatment_category": intake.treatment_category,
        },
        "seconds": round(time.time() - t0, 1),
        "filed": False,
    }
    if result.interrupts:
        itr = result.interrupts[0]
        reason = itr.reason if isinstance(itr.reason, dict) else {}
        out["gate"] = {
            "interrupt_id": itr.id,
            "deadline": reason.get("deadline"),
            "summary": reason.get("summary"),
            "letter": reason.get("letter", ""),
        }
        out["status"] = (
            "Stopped at the approval gate. The letter is drafted and nothing has been "
            "filed. Filing requires a person to approve this exact letter."
        )
    else:
        out["status"] = "The agent finished without reaching the approval gate."
        out["text"] = str(result)
    return out


if __name__ == "__main__":
    app.run()

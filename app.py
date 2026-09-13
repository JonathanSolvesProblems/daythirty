"""Day Thirty, the web surface.

One page. A denial letter goes in, and every stage streams back as it happens so the
page can mark the letter up in the order a person would: read it, work out the clock,
look up the precedent, draft, then stop at the gate.

  .venv/Scripts/uvicorn app:app --port 8030
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent  # noqa: E402

from daythirty.agent import DMHC_FILING, build_agent, filing_package  # noqa: E402
from daythirty.intake import parse_denial_letter, render_denial_letter  # noqa: E402
from daythirty.precedent import PrecedentIndex  # noqa: E402

app = FastAPI(title="Day Thirty")
WEB = ROOT / "web"
TEST = ROOT / "data" / "split" / "test.jsonl"
# Where an approved application lands, as a file a person can print or upload. DMHC has
# no API, so this is the real end of the run: the package, not a pretend submission.
OUTBOX = ROOT / "outbox"

_index: PrecedentIndex | None = None
_cases: list[dict] | None = None
RUNS: dict[str, dict] = {}

# Spend guard for the public deployment. Each run is a Bedrock call that costs about a
# cent, and a public page can be hammered, so the deployment sets a daily cap and a
# per-address hourly cap through the environment. Both default to off, so a local run
# behaves exactly as before. Counts live in memory: a restart resets them, which is fine
# for a cap whose job is to bound a bad day, not to meter.
DAILY_CAP = int(os.environ.get("DAYTHIRTY_DAILY_CAP", "0"))
PER_IP_HOURLY = int(os.environ.get("DAYTHIRTY_PER_IP_HOURLY", "0"))
_day: list = [date.today(), 0]
_by_ip: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _guard(request: Request) -> None:
    now = time.time()
    if DAILY_CAP:
        if _day[0] != date.today():
            _day[0], _day[1] = date.today(), 0
        if _day[1] >= DAILY_CAP:
            raise HTTPException(429, "This public demo has used its runs for today. The "
                                     "video shows the full run, and the repo runs it locally.")
        _day[1] += 1
    if PER_IP_HOURLY:
        ip = _client_ip(request)
        recent = [t for t in _by_ip.get(ip, []) if now - t < 3600]
        if len(recent) >= PER_IP_HOURLY:
            raise HTTPException(429, f"That is {PER_IP_HOURLY} runs in an hour from this "
                                     "address. Try again later, or run it from the repo.")
        recent.append(now)
        _by_ip[ip] = recent


def index() -> PrecedentIndex:
    global _index
    if _index is None:
        _index = PrecedentIndex()
    return _index


_rows: list[dict] | None = None
_usable: dict[int, bool] = {}


def rows() -> list[dict]:
    global _rows
    if _rows is None:
        _rows = [json.loads(line) for line in TEST.open(encoding="utf-8")]
    return _rows


def nth_usable(n: int) -> tuple[int, dict]:
    """The n-th held-out case that has usable precedent, found lazily.

    Checking all 3,276 up front takes over a minute; checking on demand takes
    milliseconds per case. Real, published, never seeded.
    """
    n = max(0, n)
    seen = 0
    for i, rec in enumerate(rows()):
        if i not in _usable:
            _usable[i] = bool(index().query(rec["case"], k=1).exemplars)
        if _usable[i]:
            if seen == n:
                return i, rec
            seen += 1
    return nth_usable(0)


@app.get("/")
def home():
    return FileResponse(WEB / "index.html")


@app.get("/api/config")
def config():
    """What the page needs to know about where it is running.

    On the public deployment the page opens with a note saying so: this is a preview
    with a daily cap, the same agent is deployed on Bedrock AgentCore, and the way to
    judge it properly is the README's testing steps. Locally nothing is shown.
    """
    return {
        "public": bool(os.environ.get("DAYTHIRTY_PUBLIC")),
        "daily_cap": DAILY_CAP,
        "per_ip_hourly": PER_IP_HOURLY,
        "repo": "https://github.com/JonathanSolvesProblems/daythirty",
    }


@app.get("/api/case")
def get_case(i: int = 0):
    """A real held-out case rendered as the letter the plan would have sent."""
    _, rec = nth_usable(i)
    denial = date.today() - timedelta(days=95)
    return {
        "index": max(0, i),
        "total": len(rows()),
        "letter": render_denial_letter(rec["case"], denial.isoformat()),
        "denial_date": denial.isoformat(),
        "grievance_filed": (denial + timedelta(days=9)).isoformat(),
        "state_filed_as": {
            "diagnosis": rec["case"]["DiagnosisCategory"],
            "treatment": rec["case"]["TreatmentCategory"],
        },
        "age": rec["case"]["AgeRange"],
        "gender": rec["case"]["PatientGender"],
    }


class RunRequest(BaseModel):
    letter: str
    grievance_filed: str
    plan_upheld_on: str | None = None
    age: str = ""
    gender: str = ""


class Decision(BaseModel):
    approved: bool
    note: str = ""


def _emit(q: queue.Queue, kind: str, **payload) -> None:
    q.put({"type": kind, "t": round(time.time(), 3), **payload})


def _unwrap(result):
    """Pull the tool's own return value out of Strands' ToolResult envelope."""
    try:
        content = result.get("content") if isinstance(result, dict) else None
        if content:
            block = content[0]
            if "json" in block:
                return block["json"]
            if "text" in block:
                try:
                    return json.loads(block["text"])
                except (TypeError, ValueError):
                    return block["text"]
        json.dumps(result)
        return result
    except TypeError:
        return str(result)


def _work(run_id: str, req: RunRequest) -> None:
    run = RUNS[run_id]
    q: queue.Queue = run["q"]
    t0 = time.time()
    try:
        _emit(q, "stage", name="intake", label="Reading the letter")
        intake = parse_denial_letter(req.letter)
        _emit(
            q, "intake",
            condition=intake.condition_text,
            treatment=intake.treatment_text,
            grounds=intake.grounds,
            denial_date=intake.denial_date,
            diagnosis_category=intake.diagnosis_category,
            treatment_category=intake.treatment_category,
            corrections=intake.corrections,
        )

        agent = build_agent()
        run["agent"] = agent

        def before(event: BeforeToolCallEvent) -> None:
            name = (event.tool_use or {}).get("name") or "tool"
            _emit(q, "stage", name=name, label={
                "compute_filing_deadline": "Computing the deadline from the statute",
                "find_precedent": "Reading how California decided cases like this",
                "file_appeal": "Stopping for your approval",
            }.get(name, name))

        def after(event: AfterToolCallEvent) -> None:
            name = (event.tool_use or {}).get("name") or "tool"
            # Strands wraps a tool's return value as
            #   {"toolUseId", "status", "content": [{"text": "<json>"}]}
            # so the dict the tool returned is a JSON string one level down.
            result = _unwrap(event.result)
            _emit(q, "tool", name=name, result=result)

        agent.add_hook(before, BeforeToolCallEvent)
        agent.add_hook(after, AfterToolCallEvent)

        def on_text(**kw):
            data = kw.get("data")
            if data:
                _emit(q, "text", delta=data)

        agent.callback_handler = on_text

        denial_date = intake.denial_date or (date.today() - timedelta(days=95)).isoformat()
        status = (
            f"My plan answered the grievance on {req.plan_upheld_on} and upheld the denial."
            if req.plan_upheld_on else "My plan has not answered the grievance."
        )
        prompt = f"""My health plan denied coverage and I want to appeal to the state.

Denial letter date: {denial_date}
I filed a grievance with my plan on: {req.grievance_filed}
{status}

What was denied, read from my denial letter:
- Diagnosis category: {intake.diagnosis_category}
- Diagnosis: {intake.diagnosis_subcategory or intake.condition_text}
- Treatment category: {intake.treatment_category}
- Treatment refused: {intake.treatment_subcategory or intake.treatment_text}
- The plan's stated grounds: {intake.grounds}
- Me: {req.age}, {req.gender}

Work out my deadline, find out how cases like mine were actually decided, and draft
my appeal."""

        _emit(q, "stage", name="agent", label="Working the denial")
        result = agent(prompt)

        if result.interrupts:
            itr = result.interrupts[0]
            reason = itr.reason if isinstance(itr.reason, dict) else {}
            run["interrupt_id"] = itr.id
            run["gate"] = reason
            _emit(
                q, "gate",
                letter=reason.get("letter", ""),
                deadline=reason.get("deadline"),
                summary=reason.get("summary"),
                seconds=round(time.time() - t0, 1),
            )
        else:
            _emit(q, "done", approved=False, text=str(result),
                  seconds=round(time.time() - t0, 1),
                  note="The agent finished without reaching the approval gate.")
            run["finished"] = True
    except Exception as exc:  # noqa: BLE001
        _emit(q, "error", message=f"{type(exc).__name__}: {exc}")
        run["finished"] = True


@app.post("/api/run")
def start_run(req: RunRequest, request: Request):
    _guard(request)
    run_id = uuid.uuid4().hex[:12]
    RUNS[run_id] = {"q": queue.Queue(), "agent": None, "interrupt_id": None,
                    "finished": False, "started": time.time()}
    threading.Thread(target=_work, args=(run_id, req), daemon=True).start()
    return {"run_id": run_id}


@app.get("/api/run/{run_id}/events")
def events(run_id: str):
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404)

    def gen():
        q: queue.Queue = run["q"]
        idle = 0
        while True:
            try:
                ev = q.get(timeout=1.0)
                idle = 0
                yield f"data: {json.dumps(ev)}\n\n"
                if ev["type"] in ("done", "error"):
                    return
            except queue.Empty:
                idle += 1
                yield ": keepalive\n\n"
                if idle > 600:
                    return

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/run/{run_id}/decide")
def decide(run_id: str, d: Decision):
    run = RUNS.get(run_id)
    if not run or not run.get("agent") or not run.get("interrupt_id"):
        raise HTTPException(409, "no gate is waiting on this run")

    def resume():
        q: queue.Queue = run["q"]
        try:
            _emit(q, "stage", name="decision",
                  label="Preparing the application" if d.approved else "Not filing")
            note = d.note or ("approved by the patient" if d.approved else
                              "declined by the patient")
            resumed = run["agent"]([{
                "interruptResponse": {
                    "interruptId": run["interrupt_id"],
                    "response": {"approved": d.approved, "note": note},
                }
            }])
            gate = run.get("gate") or {}
            outbox = None
            if d.approved:
                OUTBOX.mkdir(exist_ok=True)
                path = OUTBOX / f"{date.today().isoformat()}-imr-application-{run_id}.txt"
                path.write_text(
                    filing_package(gate.get("letter", ""), gate.get("deadline", ""),
                                   gate.get("summary", ""), note),
                    encoding="utf-8",
                )
                outbox = path.relative_to(ROOT).as_posix()
            _emit(q, "done", approved=d.approved, text=str(resumed),
                  deadline=gate.get("deadline"), outbox=outbox, filing=DMHC_FILING)
        except Exception as exc:  # noqa: BLE001
            _emit(q, "error", message=f"{type(exc).__name__}: {exc}")
        run["finished"] = True

    threading.Thread(target=resume, daemon=True).start()
    return {"ok": True}

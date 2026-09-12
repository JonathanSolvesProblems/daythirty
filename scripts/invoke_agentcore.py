"""Invoke the deployed Day Thirty runtime on Bedrock AgentCore with a real denial.

  python scripts/invoke_agentcore.py            # case 0
  python scripts/invoke_agentcore.py --case 5

The runtime ARN is read from .bedrock_agentcore.yaml, which `agentcore deploy` writes.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import boto3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daythirty.intake import render_denial_letter  # noqa: E402
from daythirty.precedent import PrecedentIndex  # noqa: E402

TEST = ROOT / "data" / "split" / "test.jsonl"


def runtime_arn() -> str:
    cfg = (ROOT / ".bedrock_agentcore.yaml").read_text(encoding="utf-8")
    m = re.search(r"agent_arn:\s*(arn:aws:bedrock-agentcore:\S+)", cfg)
    if not m:
        raise SystemExit("no agent_arn in .bedrock_agentcore.yaml; run `agentcore deploy`")
    return m.group(1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", type=int, default=0)
    args = ap.parse_args()

    idx = PrecedentIndex()
    rows = [json.loads(line) for line in TEST.open(encoding="utf-8")]
    usable = [r for r in rows if idx.query(r["case"], k=1).exemplars]
    rec = usable[args.case % len(usable)]
    c = rec["case"]
    denial = date.today() - timedelta(days=95)
    payload = {
        "letter": render_denial_letter(c, denial.isoformat()),
        "grievance_filed": (denial + timedelta(days=9)).isoformat(),
        "age": c["AgeRange"], "gender": c["PatientGender"],
    }

    arn = runtime_arn()
    print(f"runtime : {arn}")
    print(f"case    : {c['DiagnosisSubCategory']} / {c['TreatmentSubCategory']} / {c['Type']}")
    print(f"state's determination (the runtime cannot see this): "
          f"{'OVERTURNED' if rec['label'] else 'UPHELD'}\n")

    client = boto3.client("bedrock-agentcore", region_name="us-east-1")
    t0 = time.time()
    resp = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=uuid.uuid4().hex + uuid.uuid4().hex[:5],  # >= 33 chars
        payload=json.dumps(payload).encode("utf-8"),
    )
    body = resp["response"].read().decode("utf-8")
    dt = time.time() - t0
    try:
        out = json.loads(body)
    except ValueError:
        print(body[:2000]); return 1

    print(f"round trip: {dt:.1f}s   (runtime reports {out.get('seconds')}s of work)\n")
    print("intake  :", json.dumps(out.get("intake"), indent=None))
    print("status  :", out.get("status"))
    gate = out.get("gate") or {}
    if gate:
        print(f"deadline: {gate.get('deadline')}")
        print(f"summary : {gate.get('summary')}")
        letter = gate.get("letter", "")
        print(f"\n--- drafted letter, {len(letter):,} chars, first 700 ---\n{letter[:700]}")
    print(f"\nfiled: {out.get('filed')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

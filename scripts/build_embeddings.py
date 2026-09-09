"""Embed the exemplar pool with Amazon Nova so retrieval can reach past the taxonomy.

Why this exists, in one measurement: 15.9% of held-out denials get no usable exemplar,
because California's category tree separates cases that medicine does not. A hepatitis
antiviral denial and a psoriasis biologic denial are both "Pharmacy / Medical Necessity"
and nothing tighter connects them to anything. Taxonomy matching either finds an exact
sibling or finds nothing.

Semantic similarity over the reviewers' own reasoning is the honest fix, and it is the
job Nova embeddings is actually for rather than a sponsor model bolted on for a
scorecard.

Only overturned cases are embedded, because that is the only pool exemplars are drawn
from: the appeal argues from what persuaded a reviewer.

  python scripts/build_embeddings.py            # resumable, safe to re-run
  python scripts/build_embeddings.py --limit 200
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
import numpy as np
from botocore.config import Config

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from daythirty.precedent import is_clean_reasoning, reasoning_of  # noqa: E402

TRAIN = ROOT / "data" / "split" / "train.jsonl"
OUT_DIR = ROOT / "data" / "index"
VECTORS = OUT_DIR / "exemplar_vectors.npy"
MANIFEST = OUT_DIR / "exemplar_manifest.jsonl"

MODEL = "amazon.nova-2-multimodal-embeddings-v1:0"
REGION = "us-east-1"
DIMS = 3072
WORKERS = 4

_local = threading.local()


def client():
    if not hasattr(_local, "rt"):
        _local.rt = boto3.client(
            "bedrock-runtime",
            region_name=REGION,
            config=Config(
                retries={"max_attempts": 10, "mode": "adaptive"},
                read_timeout=60,
            ),
        )
    return _local.rt


def embed(text: str, purpose: str = "GENERIC_INDEX", attempts: int = 8) -> list[float]:
    """Embed one record, backing off hard on throttling.

    This account's quota for the embeddings model is low: 16 concurrent workers lost
    46% of calls to ThrottlingException. boto3's adaptive retry alone was not enough,
    so throttles are also retried here with exponential backoff and jitter.
    """
    body = {
        "taskType": "SINGLE_EMBEDDING",
        "singleEmbeddingParams": {
            "embeddingPurpose": purpose,
            "text": {"truncationMode": "END", "value": text},
        },
    }
    delay = 1.0
    last: Exception | None = None
    for _ in range(attempts):
        try:
            resp = client().invoke_model(modelId=MODEL, body=json.dumps(body))
            return json.loads(resp["body"].read())["embeddings"][0]["embedding"]
        except Exception as exc:  # noqa: BLE001
            last = exc
            if "Throttl" not in type(exc).__name__ and "Throttl" not in str(exc):
                raise
            time.sleep(delay + random.random() * 0.5)
            delay = min(delay * 2, 20.0)
    raise last if last else RuntimeError("embed failed")


def load_pool(limit: int | None) -> list[dict]:
    """The exemplar pool: overturned cases with reasoning clean enough to argue from."""
    pool = []
    with TRAIN.open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r["label"] != 1:
                continue
            reasoning = reasoning_of(r.get("findings", ""))
            if len(reasoning) < 120 or not is_clean_reasoning(reasoning):
                continue
            pool.append({"year": r["year"], "case": r["case"], "reasoning": reasoning})
            if limit and len(pool) >= limit:
                break
    return pool


def text_for(rec: dict) -> str:
    """What gets embedded: the case in words, then the reviewer's reasoning."""
    c = rec["case"]
    return (
        f"Diagnosis: {c['DiagnosisCategory']}, {c['DiagnosisSubCategory']}. "
        f"Treatment requested: {c['TreatmentCategory']}, {c['TreatmentSubCategory']}. "
        f"Denial grounds: {c['Type']}.\n\n{rec['reasoning']}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=WORKERS)
    args = ap.parse_args()

    pool = load_pool(args.limit)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"exemplar pool: {len(pool):,} overturned decisions with usable reasoning")

    if VECTORS.exists() and MANIFEST.exists():
        existing = sum(1 for _ in MANIFEST.open(encoding="utf-8"))
        if existing == len(pool):
            print(f"already built: {existing:,} vectors. Delete data/index to rebuild.")
            return 0
        print(f"found {existing:,} of {len(pool):,}, rebuilding")

    vecs = np.zeros((len(pool), DIMS), dtype=np.float16)
    done = [0]
    failed: list[int] = []
    lock = threading.Lock()
    t0 = time.time()

    def work(i: int) -> None:
        try:
            v = embed(text_for(pool[i]))
            vecs[i] = np.asarray(v, dtype=np.float16)
        except Exception as exc:  # noqa: BLE001
            with lock:
                failed.append(i)
                if len(failed) <= 3:
                    print(f"  fail {i}: {type(exc).__name__}: {str(exc)[:90]}")
        with lock:
            done[0] += 1
            if done[0] % 500 == 0:
                rate = done[0] / (time.time() - t0)
                left = (len(pool) - done[0]) / max(rate, 0.01)
                print(f"  {done[0]:,}/{len(pool):,}  {rate:.1f}/s  ~{left/60:.1f} min left")

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(work, range(len(pool))))

    ok = [i for i in range(len(pool)) if i not in set(failed)]
    print(f"\nembedded {len(ok):,} of {len(pool):,} in {(time.time()-t0)/60:.1f} min")
    if failed:
        print(f"failed: {len(failed):,}. They are dropped from the index rather than "
              f"stored as zero vectors, which would silently match everything.")

    vecs = vecs[ok]
    np.save(VECTORS, vecs)
    with MANIFEST.open("w", encoding="utf-8") as fh:
        for i in ok:
            fh.write(json.dumps(pool[i]) + "\n")

    print(f"wrote {VECTORS.relative_to(ROOT)}  shape={vecs.shape}  "
          f"{VECTORS.stat().st_size/1e6:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

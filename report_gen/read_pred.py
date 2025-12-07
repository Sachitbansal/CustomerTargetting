#!/usr/bin/env python3
"""
STEP 1 — CLUSTER AGGREGATOR (REDIS)

✔ Properly returns batch data to Pathway
✔ Only keeps predicted_eligible == True
✔ Aggregates cluster batches in memory
✔ Emits complete JSON payload with all fields populated
✔ Stores predictions in Redis (not CSV)
"""

import pathway as pw
from pathlib import Path
import sys
import json
from collections import defaultdict
import os

# ------------------------------------------------
# CONFIG
# ------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
ROOT = CURRENT_DIR.parent
sys.path.append(str(ROOT))

K_BATCH = 5

LOG_FILE = CURRENT_DIR / "aggregator.log"

NATS_URI = "nats://localhost:4222"
INPUT_TOPIC = "leads.callCarLoan"
OUTPUT_TOPIC = "reports.cluster.ready"

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "1"))
PREDICTION_CACHE_KEY = "prediction_cache"

cluster_buffers = defaultdict(list)

# ------------------------------------------------
# REDIS CONNECTION
# ------------------------------------------------
import redis
import pickle

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=False
)

# ------------------------------------------------
# LOGGING
# ------------------------------------------------
def log(msg: str):
    line = f"[ClusterAgg] {msg}\n"
    with open(LOG_FILE, "a") as f:
        f.write(line)
    print(line, end="")

# ------------------------------------------------
# SCHEMA
# ------------------------------------------------
class PredictionSchema(pw.Schema):
    customer_id: str
    predicted_eligible: bool
    cluster_id: int
    confidence_score: float
    similar_customers: str   # JSON string

# Output schema for batches
class BatchSchema(pw.Schema):
    cluster_id: int
    count: int
    customers: str  # JSON string of customer list

# ------------------------------------------------
# CACHE WRITER (Redis-based)
# ------------------------------------------------
def append_to_cache(row):
    """Store prediction in Redis hash keyed by customer_id."""
    customer_id = row.get("customer_id")
    if not customer_id:
        return
    
    # Store as pickled dict for consistency with MASTERFILE storage
    redis_client.hset(PREDICTION_CACHE_KEY, customer_id, pickle.dumps(row))
    log(f"📝 Cached prediction for {customer_id} in Redis")

# ------------------------------------------------
# MAIN UDF → Returns tuple of (cluster_id, count, customers_json)
# ------------------------------------------------
def handle_prediction(customer_id, predicted_yes, cluster_id, score, exemplars_json):
    
    # ⛔ Ignore negative predictions
    if not predicted_yes:
        return None, None, None

    # Parse similar_customers
    try:
        exemplars = json.loads(exemplars_json)
    except Exception:
        exemplars = []

    row = {
        "customer_id": customer_id,
        "cluster_id": int(cluster_id),
        "score": float(score),
        "exemplars": exemplars
    }

    append_to_cache(row)

    # Add to cluster buffer
    cluster_buffers[cluster_id].append(row)
    size = len(cluster_buffers[cluster_id])

    log(f"CUST {customer_id} → CL {cluster_id} | score={score:.3f} | {size}/{K_BATCH}")

    # ✔ Trigger batch
    if size >= K_BATCH:
        batch = cluster_buffers[cluster_id].copy()
        cluster_buffers[cluster_id].clear()

        log(f"✔ CLUSTER {cluster_id} READY → sending {len(batch)} customers to Step-2\n")

        # Return as tuple: (cluster_id, count, customers_json_string)
        return int(cluster_id), len(batch), json.dumps(batch)

    # Not ready yet - return None tuple
    return None, None, None

# ------------------------------------------------
# PATHWAY PIPELINE
# ------------------------------------------------
def run_cluster_aggregator():

    log("=== Cluster Aggregator Started ===")
    log(f"Listening on topic: {INPUT_TOPIC}")
    log(f"Publishing batches to: {OUTPUT_TOPIC}")
    log(f"K_BATCH = {K_BATCH}")
    log(f"Cache: Redis @ {REDIS_HOST}:{REDIS_PORT} (key: {PREDICTION_CACHE_KEY})\n")

    # 1. Stream from NATS
    stream = pw.io.nats.read(
        uri=NATS_URI,
        topic=INPUT_TOPIC,
        format="json",
        schema=PredictionSchema
    )

    # 2. Apply UDF - returns tuple (cluster_id, count, customers_json)
    processed = stream.select(
        result=pw.apply(
            handle_prediction,
            pw.this.customer_id,
            pw.this.predicted_eligible,
            pw.this.cluster_id,
            pw.this.confidence_score,
            pw.this.similar_customers
        )
    )

    # 3. Unpack the tuple into separate columns
    unpacked = processed.select(
        cluster_id=pw.apply(lambda x: x[0], pw.this.result),
        count=pw.apply(lambda x: x[1], pw.this.result),
        customers=pw.apply(lambda x: x[2], pw.this.result)
    )

    # 4. Filter out None results (incomplete batches)
    batches = unpacked.filter(pw.this.cluster_id.is_not_none())

    # 5. Publish to NATS
    pw.io.nats.write(
        batches,
        uri=NATS_URI,
        topic=OUTPUT_TOPIC,
        format="json"
    )

    pw.run()


if __name__ == "__main__":
    run_cluster_aggregator()
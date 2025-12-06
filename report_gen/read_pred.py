#!/usr/bin/env python3
"""
STEP 1 — CLUSTER AGGREGATOR (ROLLING CACHE)

✔ Properly returns batch data to Pathway
✔ Only keeps predicted_eligible == True
✔ Aggregates cluster batches in memory
✔ Emits complete JSON payload with all fields populated
✔ Maintains rolling cache with max 500 entries (FIFO)
"""

import pathway as pw
from pathlib import Path
import sys
import json
import csv
from collections import defaultdict, deque

# ------------------------------------------------
# CONFIG
# ------------------------------------------------
CURRENT_DIR = Path(__file__).resolve().parent
ROOT = CURRENT_DIR.parent
sys.path.append(str(ROOT))

K_BATCH = 5
MAX_CACHE_SIZE = 500

CACHE_FILE = CURRENT_DIR / "prediction_cache.csv"
LOG_FILE = CURRENT_DIR / "aggregator.log"

NATS_URI = "nats://localhost:4222"
INPUT_TOPIC = "leads.callCarLoan"
OUTPUT_TOPIC = "reports.cluster.ready"

cluster_buffers = defaultdict(list)

# Rolling cache to maintain only last 500 entries
cache_queue = deque(maxlen=MAX_CACHE_SIZE)

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
# CACHE INITIALIZATION
# ------------------------------------------------
def initialize_cache():
    """Load existing cache entries into memory (up to MAX_CACHE_SIZE)."""
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, 'r') as f:
                reader = csv.DictReader(f)
                entries = list(reader)
                
                # Keep only the last MAX_CACHE_SIZE entries
                if len(entries) > MAX_CACHE_SIZE:
                    entries = entries[-MAX_CACHE_SIZE:]
                
                for entry in entries:
                    cache_queue.append(entry)
                
                log(f"Loaded {len(cache_queue)} entries from existing cache")
        except Exception as e:
            log(f"⚠ Error loading cache: {e}")
            cache_queue.clear()

# ------------------------------------------------
# ROLLING CACHE WRITER
# ------------------------------------------------
def write_cache_to_file():
    """Write the entire cache queue to file (overwrites)."""
    try:
        with open(CACHE_FILE, 'w', newline='') as f:
            if len(cache_queue) == 0:
                return
            
            # Get fieldnames from first entry
            fieldnames = list(cache_queue[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            writer.writeheader()
            for entry in cache_queue:
                writer.writerow(entry)
                
    except Exception as e:
        log(f"❌ Error writing cache: {e}")

def append_to_cache(row):
    """
    Add new entry to rolling cache.
    Automatically removes oldest entry if cache exceeds MAX_CACHE_SIZE.
    """
    # Convert row to string values for CSV compatibility
    csv_row = {k: str(v) for k, v in row.items()}
    
    # Add to queue (automatically removes oldest if at max capacity)
    cache_queue.append(csv_row)
    
    cache_size = len(cache_queue)
    log(f"Cache: {cache_size}/{MAX_CACHE_SIZE} entries")
    
    # Write entire cache to file
    write_cache_to_file()

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
        "exemplars": json.dumps(exemplars)  # Keep as JSON string for CSV
    }

    append_to_cache(row)

    # Add to cluster buffer
    cluster_buffers[cluster_id].append({
        "customer_id": customer_id,
        "cluster_id": int(cluster_id),
        "score": float(score),
        "exemplars": exemplars  # Keep as list for batch processing
    })
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
    log(f"MAX_CACHE_SIZE = {MAX_CACHE_SIZE}")
    log(f"Cache file: {CACHE_FILE}\n")

    # Initialize cache from existing file
    initialize_cache()

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
import sys
from pathlib import Path

# --- PATH SETUP ---
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
# ------------------

from pathlib import Path
import sys

# Add parent directory to path BEFORE importing transactionPublisher modules
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

import threading
import pathway as pw
from transactionPublisher.schema import TxnSchema
from transactionPublisher.streamer import stream_csv_as_file

# Paths
CSV_PATH = Path(__file__).parent.parent / 'streaming_transactions.csv'
TEMP_STREAM_FILE = Path(__file__).parent.parent / 'temp_txn_stream.csv'

NATS_URI = "nats://localhost:4222"
NATS_TOPIC = "transactions.stream"
TARGET_TPS = 1000

def run_publisher():
    print("═══════════════════════════════════════════════")
    print("           TRANSACTION PUBLISHER               ")
    print("═══════════════════════════════════════════════")

    # Start Streaming Thread
    t = threading.Thread(
        target=stream_csv_as_file,
        args=(str(CSV_PATH), str(TEMP_STREAM_FILE), TARGET_TPS),
        daemon=True
    )
    t.start()

    # 1. Read CSV (txn_datetime stays as String - no conversion needed!)
    tx = pw.io.csv.read(
        str(TEMP_STREAM_FILE),
        schema=TxnSchema,
        mode="streaming",
        autocommit_duration_ms=100
    )

    # 2. NO DATETIME CONVERSION HERE
    # We keep txn_datetime as a string in the format from CSV ("%Y-%m-%d")
    # The enrichment node will parse it when it receives from NATS

    # 3. Publish to NATS (as JSON with string datetime)
    pw.io.nats.write(
        tx,
        uri=NATS_URI,
        topic=NATS_TOPIC,
        format="json"
    )

    print(f"✓ Publishing to NATS topic '{NATS_TOPIC}' at {TARGET_TPS} TPS")
    print("✓ Pathway publisher is running...\n")
    pw.run()

if __name__ == "__main__":
    run_publisher()

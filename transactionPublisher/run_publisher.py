# publisher/run_publisher.py

from pathlib import Path
import sys

# Add parent directory to path BEFORE importing transactionPublisher modules
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

import threading
import pathway as pw
from transactionPublisher.schema import TxnSchema
from transactionPublisher.streamer import stream_csv_as_file

CSV_PATH = './streaming_transactions.csv'

TEMP_STREAM_FILE = "./transactionPublisher/temp_txn_stream.csv"

NATS_URI = "nats://localhost:4222"
NATS_TOPIC = "transactions.stream"

TARGET_TPS = 20  # transactions per second


def run_publisher():
    print("═══════════════════════════════════════════════")
    print("           TRANSACTION PUBLISHER               ")
    print("═══════════════════════════════════════════════")

    # Start Python streaming thread
    t = threading.Thread(
        target=stream_csv_as_file,
        args=(CSV_PATH, TEMP_STREAM_FILE, TARGET_TPS),
        daemon=True
    )
    t.start()

    # Pathway ingests the growing temp CSV
    tx = pw.io.csv.read(
        TEMP_STREAM_FILE,
        schema=TxnSchema,
        mode="streaming",
        autocommit_duration_ms=100
    )

    # Pathway publishes rows to NATS
    pw.io.nats.write(
        tx,
        uri=NATS_URI,
        topic=NATS_TOPIC,
        format="json"
    )

    print("✓ Pathway publisher is running...\n")
    pw.run()


if __name__ == "__main__":
    run_publisher()

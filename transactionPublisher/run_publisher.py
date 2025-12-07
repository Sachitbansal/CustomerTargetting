import sys
from pathlib import Path

# --- PATH SETUP ---
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))
# ------------------

import threading
import pathway as pw
from transactionPublisher.schema import TxnSchema
from transactionPublisher.streamer import stream_csv_as_file

# Import metrics
from monitoring.metrics import (
    initialize_metrics,
    get_metrics_manager,
    record_nats_publish,
    set_nats_connection_status,
    update_memory_usage
)

import psutil  # For memory monitoring
import os

# Paths
CSV_PATH = Path(__file__).parent.parent / 'streaming_transactions.csv'
TEMP_STREAM_FILE = Path(__file__).parent.parent / 'temp_txn_stream.csv'

NATS_URI = "nats://localhost:4222"
NATS_TOPIC = "transactions.stream"
TARGET_TPS = 200

# Metrics port for Publisher
METRICS_PORT = 8001


def monitor_memory():
    """Background thread to monitor memory usage"""
    process = psutil.Process(os.getpid())
    metrics_manager = get_metrics_manager()
    
    while True:
        try:
            memory_bytes = process.memory_info().rss
            update_memory_usage("publisher", memory_bytes)
            metrics_manager.update_component_uptime()
            time.sleep(5)  # Update every 5 seconds
        except Exception as e:
            print(f"⚠️  Memory monitoring error: {e}")
            time.sleep(5)


def run_publisher():
    print("═══════════════════════════════════════════════")
    print("           TRANSACTION PUBLISHER               ")
    print("═══════════════════════════════════════════════")
    
    # Initialize Prometheus metrics
    metrics_manager = initialize_metrics("publisher", port=METRICS_PORT)
    print()
    
    # Start memory monitoring thread
    memory_thread = threading.Thread(target=monitor_memory, daemon=True)
    memory_thread.start()

    # Start Streaming Thread
    stream_thread = threading.Thread(
        target=stream_csv_as_file,
        args=(str(CSV_PATH), str(TEMP_STREAM_FILE), TARGET_TPS),
        daemon=True
    )
    stream_thread.start()

    try:
        # Set NATS connection status (will be updated when connection succeeds)
        set_nats_connection_status("publisher", True)
        
        # 1. Read CSV (txn_datetime stays as String)
        tx = pw.io.csv.read(
            str(TEMP_STREAM_FILE),
            schema=TxnSchema,
            mode="streaming",
            autocommit_duration_ms=100
        )

        # 2. Add a select to track NATS publishes
        # We'll use a UDF to increment metrics
        @pw.udf
        def track_nats_publish(customer_id: str) -> str:
            """Track each message published to NATS"""
            record_nats_publish(NATS_TOPIC, success=True)
            return customer_id
        
        tx_tracked = tx.select(
            *pw.this,
            _tracked_id=track_nats_publish(pw.this.customer_id)
        )

        # 3. Publish to NATS
        pw.io.nats.write(
            tx_tracked,
            uri=NATS_URI,
            topic=NATS_TOPIC,
            format="json"
        )

        print(f"✓ Publishing to NATS topic '{NATS_TOPIC}' at {TARGET_TPS} TPS")
        print(f"✓ Metrics available at: http://localhost:{METRICS_PORT}/metrics")
        print("✓ Pathway publisher is running...\n")
        
        pw.run()
        
    except Exception as e:
        print(f"❌ Publisher error: {e}")
        set_nats_connection_status("publisher", False)
        record_nats_publish(NATS_TOPIC, success=False, error_type=type(e).__name__)
        metrics_manager.record_error(type(e).__name__)
        raise


if __name__ == "__main__":
    run_publisher()
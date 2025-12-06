# transactionPublisher/streamer.py (Updated with Metrics)

import time
from pathlib import Path
import sys

# Add monitoring to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from monitoring.metrics import (
    record_csv_row_injected,
    update_current_tps,
    record_io_wait,
    MetricsTimer
)


def stream_csv_as_file(source_csv, temp_stream_file, tps=20):
    """
    Reads a CSV file, and continuously streams rows into a temp file.
    Pathway will read this temp file in streaming mode.
    
    Now with Prometheus metrics tracking!
    """

    print(f"Loading CSV: {source_csv}")
    
    # Time the CSV read operation
    read_start = time.time()
    with open(source_csv, "r") as f:
        lines = f.readlines()
    read_duration = time.time() - read_start
    record_io_wait("read", read_duration)

    header = lines[0]
    rows = lines[1:]

    # Ensure directory for stream file
    Path(temp_stream_file).parent.mkdir(parents=True, exist_ok=True)

    # Start the streaming file fresh
    write_start = time.time()
    with open(temp_stream_file, "w") as f:
        f.write(header)
    write_duration = time.time() - write_start
    record_io_wait("write", write_duration)

    print(f"Streaming {len(rows)} rows at {tps} TPS → {temp_stream_file}")

    idx = 0
    interval = 1.0 / tps
    
    # TPS tracking variables
    rows_in_last_second = 0
    last_tps_update = time.time()

    while True:
        t0 = time.time()

        # Append the next row with timing
        append_start = time.time()
        with open(temp_stream_file, "a") as f:
            f.write(rows[idx])
        append_duration = time.time() - append_start
        
        # Record metrics
        record_io_wait("append", append_duration)
        record_csv_row_injected()
        
        rows_in_last_second += 1
        idx = (idx + 1) % len(rows)

        # Update TPS gauge every second
        if time.time() - last_tps_update >= 1.0:
            actual_tps = rows_in_last_second / (time.time() - last_tps_update)
            update_current_tps(actual_tps)
            rows_in_last_second = 0
            last_tps_update = time.time()

        # TPS control
        elapsed = time.time() - t0
        remaining = interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

        # Light logging
        if idx % 100 == 0:
            print(f"[STREAM] wrote {idx} rows", end="\r")
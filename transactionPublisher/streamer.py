# publisher/streamer.py

import time
from pathlib import Path

def stream_csv_as_file(source_csv, temp_stream_file, tps=20):
    """
    Reads a CSV file, and continuously streams rows into a temp file.
    Pathway will read this temp file in streaming mode.
    """

    print(f"Loading CSV: {source_csv}")
    with open(source_csv, "r") as f:
        lines = f.readlines()

    header = lines[0]
    rows = lines[1:]

    # Ensure directory for stream file
    Path(temp_stream_file).parent.mkdir(parents=True, exist_ok=True)

    # Start the streaming file fresh
    with open(temp_stream_file, "w") as f:
        f.write(header)

    print(f"Streaming {len(rows)} rows at {tps} TPS → {temp_stream_file}")

    idx = 0
    interval = 1.0 / tps

    while True:
        t0 = time.time()

        # Append the next row
        with open(temp_stream_file, "a") as f:
            f.write(rows[idx])

        idx = (idx + 1) % len(rows)

        # TPS control
        elapsed = time.time() - t0
        remaining = interval - elapsed
        if remaining > 0:
            time.sleep(remaining)

        # Light logging
        if idx % 100 == 0:
            print(f"[STREAM] wrote {idx} rows", end="\r")

import pandas as pd
import os
import time
from pathlib import Path

# Define paths
STREAM_PATH = "data/stream_tables"
PRESENT_PATH = "data/present_tables"
TRANS_FILE = "trans.csv"

def stream_trans(batch_size=10, delay=5):
    """
    Stream rows from stream_tables/trans.csv to present_tables/trans.csv

    Parameters:
    -----------
    batch_size : int
        Number of rows to add from stream to present in each iteration
    delay : float
        Time delay in seconds between each batch update

    Returns:
    --------
    dict : Statistics about the streaming process
    """
    stream_file = os.path.join(STREAM_PATH, TRANS_FILE)
    present_file = os.path.join(PRESENT_PATH, TRANS_FILE)

    # Check if files exist
    if not os.path.exists(stream_file):
        print(f"Error: Stream file not found at {stream_file}")
        return {"error": "Stream file not found", "rows_added": 0}

    try:
        # Load the stream data
        stream_df = pd.read_csv(stream_file)

        # Load or create present data
        if os.path.exists(present_file):
            present_df = pd.read_csv(present_file)
            initial_count = len(present_df)
        else:
            # Create empty dataframe with same columns
            present_df = pd.DataFrame(columns=stream_df.columns)
            initial_count = 0
            os.makedirs(PRESENT_PATH, exist_ok=True)

        # Calculate rows to add
        total_stream_rows = len(stream_df)
        rows_to_add = min(batch_size, total_stream_rows)

        if rows_to_add == 0:
            print(f"[TRANS] No rows available in stream")
            return {"rows_added": 0, "total_present": initial_count, "remaining_stream": 0}

        # Get the batch to add
        batch_to_add = stream_df.head(rows_to_add).copy()

        # Append to present data
        updated_present_df = pd.concat([present_df, batch_to_add], ignore_index=True)

        # Save updated present data
        updated_present_df.to_csv(present_file, index=False)

        # Remove added rows from stream
        remaining_stream_df = stream_df.iloc[rows_to_add:].copy()
        remaining_stream_df.to_csv(stream_file, index=False)

        print(f"[TRANS] Added {rows_to_add} rows | Total present: {len(updated_present_df)} | Remaining stream: {len(remaining_stream_df)}")

        # Sleep for delay
        if delay > 0:
            time.sleep(delay)

        return {
            "rows_added": rows_to_add,
            "total_present": len(updated_present_df),
            "remaining_stream": len(remaining_stream_df),
            "initial_count": initial_count
        }

    except Exception as e:
        print(f"[TRANS] Error during streaming: {str(e)}")
        return {"error": str(e), "rows_added": 0}


def stream_trans_continuous(batch_size=10, delay=5, max_iterations=None):
    """
    Continuously stream rows until stream is empty

    Parameters:
    -----------
    batch_size : int
        Number of rows to add from stream to present in each iteration
    delay : float
        Time delay in seconds between each batch update
    max_iterations : int or None
        Maximum number of iterations. None means run until stream is empty

    Returns:
    --------
    dict : Overall statistics
    """
    iteration = 0
    total_rows_added = 0

    print(f"\n{'='*60}")
    print(f"Starting continuous streaming for TRANS")
    print(f"Batch size: {batch_size}, Delay: {delay}s")
    print(f"{'='*60}\n")

    while True:
        iteration += 1

        if max_iterations and iteration > max_iterations:
            print(f"\n[TRANS] Reached maximum iterations ({max_iterations})")
            break

        result = stream_trans(batch_size=batch_size, delay=delay)

        if "error" in result:
            print(f"[TRANS] Stopping due to error")
            break

        total_rows_added += result["rows_added"]

        if result["remaining_stream"] == 0:
            print(f"\n[TRANS] Stream is empty. Stopping.")
            break

    print(f"\n{'='*60}")
    print(f"TRANS Streaming Complete")
    print(f"Total iterations: {iteration}")
    print(f"Total rows streamed: {total_rows_added}")
    print(f"{'='*60}\n")

    return {
        "total_iterations": iteration,
        "total_rows_added": total_rows_added
    }


if __name__ == "__main__":
    # Example usage: Stream in batches of 20 rows with 3 second delay
    stream_trans_continuous(batch_size=20, delay=3)

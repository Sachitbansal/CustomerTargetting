import time
import pandas as pd
import os
import pathway as pw

def create_stream_data(input_path, output_path=None, delay=0.1):
    """
    Create a streaming CSV file from input data for Pathway to consume.
    This simulates real-time transaction/application events.
    
    Args:
        input_path: Path to input CSV file
        output_path: Path to write streaming CSV (if None, uses input_path with _stream suffix)
        delay: Delay between rows (not used in Pathway, but kept for compatibility)
    """
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_stream{ext}"
    
    # Read input data
    df = pd.read_csv(input_path, sep=';')
    
    # Write to output (Pathway will read this incrementally)
    df.to_csv(output_path, index=False, sep=';')
    
    return output_path

def stream_csv_rows(input_path, delay=1.0):
    """
    Generator function for streaming CSV rows (for non-Pathway use).
    
    Args:
        input_path: Path to CSV file
        delay: Delay between rows in seconds
        
    Yields:
        Dictionary of row data
    """
    df = pd.read_csv(input_path, sep=';')
    for _, row in df.iterrows():
        yield row.to_dict()
        time.sleep(delay)

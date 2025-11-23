# sort_transactions.py

import pandas as pd
import os

# --- Configuration ---
# This is the file we will be sorting.
TRANSACTION_FILE = 'streaming_transactions.csv'

def sort_transaction_file_by_datetime():
    """
    Loads the transaction file, sorts it chronologically by the txn_datetime column,
    and overwrites the original file with the sorted data. This is a critical
    pre-processing step for any event-driven simulation.
    """
    # 1. --- Check if the input file exists ---
    if not os.path.exists(TRANSACTION_FILE):
        print(f"Error: File not found at '{TRANSACTION_FILE}'.")
        print("Please make sure you have run split_data.py to generate this file first.")
        return

    try:
        # 2. --- Load the CSV into a pandas DataFrame ---
        print(f"Loading transactions from '{TRANSACTION_FILE}'...")
        
        # We use 'parse_dates' to tell pandas to automatically convert
        # the 'txn_datetime' column from text into a proper datetime object.
        # This is essential for correct sorting.
        df = pd.read_csv(TRANSACTION_FILE, parse_dates=['txn_datetime'])
        
        print(f"Loaded {len(df)} transactions successfully.")

        # 3. --- Sort the DataFrame ---
        print("Sorting transactions chronologically by 'txn_datetime'...")
        
        # sort_values() is the primary function for sorting.
        # 'inplace=True' modifies the DataFrame directly without creating a copy.
        df.sort_values(by='txn_datetime', inplace=True)

        # 4. --- Save the sorted DataFrame back to the original file ---
        print(f"Saving the sorted data back to '{TRANSACTION_FILE}'...")
        
        # 'index=False' is crucial to prevent pandas from writing a new,
        # unwanted index column into the CSV file.
        df.to_csv(TRANSACTION_FILE, index=False)

        print("\nProcess complete. The transaction file is now sorted chronologically.")

    except Exception as e:
        print(f"\nAn error occurred during the process: {e}")
        print("Please check that the CSV file is not corrupted and the 'txn_datetime' column exists.")

if __name__ == '__main__':
    sort_transaction_file_by_datetime()